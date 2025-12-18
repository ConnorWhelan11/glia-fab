Outora Library

This folder contains the Outora Library asset pipeline: Blender scenes, automation
scripts, exported assets, and a small Python helper package.

Layout
- `blender/`: Blender automation scripts and working `.blend` files (run these via Blender).
- `assets/`: Source meshes/textures.
- `export/`: Generated exports (GLB/FBX, atlases, etc).
- `renders/`: Preview renders for review.
- `src/outora_library/`: Lightweight Python helpers (path utilities, shared logic).

Quick start
1) Create a venv and install dev deps:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -e .[dev]`

2) Run a Blender script headless (example):
   - macOS: `/Applications/Blender.app/Contents/MacOS/Blender blender/outora_library_v0.4.0.blend --background --python blender/run_pipeline.py`
   - Other: `blender blender/outora_library_v0.4.0.blend --background --python blender/run_pipeline.py`

Lint/tests
- `ruff check .`
- `black .`
- `pytest`

Notes
- The Python package is intended for helpers; most functionality lives in Blender
  scripts and relies on `bpy`.
- Avoid committing large `.blend1` backups unless they’re intentional releases.
