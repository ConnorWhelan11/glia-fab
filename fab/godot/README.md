# Fab Godot Template

This folder contains a minimal Godot 4 template project intended to turn Blender-authored
`.glb` scenes into a basic, testable first-person “walkaround”.

## Contract

See `fab/godot/CONTRACT.md` for the Blender→Godot metadata contract (spawn/colliders).

## Template layout

- `fab/godot/template/`: Godot project (text-only; no bundled assets).
  - `assets/`: place the exported level GLB as `assets/level.glb` (or change the path in
    `scripts/FabLevelLoader.gd`).

## Quick start (local)

1. Export a scene from Blender as `.glb` using the contract markers.
2. Copy it to `fab/godot/template/assets/level.glb`.
3. Open `fab/godot/template/` in Godot 4 and run the project.

## Build a Web export (via dev-kernel)

If you have Godot installed, you can build a Web export (and emit a `godot_report.json`)
with:

- If `dev-kernel` is installed: `fab-godot --asset path/to/level.glb --config godot_integration_v001 --out /tmp/fab-game`
- Or from source: `cd dev-kernel && PYTHONPATH=src python -m dev_kernel.fab.godot --asset ../path/to/level.glb --config godot_integration_v001 --out /tmp/fab-game`

To place the build where the Three.js viewer can “Play” it:

- If `dev-kernel` is installed: `fab-godot --asset fab/outora-library/viewer/assets/exports/gothic_library_full.glb --config godot_integration_v001 --out fab/outora-library/viewer/assets/games/gothic_library_full`
- Or from source: `cd dev-kernel && PYTHONPATH=src python -m dev_kernel.fab.godot --asset ../fab/outora-library/viewer/assets/exports/gothic_library_full.glb --config godot_integration_v001 --out ../fab/outora-library/viewer/assets/games/gothic_library_full`

## Web export preset

`fab/godot/template/export_presets.cfg` includes a starter “Web” preset meant for CI
automation. You may still need to configure export templates locally in the Godot editor.
