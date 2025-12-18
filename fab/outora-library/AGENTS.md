# Repository Guidelines

This repository holds the Outora Library asset pipeline: Python helpers, Blender automation, and exportable assets. Use this guide to keep contributions consistent and reproducible.

## Project Structure & Module Organization

- `architecture/` Architecture design docs and sketches
- `src/outora_library/`: Python package entry point; keep reusable code here before adding scripts.
- `blender/`: Automation (e.g., `integrate_assets.py`, `apply_style.py`) and the working `.blend`; run these via Blender, not straight with CPython.
- `assets/`: Source meshes and textures; mirror any new subfolders in `licenses/` for attribution.
- `export/`: Generated GLB/FBX or baked outputs ready for downstream use.

## Environment Setup, Build, and Test

- Python 3.10+. Create a venv (`python -m venv .venv && source .venv/bin/activate`), then install dev tools: `pip install -e .[dev]`.
- Lint/format: `ruff check .` and `black .` (line length 88).
- Tests: `pytest`; prefer mocking `bpy` when testing Blender-facing logic.
- Blender automation (headless example): `blender blender/outora_library.blend --background --python blender/integrate_assets.py`; copy the blend before experiments.
- Build a distributable wheel: `python -m build` (outputs in `dist/`).

## Coding Style & Naming Conventions

- Follow Black formatting and Ruff lint rules; keep Python in `src/` and Blender-only code in `blender/`.
- Functions/variables use `snake_case`; classes `CapWords`; constants `UPPER_CASE`.
- Blender scene objects and custom materials should use the `ol_` prefix plus a clear role (e.g., `ol_floor`, `ol_mat_wall`).
- Favor project-relative paths via `Path(__file__).parent` instead of hard-coded absolute paths.

## Testing Guidelines

- Place tests under `tests/` using `test_*.py`; co-locate fixtures near the behaviors they cover.
- Cover new logic; mock assets/Blender or use temporary copies to avoid mutating shared files.
- Re-run `pytest` before opening a PR; regenerate coverage when pipelines change and keep reports local.

## Commit & Pull Request Guidelines

- Commits: short, imperative subjects (`Add lighting setup helper`, `Fix asset path resolution`); keep related changes together.
- PRs: note purpose/approach, commands run (lint/tests), and Blender screenshots/GIFs when visuals change. Link issues and call out asset licenses or new dependencies.
- Avoid committing large binaries or `.blend1` backups unless intentional releases; prefer reproducible scripts and documented export steps.

# Blender MCP Tools Usage

You have access to powerful Blender integration tools. Use them proactively to validate your work.

## Validation

- After writing or modifying a Blender Python script (in `blender/`), **ALWAYS** attempt to execute it or a test harness.
- Use `mcp_blender_execute_blender_code` to run snippets.
  - Example: `import my_script; my_script.run()`

## Visual Confirmation

- If your task involves scene layout, materials, or geometry, use `mcp_blender_get_viewport_screenshot` to inspect the result.
- Verify that the visual output matches the design intent.

## Object Inspection

- Use `mcp_blender_get_object_info` to check specific object properties (location, dimensions, materials).
- Use `mcp_blender_get_scene_info` to verify object hierarchy and existence.

## Asset Management

- Use Polyhaven/Sketchfab/Hyper3D tools (`mcp_blender_search_*`, `mcp_blender_download_*`) **only when explicitly requested** for new assets.
- Focus on verifying _existing_ or _generated_ assets first.

# Core Workflow

Adhere to the following cycle for all tasks to ensure high quality and verifiable changes.

## 1. Analysis

- Understand the goal.
- Check existing code and documentation.
- Plan the approach before writing code.

## 2. Implementation

- Make changes in small, verifiable steps.
- Focus on one logical change at a time.

## 3. Verification (CRITICAL)

- **Do NOT assume code works; prove it.**
- Use **Blender MCP tools** to validate changes immediately.
- If a script is modified, run it using `mcp_blender_execute_blender_code`.
- If visual assets change, take a screenshot using `mcp_blender_get_viewport_screenshot`.

## 4. Review

- Check for regressions.
- Verify linter errors are resolved.
- Ensure adherence to style guides (Python & Blender).

# Sverchok & Procedural Generation

We use the Sverchok add-on for procedural geometry.

## Setup

- Sverchok may not be auto-enabled. Use this snippet if needed:
  ```python
  import addon_utils
  addon_utils.enable('sverchok', default_set=True, persistent=True)
  ```

## Node Trees

- Create trees using `bpy.data.node_groups.new(name, 'SverchCustomTreeType')`.
- Standard trees like `SvGroupTree` are also available.

## Scripted Nodes (`SvScriptNodeLite`)

- This is our primary generator for logic.
- Inject logic via `node.script_str`.
- Use standard Python math/lists within the script node context.
- Define inputs and outputs dynamically in the script string.

## Baking

- **Do not rely on live nodes for the final scene.**
- Use a baking script (e.g., `sverchok_bake.py`) to convert node output into standard Blender meshes (`bpy.data.meshes`).
- Map generated matrices to library assets (walls, arches) via instance mapping.
- Ensure generated objects are added to the correct `ol_*` collection.

# Mega Library Design Rules

## Architectural Vocabulary

- **Nave / Transept**: Cross-shaped primary axes, 8m wide.
- **Bay Rhythm**: Repeat structural bays every ~6m.
- **Levels**:
  - Ground Plane: 0m
  - Mezzanine Deck: +5m (Slab thickness ~0.4-0.6m)
  - Upper Cornice: ~9-10m
- **Oculus**: Circular opening above the crossing.

## Asset Mapping (Gothic Kit)

- **Arches**: `GIK_Arch1` (Scale 2.2-2.6, Crest ~8-9m)
- **Balustrades**: `GIK_LongStair1` rail segments + `GIK_UpperWall.001`
- **Walls/Buttresses**: `Wall2`, `Plane.006`, `Cube.006`
- **Windows**: `GIK_Window`, `MinWindow`
- **Stairs**: `GIK_LongStair1` (Grand), `GIK_CornerStair1`
- **Statues**: `Statue1`, `Statue2` on plinths

## Material Intent

- **Stone**: Warm limestone (`ol_mat_gothic_stone`)
- **Wood**: Dark walnut for shelves/rails
- **Glass**: Emissive stained panels (Nebula hues), Frosted clerestory
- **Metal**: Aged brass accents

## Outora Flavor

- Cosmic skybox visible through oculus.
- "Knowledge Cores": Softly glowing vertical columns.
- Each section owned by a student (study pods).
