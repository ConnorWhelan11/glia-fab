# Fab Blender→Godot Game Contract (v0)

This contract defines how Blender-authored scenes (exported as glTF 2.0 `.glb`) encode
enough metadata for a minimal, testable Godot scene (spawn + collisions + triggers).

This is intentionally simple and name-driven so it survives round-trips and works with
headless export pipelines.

## Coordinate system & scale

- Author in Blender using **metric** scale: **1 Blender unit = 1 meter**.
- Blender is Z-up; glTF is Y-up. The Blender glTF exporter performs the axis conversion.
- Apply transforms deterministically on export (prefer exporter `export_apply=true`).

## Required markers (playable)

For a scene to be considered “playable” by the template:

1. **Exactly 1 player spawn** marker.
2. **≥ 1 collider** marker mesh (static collision).

Everything else is optional in v0 (triggers, interactables, nav, etc).

## Naming conventions (supported aliases)

The loader recognizes both the “Fab” uppercase names and Outora’s `ol_` prefix style.

### Player spawn

Use an Empty or any object named:

- `SPAWN_PLAYER` (or `SPAWN_PLAYER_*`)
- `ol_spawn_player` (or `ol_spawn_player_*`)

The object transform defines the player start transform.

### Static colliders

Use simplified mesh objects named:

- `COLLIDER_*`
- `ol_collider_*`

These meshes are converted into `StaticBody3D` + `CollisionShape3D` (trimesh) at runtime
by the template loader.

### Triggers (optional)

Mesh objects named:

- `TRIGGER_*`
- `ol_trigger_*`

These are converted into `Area3D` triggers at runtime.

### Interactables (optional)

Node names:

- `INTERACT_*`
- `ol_interact_*`

v0 treats these as “tagged nodes” only; the gameplay layer can decide how to use them.

## Custom properties (optional, future-proof)

If you need more than names, add Blender custom properties (ID properties) on objects.
When exported with glTF “extras”, these can be read from the glTF node metadata.

Recommended keys (all optional):

- `fab_role`: `spawn_player` | `collider` | `trigger` | `interact`
- `fab_id`: stable string identifier (e.g. `door_main`)
- `fab_trigger_kind`: e.g. `enter_area`, `pickup`, `teleport`

## Export rules (Blender)

- Prefer exporting **`.glb`** (binary glTF) for Godot.
- Include markers in the exported selection/collection.
- Collider meshes should be low-poly and closed when possible.
- Avoid negative scale; apply transforms before export.

The Outora Library includes a reference exporter/validator:

- `fab/outora-library/blender/export_fab_game_glb.py`

