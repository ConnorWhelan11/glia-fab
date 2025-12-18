# Glia Fab Desktop (Mission Control)

Tauri desktop app for orchestrating Glia Fab terminals/runs and previewing assets (including the Outora Library Three.js viewer + Godot web exports).

## Dev

From repo root:

- `cd apps/glia-fab-desktop`
- `npm install`
- `npm run tauri dev`

If Rust is too old, install the pinned toolchain:

- `cd apps/glia-fab-desktop/src-tauri`
- `rustup show`
- `rustup toolchain install 1.85.0`

The app starts a local HTTP server on `127.0.0.1` (ephemeral port) to serve:

- the selected project’s `fab/outora-library/viewer/` at `/viewer/` (so Godot Play mode works)

## Usage (current MVP)

- Add a project by pasting its repo root path.
- Click **New Terminal** to start a PTY session in that repo.
- Use **Viewer** to embed the Outora Library Three.js viewer (served over HTTP so Play mode can work).

## Artifacts (recommended convention)

- Centralize run outputs under `<repo>/.glia-fab/runs/<run_id>/…`
- “Publish” (copy/symlink) any curated exports you want visible in the static viewer under `fab/outora-library/viewer/assets/...`
