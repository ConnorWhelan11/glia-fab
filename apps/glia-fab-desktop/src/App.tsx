import { listen } from "@tauri-apps/api/event";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { FitAddon } from "xterm-addon-fit";
import { Terminal } from "xterm";
import "xterm/css/xterm.css";
import { invoke } from "@tauri-apps/api/tauri";

type Nav = "projects" | "runs" | "terminals" | "viewer";

type ServerInfo = {
  base_url: string;
};

type ProjectInfo = {
  root: string;
  viewer_dir: string | null;
  dev_kernel_dir: string | null;
};

type PtySessionInfo = {
  id: string;
  cwd: string | null;
  command: string | null;
};

type RunInfo = {
  id: string;
  dir: string;
  modifiedMs: number | null;
};

type ArtifactInfo = {
  relPath: string;
  kind: string;
  sizeBytes: number;
  url: string;
};

type JobInfo = {
  jobId: string;
  runId: string;
  runDir: string;
};

export default function App() {
  const [nav, setNav] = useState<Nav>("projects");
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [activeProjectRoot, setActiveProjectRoot] = useState<string | null>(
    null
  );

  const [sessions, setSessions] = useState<PtySessionInfo[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [activeArtifactRelPath, setActiveArtifactRelPath] = useState<string | null>(
    null
  );
  const [artifactText, setArtifactText] = useState<string | null>(null);
  const [jobOutputs, setJobOutputs] = useState<Record<string, string>>({});
  const [jobExitCodes, setJobExitCodes] = useState<Record<string, number | null>>(
    {}
  );

  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [newProjectPath, setNewProjectPath] = useState("");

  const [isNewRunOpen, setIsNewRunOpen] = useState(false);
  const [newRunCommand, setNewRunCommand] = useState("ls -la");
  const [newRunLabel, setNewRunLabel] = useState("");

  const terminalRef = useRef<HTMLDivElement | null>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);

  const activeProject = useMemo(
    () => projects.find((p) => p.root === activeProjectRoot) ?? null,
    [projects, activeProjectRoot]
  );

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) ?? null,
    [sessions, activeSessionId]
  );

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  const activeRun = useMemo(
    () => runs.find((r) => r.id === activeRunId) ?? null,
    [runs, activeRunId]
  );

  const activeArtifact = useMemo(
    () => artifacts.find((a) => a.relPath === activeArtifactRelPath) ?? null,
    [artifacts, activeArtifactRelPath]
  );

  useEffect(() => {
    (async () => {
      try {
        const info = await invoke<ServerInfo>("get_server_info");
        setServerInfo(info);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  async function refreshRuns(projectRoot: string) {
    try {
      const list = await invoke<RunInfo[]>("runs_list", { params: { projectRoot } });
      setRuns(list);
    } catch (e) {
      setError(String(e));
    }
  }

  async function loadArtifacts(projectRoot: string, runId: string) {
    try {
      const list = await invoke<ArtifactInfo[]>("run_artifacts", {
        params: { projectRoot, runId },
      });
      setArtifacts(list);
      setActiveArtifactRelPath(null);
      setArtifactText(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const list = await invoke<PtySessionInfo[]>("pty_list");
        setSessions(list);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  useEffect(() => {
    const unsubs: Array<() => void> = [];
    (async () => {
      const unlistenOutput = await listen<{ session_id: string; data: string }>(
        "pty_output",
        (event) => {
          if (event.payload.session_id !== activeSessionId) return;
          xtermRef.current?.write(event.payload.data);
        }
      );
      unsubs.push(unlistenOutput);

      const unlistenExit = await listen<{
        session_id: string;
        exit_code: number | null;
      }>("pty_exit", (event) => {
        setSessions((prev) => prev.filter((s) => s.id !== event.payload.session_id));
        setActiveSessionId((prev) =>
          prev === event.payload.session_id ? null : prev
        );
      });
      unsubs.push(unlistenExit);
    })();

    return () => {
      for (const u of unsubs) u();
    };
  }, [activeSessionId]);

  useEffect(() => {
    const unsubs: Array<() => void> = [];
    (async () => {
      const unlistenOutput = await listen<{ job_id: string; run_id: string; data: string }>(
        "job_output",
        (event) => {
          const { run_id, data } = event.payload;
          setJobOutputs((prev) => ({ ...prev, [run_id]: (prev[run_id] ?? "") + data }));
        }
      );
      unsubs.push(unlistenOutput);

      const unlistenExit = await listen<{ job_id: string; run_id: string; exit_code: number | null }>(
        "job_exit",
        async (event) => {
          const { run_id, exit_code } = event.payload;
          setJobExitCodes((prev) => ({ ...prev, [run_id]: exit_code }));
          if (activeProject) {
            await refreshRuns(activeProject.root);
            if (activeRunId === run_id) {
              await loadArtifacts(activeProject.root, run_id);
            }
          }
        }
      );
      unsubs.push(unlistenExit);
    })();

    return () => {
      for (const u of unsubs) u();
    };
  }, [activeProject, activeRunId]);

  useEffect(() => {
    if (nav !== "terminals") return;
    if (!terminalRef.current) return;

    terminalRef.current.innerHTML = "";

    if (!xtermRef.current) {
      const term = new Terminal({
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
        fontSize: 13,
        cursorBlink: true,
        convertEol: true,
        theme: {
          background: "#0b0d10",
          foreground: "rgba(255,255,255,0.9)",
          cursor: "rgba(212,165,116,0.95)",
          selection: "rgba(212,165,116,0.25)",
        },
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(terminalRef.current);
      fit.fit();
      term.onData((data) => {
        const sessionId = activeSessionIdRef.current;
        if (!sessionId) return;
        invoke("pty_write", { params: { sessionId, data } }).catch((e) =>
          setError(String(e))
        );
      });
      xtermRef.current = term;
      fitRef.current = fit;
      term.focus();
    } else {
      xtermRef.current.open(terminalRef.current);
      fitRef.current?.fit();
      xtermRef.current.focus();
    }

    const term = xtermRef.current;
    const fit = fitRef.current;
      const onResize = () => {
        fit?.fit();
        if (!term) return;
        const cols = term.cols;
        const rows = term.rows;
        if (activeSessionId) {
          invoke("pty_resize", { params: { sessionId: activeSessionId, cols, rows } }).catch(
            () => {}
          );
        }
      };
    window.addEventListener("resize", onResize);
    onResize();
    return () => window.removeEventListener("resize", onResize);
  }, [nav, activeSessionId]);

  useEffect(() => {
    if (nav !== "terminals") return;
    if (!xtermRef.current) return;
    xtermRef.current.reset();
    xtermRef.current.writeln(
      activeSessionId
        ? `Connected to session ${activeSessionId}`
        : "Select or create a terminal session"
    );
    xtermRef.current.focus();
  }, [nav, activeSessionId]);

  async function confirmAddProject() {
    const root = newProjectPath.trim();
    if (!root) {
      setError("Project path is required.");
      return;
    }

    try {
      const info = await invoke<ProjectInfo>("detect_project", { root });
      setProjects((prev) => {
        const exists = prev.some((p) => p.root === info.root);
        return exists ? prev : [...prev, info];
      });
      setActiveProjectRoot(info.root);
      await invoke("set_server_roots", {
        params: { viewerDir: info.viewer_dir ?? null, projectRoot: info.root },
      });
      await refreshRuns(info.root);
      setIsAddProjectOpen(false);
      setNewProjectPath("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function setActiveProject(root: string) {
    setActiveProjectRoot(root);
    const info = projects.find((p) => p.root === root) ?? null;
    try {
      await invoke("set_server_roots", {
        params: { viewerDir: info?.viewer_dir ?? null, projectRoot: root },
      });
      await refreshRuns(root);
    } catch (e) {
      setError(String(e));
    }
  }

  async function createTerminal() {
    const cwd = activeProject?.root ?? null;
    const cols = xtermRef.current?.cols ?? 120;
    const rows = xtermRef.current?.rows ?? 34;
    try {
      const id = await invoke<string>("pty_create", { params: { cwd, cols, rows } });
      const list = await invoke<PtySessionInfo[]>("pty_list");
      setSessions(list);
      setActiveSessionId(id);
      setNav("terminals");
    } catch (e) {
      setError(String(e));
    }
  }

  async function killTerminal(sessionId: string) {
    try {
      await invoke("pty_kill", { params: { sessionId } });
    } catch (e) {
      setError(String(e));
    }
  }

  const viewerUrl = useMemo(() => {
    if (!serverInfo) return null;
    if (!activeProject?.viewer_dir) return null;
    return `${serverInfo.base_url}/viewer/index.html`;
  }, [serverInfo, activeProject]);

  const activeArtifactUrl = useMemo(() => {
    if (!serverInfo) return null;
    if (!activeArtifact) return null;
    return `${serverInfo.base_url}${activeArtifact.url}`;
  }, [serverInfo, activeArtifact]);

  async function confirmStartRun() {
    if (!activeProject) {
      setError("Select a project first.");
      return;
    }
    const command = newRunCommand.trim();
    if (!command) {
      setError("Command is required.");
      return;
    }

    try {
      const job = await invoke<JobInfo>("job_start", {
        params: {
          projectRoot: activeProject.root,
          command,
          label: newRunLabel.trim() ? newRunLabel.trim() : null,
        },
      });
      setJobOutputs((prev) => ({ ...prev, [job.runId]: "" }));
      setJobExitCodes((prev) => ({ ...prev, [job.runId]: null }));
      setActiveRunId(job.runId);
      setNav("runs");
      await refreshRuns(activeProject.root);
      await loadArtifacts(activeProject.root, job.runId);
      setIsNewRunOpen(false);
      setNewRunLabel("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function selectRun(runId: string) {
    setActiveRunId(runId);
    setActiveArtifactRelPath(null);
    setArtifactText(null);
    if (activeProject) {
      await loadArtifacts(activeProject.root, runId);
    }
  }

  async function selectArtifact(relPath: string) {
    setActiveArtifactRelPath(relPath);
    setArtifactText(null);
    const artifact = artifacts.find((a) => a.relPath === relPath) ?? null;
    if (!artifact || !serverInfo) return;
    if (artifact.kind !== "json" && artifact.kind !== "text" && artifact.kind !== "html") return;
    try {
      const url = `${serverInfo.base_url}${artifact.url}`;
      const res = await fetch(url, { cache: "no-store" });
      const text = await res.text();
      if (artifact.kind === "json") {
        try {
          setArtifactText(JSON.stringify(JSON.parse(text), null, 2));
          return;
        } catch {
          // fall through
        }
      }
      setArtifactText(text);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="app">
      <div className="sidebar">
        <div className="brand">
          <div className="brand-badge">GF</div>
          <div>
            <div className="brand-title">Glia Fab Desktop</div>
            <div className="brand-subtitle">Mission Control</div>
          </div>
        </div>

        <div className="nav">
          <button
            className={nav === "projects" ? "active" : ""}
            onClick={() => setNav("projects")}
          >
            Projects
          </button>
          <button
            className={nav === "runs" ? "active" : ""}
            onClick={() => setNav("runs")}
          >
            Runs
          </button>
          <button
            className={nav === "terminals" ? "active" : ""}
            onClick={() => setNav("terminals")}
          >
            Terminals
          </button>
          <button
            className={nav === "viewer" ? "active" : ""}
            onClick={() => setNav("viewer")}
          >
            Viewer
          </button>
        </div>

        <div style={{ marginTop: 14 }} className="muted">
          <div>Server: {serverInfo ? serverInfo.base_url : "…"}</div>
          <div>
            Active:{" "}
            {activeProject ? activeProject.root.split("/").slice(-1)[0] : "—"}
          </div>
        </div>
      </div>

      <div className="main">
        {error && (
          <div className="panel" style={{ marginBottom: 12 }}>
            <div className="panel-header">
              <div className="panel-title">Error</div>
              <button className="btn" onClick={() => setError(null)}>
                Dismiss
              </button>
            </div>
            <div style={{ padding: 14 }} className="muted">
              {error}
            </div>
          </div>
        )}

        {nav === "projects" && (
          <div className="panel" style={{ height: "100%" }}>
            <div className="panel-header">
              <div className="panel-title">Projects</div>
              <div className="row">
                <button
                  className="btn primary"
                  onClick={() => {
                    setNewProjectPath("");
                    setIsAddProjectOpen(true);
                  }}
                >
                  Add Project
                </button>
              </div>
            </div>

            <div className="split" style={{ gridTemplateColumns: "380px 1fr" }}>
              <div className="list">
                {projects.length === 0 && (
                  <div className="list-item muted">
                    Add a repo root (e.g. this folder).
                  </div>
                )}
                {projects.map((p) => (
                  <div
                    key={p.root}
                    className={
                      "list-item " + (p.root === activeProjectRoot ? "active" : "")
                    }
                    onClick={() => setActiveProject(p.root)}
                  >
                    <div style={{ fontWeight: 650 }}>
                      {p.root.split("/").slice(-1)[0]}
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                      {p.root}
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                      Viewer: {p.viewer_dir ? "yes" : "no"} · Dev Kernel:{" "}
                      {p.dev_kernel_dir ? "yes" : "no"}
                    </div>
                  </div>
                ))}
              </div>

              <div className="detail">
                <div className="panel-header">
                  <div className="panel-title">Project</div>
                  <div className="row">
                    <button className="btn" onClick={createTerminal} disabled={!activeProject}>
                      New Terminal
                    </button>
                  </div>
                </div>
                <div style={{ padding: 14, overflow: "auto" }}>
                  {!activeProject && (
                    <div className="muted">Select a project to view details.</div>
                  )}
                  {activeProject && (
                    <>
                      <div style={{ fontWeight: 650, marginBottom: 6 }}>
                        {activeProject.root}
                      </div>
                      <div className="muted" style={{ marginBottom: 10 }}>
                        Viewer dir: {activeProject.viewer_dir ?? "—"}
                      </div>
                      <div className="muted">
                        Dev kernel dir: {activeProject.dev_kernel_dir ?? "—"}
                      </div>
                      <div style={{ height: 18 }} />
                      <div className="muted">
                        Tip: run `fab-gate`, `fab-render`, `fab-godot`, or `dev-kernel`
                        commands in a terminal session.
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {nav === "runs" && (
          <div className="panel" style={{ height: "100%" }}>
            <div className="panel-header">
              <div className="panel-title">Runs</div>
              <div className="row">
                <button
                  className="btn primary"
                  onClick={() => {
                    setNewRunCommand("ls -la");
                    setNewRunLabel("");
                    setIsNewRunOpen(true);
                  }}
                  disabled={!activeProject}
                >
                  New Run
                </button>
                <button
                  className="btn"
                  onClick={() => activeProject && refreshRuns(activeProject.root)}
                  disabled={!activeProject}
                >
                  Refresh
                </button>
              </div>
            </div>

            <div className="split">
              <div className="list">
                {!activeProject && (
                  <div className="list-item muted">Select a project first.</div>
                )}
                {activeProject && runs.length === 0 && (
                  <div className="list-item muted">
                    No runs yet. Output is expected under <code>.glia-fab/runs/</code>.
                  </div>
                )}
                {runs.map((r) => (
                  <div
                    key={r.id}
                    className={"list-item " + (r.id === activeRunId ? "active" : "")}
                    onClick={() => selectRun(r.id)}
                  >
                    <div style={{ fontWeight: 650 }}>{r.id}</div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                      {jobExitCodes[r.id] === undefined
                        ? ""
                        : jobExitCodes[r.id] === null
                          ? "running"
                          : `exit ${jobExitCodes[r.id]}`}
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                      {r.modifiedMs ? new Date(r.modifiedMs).toLocaleString() : ""}
                    </div>
                  </div>
                ))}
              </div>

              <div className="detail">
                <div className="panel-header">
                  <div className="panel-title">Details</div>
                  <div className="muted">{activeRun ? activeRun.id : "—"}</div>
                </div>

                <div className="split" style={{ gridTemplateColumns: "360px 1fr" }}>
                  <div className="list">
                    {activeRun && artifacts.length === 0 && (
                      <div className="list-item muted">No artifacts found.</div>
                    )}
                    {activeRun &&
                      artifacts.map((a) => (
                        <div
                          key={a.relPath}
                          className={
                            "list-item " +
                            (a.relPath === activeArtifactRelPath ? "active" : "")
                          }
                          onClick={() => selectArtifact(a.relPath)}
                        >
                          <div style={{ fontWeight: 650 }}>{a.relPath}</div>
                          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                            {a.kind} · {a.sizeBytes.toLocaleString()} bytes
                          </div>
                        </div>
                      ))}
                  </div>

                  <div style={{ overflow: "auto" }}>
                    {!activeRun && (
                      <div style={{ padding: 14 }} className="muted">
                        Select a run to view artifacts.
                      </div>
                    )}

                    {activeRun && (
                      <div style={{ padding: 14 }}>
                        <div className="row" style={{ justifyContent: "space-between" }}>
                          <div>
                            <div style={{ fontWeight: 650 }}>{activeRun.id}</div>
                            <div className="muted" style={{ marginTop: 4 }}>
                              {activeRun.dir}
                            </div>
                          </div>
                          <div className="row">
                            {serverInfo && (
                              <a
                                className="btn"
                                href={`${serverInfo.base_url}/artifacts/${activeRun.id}/terminal.log`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open Log
                              </a>
                            )}
                          </div>
                        </div>

                        {jobOutputs[activeRun.id] && (
                          <>
                            <div style={{ height: 12 }} />
                            <div className="muted" style={{ marginBottom: 6 }}>
                              Live output
                            </div>
                            <pre
                              style={{
                                whiteSpace: "pre-wrap",
                                background: "rgba(0,0,0,0.28)",
                                border: "1px solid rgba(255,255,255,0.08)",
                                borderRadius: 12,
                                padding: 12,
                                margin: 0,
                                maxHeight: 220,
                                overflow: "auto",
                              }}
                            >
                              {jobOutputs[activeRun.id]}
                            </pre>
                          </>
                        )}

                        {activeArtifact && (
                          <>
                            <div style={{ height: 16 }} />
                            <div style={{ fontWeight: 650, marginBottom: 6 }}>
                              {activeArtifact.relPath}
                            </div>
                            <div className="muted" style={{ marginBottom: 10 }}>
                              {activeArtifact.kind}
                            </div>

                            {activeArtifact.kind === "image" && activeArtifactUrl && (
                              <img
                                src={activeArtifactUrl}
                                style={{
                                  maxWidth: "100%",
                                  borderRadius: 12,
                                  border: "1px solid rgba(255,255,255,0.08)",
                                }}
                              />
                            )}

                            {(activeArtifact.kind === "json" ||
                              activeArtifact.kind === "text" ||
                              activeArtifact.kind === "html") && (
                              <pre
                                style={{
                                  whiteSpace: "pre-wrap",
                                  background: "rgba(0,0,0,0.28)",
                                  border: "1px solid rgba(255,255,255,0.08)",
                                  borderRadius: 12,
                                  padding: 12,
                                  margin: 0,
                                }}
                              >
                                {artifactText ?? "Loading…"}
                              </pre>
                            )}

                            {activeArtifactUrl && (
                              <div style={{ height: 10 }}>
                                <a
                                  className="btn"
                                  href={activeArtifactUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Open Artifact
                                </a>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {nav === "terminals" && (
          <div className="panel" style={{ height: "100%" }}>
            <div className="panel-header">
              <div className="panel-title">Terminals</div>
              <div className="row">
                <button className="btn primary" onClick={createTerminal}>
                  New Terminal
                </button>
                {activeSession && (
                  <button className="btn" onClick={() => killTerminal(activeSession.id)}>
                    Kill
                  </button>
                )}
              </div>
            </div>

            <div className="split">
              <div className="list">
                {sessions.length === 0 && (
                  <div className="list-item muted">No sessions yet.</div>
                )}
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className={"list-item " + (s.id === activeSessionId ? "active" : "")}
                    onClick={() => setActiveSessionId(s.id)}
                  >
                    <div style={{ fontWeight: 650 }}>
                      {s.command ?? "shell"}
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                      {s.cwd ?? "—"}
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                      {s.id}
                    </div>
                  </div>
                ))}
              </div>
              <div className="detail">
                <div className="panel-header">
                  <div className="panel-title">Session</div>
                  <div className="muted">
                    {activeSessionId ? activeSessionId : "—"}
                  </div>
                </div>
                <div ref={terminalRef} className="terminal" />
              </div>
            </div>
          </div>
        )}

        {nav === "viewer" && (
          <div className="panel" style={{ height: "100%" }}>
            <div className="panel-header">
              <div className="panel-title">Outora Viewer</div>
              <div className="muted">
                {activeProject?.viewer_dir ? "served locally" : "no viewer in project"}
              </div>
            </div>
            <div style={{ height: "calc(100% - 49px)" }}>
              {viewerUrl ? (
                <iframe className="iframe" src={viewerUrl} />
              ) : (
                <div style={{ padding: 14 }} className="muted">
                  Select a project that contains `fab/outora-library/viewer/`.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {isAddProjectOpen && (
        <div className="modal-overlay" onClick={() => setIsAddProjectOpen(false)}>
          <div className="panel modal" onClick={(e) => e.stopPropagation()}>
            <div className="panel-header">
              <div className="panel-title">Add Project</div>
              <button className="btn" onClick={() => setIsAddProjectOpen(false)}>
                Close
              </button>
            </div>
            <div className="form">
              <div className="muted">Paste the repo root path (absolute).</div>
              <input
                className="text-input"
                autoFocus
                value={newProjectPath}
                onChange={(e) => setNewProjectPath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") confirmAddProject();
                }}
                placeholder="/Users/…/glia-fab"
              />
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn" onClick={() => setIsAddProjectOpen(false)}>
                  Cancel
                </button>
                <button className="btn primary" onClick={confirmAddProject}>
                  Add
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {isNewRunOpen && (
        <div className="modal-overlay" onClick={() => setIsNewRunOpen(false)}>
          <div className="panel modal" onClick={(e) => e.stopPropagation()}>
            <div className="panel-header">
              <div className="panel-title">New Run</div>
              <button className="btn" onClick={() => setIsNewRunOpen(false)}>
                Close
              </button>
            </div>
            <div className="form">
              <div className="muted">Command runs in the project root and writes to `.glia-fab/runs/…`.</div>
              <input
                className="text-input"
                autoFocus
                value={newRunCommand}
                onChange={(e) => setNewRunCommand(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") confirmStartRun();
                }}
                placeholder="fab-gate --config …"
              />
              <input
                className="text-input"
                value={newRunLabel}
                onChange={(e) => setNewRunLabel(e.target.value)}
                placeholder="Label (optional)"
              />
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn" onClick={() => setIsNewRunOpen(false)}>
                  Cancel
                </button>
                <button className="btn primary" onClick={confirmStartRun}>
                  Start
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
