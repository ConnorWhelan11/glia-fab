#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, RwLock};
use std::thread;
use std::time::Duration;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, Context, Result};
use mime_guess::MimeGuess;
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State};
use uuid::Uuid;

type CommandResult<T> = std::result::Result<T, String>;

// ---------------------------------------------
// Local HTTP server (for viewer + game exports)
// ---------------------------------------------

#[derive(Clone, Default)]
struct WebRoots {
  viewer_dir: Option<PathBuf>,
  runs_dir: Option<PathBuf>,
}

struct WebServerState {
  addr: SocketAddr,
  roots: Arc<RwLock<WebRoots>>,
}

#[derive(Serialize)]
struct ServerInfo {
  base_url: String,
}

fn safe_join(root: &Path, requested_path: &str) -> Result<PathBuf> {
  let path = requested_path.split('?').next().unwrap_or("");
  let mut rel = path.trim_start_matches('/').to_string();
  if rel.is_empty() || rel.ends_with('/') {
    rel.push_str("index.html");
  }

  let mut out = PathBuf::from(root);
  for part in rel.split('/') {
    if part.is_empty() || part == "." {
      continue;
    }
    if part == ".." {
      return Err(anyhow!("path traversal blocked"));
    }
    out.push(part);
  }
  Ok(out)
}

fn start_local_server(roots: Arc<RwLock<WebRoots>>) -> Result<WebServerState> {
  let listener = TcpListener::bind("127.0.0.1:0").context("bind local http server")?;
  let addr = listener.local_addr().context("read local http addr")?;

  let roots_for_thread = roots.clone();
  thread::spawn(move || {
    let server =
      tiny_http::Server::from_listener(listener, None).expect("tiny_http server");
    for request in server.incoming_requests() {
      let url = request.url().to_string();
      let method = request.method().as_str().to_string();

      let send_response = |request: tiny_http::Request,
                           status: u16,
                           content_type: Option<String>,
                           body: Option<Vec<u8>>| {
        let mut response = match body {
          Some(bytes) => tiny_http::Response::from_data(bytes)
            .with_status_code(tiny_http::StatusCode(status))
            .boxed(),
          None => tiny_http::Response::empty(tiny_http::StatusCode(status)).boxed(),
        };
        if let Some(ct) = content_type {
          let header =
            tiny_http::Header::from_bytes(&b"Content-Type"[..], ct.as_bytes())
              .expect("content-type header");
          response = response.with_header(header).boxed();
        }
        response = response
          .with_header(
            tiny_http::Header::from_bytes(&b"Cache-Control"[..], &b"no-store"[..])
              .expect("cache header"),
          )
          .boxed();
        let _ = request.respond(response);
      };

      let (root, path) = if url.starts_with("/viewer") {
        let viewer_dir = {
          roots_for_thread
            .read()
            .ok()
            .and_then(|r| r.viewer_dir.clone())
        };
        let Some(viewer_dir) = viewer_dir else {
          send_response(
            request,
            404,
            Some("text/plain".into()),
            Some(b"Viewer root not configured".to_vec()),
          );
          continue;
        };
        (viewer_dir, url.trim_start_matches("/viewer"))
      } else if url.starts_with("/artifacts") {
        let runs_dir = {
          roots_for_thread
            .read()
            .ok()
            .and_then(|r| r.runs_dir.clone())
        };
        let Some(runs_dir) = runs_dir else {
          send_response(
            request,
            404,
            Some("text/plain".into()),
            Some(b"Artifacts root not configured".to_vec()),
          );
          continue;
        };
        (runs_dir, url.trim_start_matches("/artifacts"))
      } else {
        send_response(request, 404, Some("text/plain".into()), Some(b"Not found".to_vec()));
        continue;
      };

      let resolved = match safe_join(&root, path) {
        Ok(p) => p,
        Err(_) => {
          send_response(request, 403, Some("text/plain".into()), Some(b"Forbidden".to_vec()));
          continue;
        }
      };

      if !resolved.is_file() {
        send_response(request, 404, Some("text/plain".into()), Some(b"Not found".to_vec()));
        continue;
      }

      let mime = MimeGuess::from_path(&resolved).first_or_octet_stream();
      let content_type = Some(mime.essence_str().to_string());

      if method == "HEAD" {
        send_response(request, 200, content_type, None);
        continue;
      }

      let bytes = match fs::read(&resolved) {
        Ok(b) => b,
        Err(_) => {
          send_response(
            request,
            500,
            Some("text/plain".into()),
            Some(b"Failed to read file".to_vec()),
          );
          continue;
        }
      };
      send_response(request, 200, content_type, Some(bytes));
    }
  });

  Ok(WebServerState { addr, roots })
}

#[tauri::command]
fn get_server_info(server: State<'_, Arc<WebServerState>>) -> ServerInfo {
  ServerInfo {
    base_url: format!("http://127.0.0.1:{}", server.addr.port()),
  }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SetServerRootsParams {
  #[serde(default)]
  viewer_dir: Option<String>,
  #[serde(default)]
  project_root: Option<String>,
}

#[tauri::command]
fn set_server_roots(
  server: State<'_, Arc<WebServerState>>,
  params: SetServerRootsParams,
) -> CommandResult<()> {
  let mut roots = server
    .roots
    .write()
    .map_err(|_| "server roots lock poisoned".to_string())?;
  roots.viewer_dir = params.viewer_dir.map(PathBuf::from);
  roots.runs_dir = params.project_root.map(|p| PathBuf::from(p).join(".glia-fab/runs"));
  Ok(())
}

#[derive(Serialize)]
struct ProjectInfo {
  root: String,
  viewer_dir: Option<String>,
  dev_kernel_dir: Option<String>,
}

#[tauri::command]
fn detect_project(root: String) -> CommandResult<ProjectInfo> {
  let root_path = PathBuf::from(&root);
  if !root_path.is_dir() {
    return Err(format!("not a directory: {}", root));
  }
  let viewer_dir = root_path.join("fab/outora-library/viewer");
  let dev_kernel_dir = root_path.join("dev-kernel");
  Ok(ProjectInfo {
    root,
    viewer_dir: viewer_dir.is_dir().then(|| viewer_dir.to_string_lossy().to_string()),
    dev_kernel_dir: dev_kernel_dir
      .is_dir()
      .then(|| dev_kernel_dir.to_string_lossy().to_string()),
  })
}

// ---------------------------------------------
// Runs / artifacts
// ---------------------------------------------

fn epoch_ms_now() -> u64 {
  SystemTime::now()
    .duration_since(UNIX_EPOCH)
    .map(|d| d.as_millis() as u64)
    .unwrap_or(0)
}

fn to_epoch_ms(ts: SystemTime) -> Option<u64> {
  ts.duration_since(UNIX_EPOCH).ok().map(|d| d.as_millis() as u64)
}

fn runs_dir_for_project(project_root: &str) -> PathBuf {
  PathBuf::from(project_root).join(".glia-fab/runs")
}

fn sanitize_slug(input: &str) -> String {
  let mut out = String::new();
  for c in input.chars() {
    let keep = c.is_ascii_alphanumeric() || c == '-' || c == '_';
    if keep {
      out.push(c.to_ascii_lowercase());
    } else if c.is_whitespace() {
      out.push('_');
    }
    if out.len() >= 32 {
      break;
    }
  }
  if out.is_empty() {
    "run".to_string()
  } else {
    out
  }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RunInfo {
  id: String,
  dir: String,
  modified_ms: Option<u64>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RunsListParams {
  project_root: String,
}

#[tauri::command]
fn runs_list(params: RunsListParams) -> CommandResult<Vec<RunInfo>> {
  let runs_dir = runs_dir_for_project(&params.project_root);
  if !runs_dir.is_dir() {
    return Ok(Vec::new());
  }

  let mut runs: Vec<RunInfo> = Vec::new();
  let entries = fs::read_dir(&runs_dir).map_err(|e| e.to_string())?;
  for entry in entries {
    let entry = entry.map_err(|e| e.to_string())?;
    let path = entry.path();
    if !path.is_dir() {
      continue;
    }
    let id = entry.file_name().to_string_lossy().to_string();
    let modified_ms = entry
      .metadata()
      .ok()
      .and_then(|m| m.modified().ok())
      .and_then(to_epoch_ms);
    runs.push(RunInfo {
      id,
      dir: path.to_string_lossy().to_string(),
      modified_ms,
    });
  }

  runs.sort_by(|a, b| b.modified_ms.cmp(&a.modified_ms).then_with(|| b.id.cmp(&a.id)));
  Ok(runs)
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ArtifactInfo {
  rel_path: String,
  kind: String,
  size_bytes: u64,
  url: String,
}

fn artifact_kind(path: &Path) -> &'static str {
  let ext = path
    .extension()
    .and_then(|e| e.to_str())
    .unwrap_or("")
    .to_ascii_lowercase();
  match ext.as_str() {
    "json" => "json",
    "png" | "jpg" | "jpeg" | "webp" => "image",
    "glb" => "glb",
    "html" | "htm" => "html",
    "txt" | "log" | "md" | "yaml" | "yml" => "text",
    _ => "other",
  }
}

fn collect_files_recursive(dir: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
  let entries = fs::read_dir(dir)?;
  for entry in entries {
    let entry = entry?;
    let path = entry.path();
    if path.is_dir() {
      collect_files_recursive(&path, out)?;
    } else if path.is_file() {
      out.push(path);
    }
  }
  Ok(())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RunArtifactsParams {
  project_root: String,
  run_id: String,
}

#[tauri::command]
fn run_artifacts(params: RunArtifactsParams) -> CommandResult<Vec<ArtifactInfo>> {
  let runs_dir = runs_dir_for_project(&params.project_root);
  let run_dir = runs_dir.join(&params.run_id);
  if !run_dir.is_dir() {
    return Ok(Vec::new());
  }

  let mut files: Vec<PathBuf> = Vec::new();
  collect_files_recursive(&run_dir, &mut files).map_err(|e| e.to_string())?;

  let mut artifacts: Vec<ArtifactInfo> = Vec::new();
  for file in files {
    let rel = match file.strip_prefix(&run_dir) {
      Ok(r) => r,
      Err(_) => continue,
    };
    let rel_path = rel.to_string_lossy().replace('\\', "/");
    let size_bytes = file.metadata().ok().map(|m| m.len()).unwrap_or(0);
    artifacts.push(ArtifactInfo {
      rel_path: rel_path.clone(),
      kind: artifact_kind(&file).to_string(),
      size_bytes,
      url: format!("/artifacts/{}/{}", params.run_id, rel_path),
    });
  }

  artifacts.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
  Ok(artifacts)
}

// ---------------------------------------------
// Job runner (one-shot commands writing into a run dir)
// ---------------------------------------------

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct JobStartParams {
  project_root: String,
  command: String,
  #[serde(default)]
  label: Option<String>,
  #[serde(default)]
  env: Option<HashMap<String, String>>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct JobInfo {
  job_id: String,
  run_id: String,
  run_dir: String,
}

#[tauri::command]
fn job_start(app: AppHandle, params: JobStartParams) -> CommandResult<JobInfo> {
  let job_id = Uuid::new_v4();
  let now_ms = epoch_ms_now();
  let slug = params
    .label
    .as_deref()
    .map(sanitize_slug)
    .unwrap_or_else(|| sanitize_slug(&params.command));
  let run_id = format!("run_{}_{}_{}", now_ms, slug, job_id.to_string()[..8].to_string());

  let runs_dir = runs_dir_for_project(&params.project_root);
  fs::create_dir_all(&runs_dir).map_err(|e| e.to_string())?;
  let run_dir = runs_dir.join(&run_id);
  fs::create_dir_all(&run_dir).map_err(|e| e.to_string())?;
  let run_dir_str = run_dir.to_string_lossy().to_string();

  let meta_path = run_dir.join("run_meta.json");
  let log_path = run_dir.join("terminal.log");

  let mut meta = serde_json::Map::new();
  meta.insert("run_id".into(), serde_json::Value::String(run_id.clone()));
  meta.insert(
    "project_root".into(),
    serde_json::Value::String(params.project_root.clone()),
  );
  meta.insert("command".into(), serde_json::Value::String(params.command.clone()));
  meta.insert(
    "label".into(),
    params
      .label
      .as_ref()
      .map(|v| serde_json::Value::String(v.clone()))
      .unwrap_or(serde_json::Value::Null),
  );
  meta.insert(
    "started_ms".into(),
    serde_json::Value::Number(serde_json::Number::from(now_ms)),
  );
  meta.insert(
    "env".into(),
    serde_json::Value::Object(
      params
        .env
        .clone()
        .unwrap_or_default()
        .into_iter()
        .map(|(k, v)| (k, serde_json::Value::String(v)))
        .collect(),
    ),
  );
  fs::write(&meta_path, serde_json::to_vec_pretty(&serde_json::Value::Object(meta)).unwrap())
    .map_err(|e| e.to_string())?;

  let pty_system = native_pty_system();
  let pair = pty_system
    .openpty(PtySize {
      rows: 34,
      cols: 120,
      pixel_width: 0,
      pixel_height: 0,
    })
    .map_err(|e| e.to_string())?;

  let mut cmd = CommandBuilder::new("zsh");
  cmd.args(["-lc", &params.command]);
  cmd.cwd(&params.project_root);
  cmd.env("GLIA_FAB_RUN_ID", &run_id);
  cmd.env("GLIA_FAB_RUN_DIR", run_dir_str.clone());
  if let Some(env) = &params.env {
    for (k, v) in env {
      cmd.env(k, v);
    }
  }

  let child = pair
    .slave
    .spawn_command(cmd)
    .map_err(|e| e.to_string())?;
  drop(pair.slave);

  let mut reader = pair
    .master
    .try_clone_reader()
    .map_err(|e| e.to_string())?;

  let job_id_str = job_id.to_string();
  let job_id_for_output = job_id_str.clone();
  let job_id_for_exit = job_id_str.clone();
  let run_id_for_output = run_id.clone();
  let app_for_output = app.clone();
  let log_path_for_output = log_path.clone();
  thread::spawn(move || {
    let mut log_file = fs::OpenOptions::new()
      .create(true)
      .append(true)
      .open(&log_path_for_output)
      .ok();
    let mut buf = [0u8; 8192];
    loop {
      let read = match reader.read(&mut buf) {
        Ok(0) => break,
        Ok(n) => n,
        Err(_) => break,
      };
      let chunk = String::from_utf8_lossy(&buf[..read]).to_string();
      if let Some(f) = &mut log_file {
        let _ = f.write_all(chunk.as_bytes());
        let _ = f.flush();
      }
      let _ = app_for_output.emit_all(
        "job_output",
        serde_json::json!({
          "job_id": job_id_for_output,
          "run_id": run_id_for_output,
          "data": chunk
        }),
      );
    }
  });

  let app_for_exit = app.clone();
  let run_id_for_exit = run_id.clone();
  let run_dir_for_exit = run_dir.clone();
  thread::spawn(move || {
    let mut child = child;
    let exit_code = loop {
      match child.try_wait() {
        Ok(Some(s)) => break Some(s.exit_code()),
        Ok(None) => {}
        Err(_) => break None,
      }
      thread::sleep(Duration::from_millis(120));
    };

    let result_path = run_dir_for_exit.join("job_result.json");
    let _ = fs::write(
      &result_path,
      serde_json::to_vec_pretty(&serde_json::json!({
        "job_id": job_id_for_exit,
        "run_id": run_id_for_exit,
        "exit_code": exit_code,
        "ended_ms": epoch_ms_now()
      }))
      .unwrap(),
    );

    let _ = app_for_exit.emit_all(
      "job_exit",
      serde_json::json!({ "job_id": job_id_str, "run_id": run_id_for_exit, "exit_code": exit_code }),
    );
  });

  Ok(JobInfo {
    job_id: job_id.to_string(),
    run_id,
    run_dir: run_dir_str,
  })
}

// ---------------------------------------------
// PTY sessions (multi-terminal)
// ---------------------------------------------

#[derive(Serialize, Clone)]
struct PtySessionInfo {
  id: String,
  cwd: Option<String>,
  command: Option<String>,
}

struct PtySession {
  info: PtySessionInfo,
  master: Mutex<Box<dyn portable_pty::MasterPty + Send>>,
  writer: Mutex<Box<dyn Write + Send>>,
  child: Mutex<Box<dyn portable_pty::Child + Send>>,
}

struct PtyState {
  sessions: Mutex<HashMap<Uuid, Arc<PtySession>>>,
}

#[derive(Deserialize)]
struct PtyCreateParams {
  cwd: Option<String>,
  cols: Option<u16>,
  rows: Option<u16>,
}

#[tauri::command]
fn pty_create(
  app: AppHandle,
  state: State<'_, Arc<PtyState>>,
  params: PtyCreateParams,
) -> CommandResult<String> {
  let pty_system = native_pty_system();
  let pair = pty_system
    .openpty(PtySize {
      rows: params.rows.unwrap_or(34),
      cols: params.cols.unwrap_or(120),
      pixel_width: 0,
      pixel_height: 0,
    })
    .context("open pty")
    .map_err(|e| e.to_string())?;

  let mut cmd = CommandBuilder::new("zsh");
  cmd.arg("-l");
  if let Some(cwd) = &params.cwd {
    cmd.cwd(cwd);
  }

  let child = pair
    .slave
    .spawn_command(cmd)
    .context("spawn shell in pty")
    .map_err(|e| e.to_string())?;
  drop(pair.slave);

  let master = pair.master;
  let mut reader = master
    .try_clone_reader()
    .context("clone pty reader")
    .map_err(|e| e.to_string())?;
  let writer = master
    .take_writer()
    .context("take pty writer")
    .map_err(|e| e.to_string())?;

  let id = Uuid::new_v4();
  let info = PtySessionInfo {
    id: id.to_string(),
    cwd: params.cwd.clone(),
    command: Some("zsh".into()),
  };
  let session_id = info.id.clone();

  let session = Arc::new(PtySession {
    info: info.clone(),
    master: Mutex::new(master),
    writer: Mutex::new(writer),
    child: Mutex::new(child),
  });

  {
    let mut sessions = state
      .sessions
      .lock()
      .map_err(|_| "pty sessions lock poisoned".to_string())?;
    sessions.insert(id, session.clone());
  }

  let app_for_output = app.clone();
  let session_id_for_output = session_id.clone();
  thread::spawn(move || {
    let mut buf = [0u8; 8192];
    loop {
      let read = match reader.read(&mut buf) {
        Ok(0) => break,
        Ok(n) => n,
        Err(_) => break,
      };
      let chunk = String::from_utf8_lossy(&buf[..read]).to_string();
      let _ = app_for_output.emit_all(
        "pty_output",
        serde_json::json!({ "session_id": session_id_for_output, "data": chunk }),
      );
    }
  });

  let state_for_exit = state.inner().clone();
  let app_for_exit = app.clone();
  thread::spawn(move || {
    let exit_code = loop {
      let status = {
        let mut child = match session.child.lock() {
          Ok(c) => c,
          Err(_) => break None,
        };
        match child.try_wait() {
          Ok(Some(s)) => break Some(s.exit_code()),
          Ok(None) => None,
          Err(_) => break None,
        }
      };
      if status.is_some() {
        break status;
      }
      thread::sleep(Duration::from_millis(120));
    };

    {
      if let Ok(mut sessions) = state_for_exit.sessions.lock() {
        sessions.remove(&id);
      }
    }

    let _ = app_for_exit.emit_all(
      "pty_exit",
      serde_json::json!({ "session_id": session_id, "exit_code": exit_code }),
    );
  });

  Ok(id.to_string())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PtyWriteParams {
  session_id: String,
  data: String,
}

#[tauri::command]
fn pty_write(state: State<'_, Arc<PtyState>>, params: PtyWriteParams) -> CommandResult<()> {
  let id = Uuid::parse_str(&params.session_id).map_err(|e| e.to_string())?;
  let session = {
    let sessions = state
      .sessions
      .lock()
      .map_err(|_| "pty sessions lock poisoned".to_string())?;
    sessions.get(&id).cloned()
  };
  let Some(session) = session else {
    return Err("session not found".to_string());
  };
  let mut writer = session
    .writer
    .lock()
    .map_err(|_| "pty writer lock poisoned".to_string())?;
  writer
    .write_all(params.data.as_bytes())
    .context("write to pty")
    .map_err(|e| e.to_string())?;
  writer.flush().ok();
  Ok(())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PtyResizeParams {
  session_id: String,
  cols: u16,
  rows: u16,
}

#[tauri::command]
fn pty_resize(state: State<'_, Arc<PtyState>>, params: PtyResizeParams) -> CommandResult<()> {
  let id = Uuid::parse_str(&params.session_id).map_err(|e| e.to_string())?;
  let session = {
    let sessions = state
      .sessions
      .lock()
      .map_err(|_| "pty sessions lock poisoned".to_string())?;
    sessions.get(&id).cloned()
  };
  let Some(session) = session else {
    return Ok(());
  };
  let master = session
    .master
    .lock()
    .map_err(|_| "pty master lock poisoned".to_string())?;
  master
    .resize(PtySize {
      rows: params.rows,
      cols: params.cols,
      pixel_width: 0,
      pixel_height: 0,
    })
    .context("resize pty")
    .map_err(|e| e.to_string())?;
  Ok(())
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PtyKillParams {
  session_id: String,
}

#[tauri::command]
fn pty_kill(state: State<'_, Arc<PtyState>>, params: PtyKillParams) -> CommandResult<()> {
  let id = Uuid::parse_str(&params.session_id).map_err(|e| e.to_string())?;
  let session = {
    let sessions = state
      .sessions
      .lock()
      .map_err(|_| "pty sessions lock poisoned".to_string())?;
    sessions.get(&id).cloned()
  };
  let Some(session) = session else {
    return Ok(());
  };
  let mut child = session
    .child
    .lock()
    .map_err(|_| "pty child lock poisoned".to_string())?;
  child.kill().ok();
  Ok(())
}

#[tauri::command]
fn pty_list(state: State<'_, Arc<PtyState>>) -> CommandResult<Vec<PtySessionInfo>> {
  let sessions = state
    .sessions
    .lock()
    .map_err(|_| "pty sessions lock poisoned".to_string())?;
  Ok(sessions.values().map(|s| s.info.clone()).collect())
}

fn main() {
  let roots = Arc::new(RwLock::new(WebRoots::default()));
  let server = Arc::new(start_local_server(roots.clone()).expect("start local server"));

  let pty_state = Arc::new(PtyState {
    sessions: Mutex::new(HashMap::new()),
  });

  tauri::Builder::default()
    .manage(server)
    .manage(pty_state)
    .invoke_handler(tauri::generate_handler![
      get_server_info,
      set_server_roots,
      detect_project,
      runs_list,
      run_artifacts,
      job_start,
      pty_create,
      pty_write,
      pty_resize,
      pty_kill,
      pty_list,
    ])
    .run(tauri::generate_context!())
    .expect("error while running Glia Fab Desktop");
}
