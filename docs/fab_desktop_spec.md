# Glia Fab Desktop (Mission Control)

A Tauri desktop app that (1) manages multiple repos/projects, (2) launches/monitors many Glia Fab
“runs” + interactive terminal sessions, and (3) indexes + renders results (reports/renders/`.glb`
assets/Godot web builds) inside the app, reusing the existing Three.js viewer
(`fab/outora-library/viewer/index.html`) as a first-class “Asset Preview/Play” surface.

## Core Architecture

- **Frontend (Web UI)**: React+TS with a dockable layout: Projects / Runs / Terminals / Assets / Settings.
  - Terminal UI: xterm.js panes (tabs + split)
  - Asset UI: embedded viewer (iframe) + run artifact explorer + report viewers
- **Backend (Tauri/Rust)**: services exposed via Tauri commands + events
  1. Project registry: tracks repo roots, labels, detected capabilities (`dev-kernel/`, `fab/`, etc.)
  2. Session manager (PTY): interactive shells + command sessions; streams output; resize/input/kill
  3. Job runner: structured “run templates” (`fab-gate`, `fab-render`, `fab-godot`, `dev-kernel verify`)
  4. Artifact indexer: filesystem watcher that catalogs outputs and emits UI events
  5. Local content server: serves viewer + artifacts over `http://127.0.0.1:<ephemeral>`

## Key Data Contracts

- **Runs layout**: per project, write/collect into `.glia-fab/runs/<run_id>/…`
- **Artifact types** (indexer recognizes by path/signature):
  - `manifest.json` / gate reports (Fab, Godot)
  - renders (`.png/.jpg`) and render folders
  - exports (`.glb`)
  - Godot web builds (`index.html` + `.pck/.wasm`)
- **Viewer contract**:
  - Serve `fab/outora-library/viewer/` over HTTP so ES modules + Godot exports can load.

## Phased Plan

1. **Phase A — Foundations**: scaffold app + persistent state + local server
2. **Phase B — Terminals**: PTY sessions + xterm.js UI
3. **Phase C — Jobs/Templates**: parameterized run templates; capture logs + metadata
4. **Phase D — Artifacts**: watch `.glia-fab/runs/**`, index/parse reports, surface in UI
5. **Phase E — Viewer/Play**: embed Outora viewer; wire dynamic asset selection
6. **Phase F — Polish**: dashboard, search, pinning, notifications; optional toolchain profiles UI
