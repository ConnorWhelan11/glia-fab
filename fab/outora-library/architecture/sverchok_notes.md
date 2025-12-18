# Sverchok Add-on Notes (local inspection, usable bits)

Context: Sverchok is installed and can be enabled to procedurally generate/bake geometry for our Outora library. These notes capture what’s available and how to hook it up in scripts.

## What we found in this install
- Add-on present but not auto-enabled; enabling via Python works:
  ```python
  import addon_utils
  addon_utils.enable('sverchok', default_set=True, persistent=True)
  ```
- Node tree types registered:
  - `SverchCustomTree` (bl_idname: `SverchCustomTreeType`)
  - `SvGroupTree` (node-group variant)
  - Standard Blender trees: ShaderNodeTree, GeometryNodeTree also present.
- Scripted node available: `SvScriptNodeLite` (class `sverchok.nodes.script.script1_lite.SvScriptNodeLite`), shorthand “snl”.
  - Inputs/outputs are defined dynamically via scripts; default new node starts empty until a script is injected.
  - Supports `script_str` or loading from a Text datablock; can create sockets based on a small script.
- Viewer nodes detected (for debug/inspection):
  - `SvMeshViewer`, `SvViewerDrawMk4`, `SvPolylineViewerNode`, `SvCurveViewerNodeV28`, `SvCurveViewerDrawNode`, `SvMatrixViewer28`, `SvGeoNodesViewerNode`, `SvLightViewerNode`, `SvViewer2D`, `ViewerNodeTextMK3`.
- Node tree creation works:
  ```python
  tree = bpy.data.node_groups.new('SV_TEMP', 'SverchCustomTreeType')
  snl = tree.nodes.new('SvScriptNodeLite')
  ```
- Sverchok version not reported (returned `None`), but node classes are present and usable.


## Quick usage pattern (non-UI)
1) Enable add-on (once per session or persistently).
2) Create a Sverchok node tree: `bpy.data.node_groups.new(name, 'SverchCustomTreeType')`.
3) Add nodes by `tree.nodes.new('<NodeID>')`, e.g., `SvScriptNodeLite`, `SvMeshViewer`.
4) For `SvScriptNodeLite`, set `node.script_str` to a small Python snippet that defines inputs/outputs and assigns `node.outputs[...] = [...]` (matched to sockets). Sockets are created/updated by the script parsing phase.
5) Use viewer nodes to inspect output in the viewport; eventually bake to Blender meshes via a Python helper (e.g., read matrices/verts/faces from the node output and build Mesh datablocks).

## Relevant nodes to use for our pipeline
- `SvScriptNodeLite`: procedural generator for bay matrices, arch curves, stair runs.
- Viewer nodes (`SvMeshViewer`, `SvPolylineViewerNode`, `SvMatrixViewer28`) to preview points/curves/meshes.
- Instance helpers: we can emit matrices and then use “Instance on Points/Matrices” nodes (available in Sverchok) to place our kit meshes—these were not enumerated here, but standard Sverchok matrix → instance nodes are part of the core set.

How to use:

import importlib, sverchok_layout, sverchok_bake
importlib.reload(sverchok_layout); importlib.reload(sverchok_bake)
sverchok_layout.ensure_layout_tree()
created = sverchok_bake.bake_bays()  # collection OL_GOTHIC_LAYOUT
print(len(created))

Adjust INSTANCE_MAP in blender/sverchok_bake.py to point at your kit pieces (walls/windows/
arches) for real layouts.

## Integration plan (agreed)
- Tree name: `SV_LIB_LAYOUT`.
- Nodes: one Scripted Node Lite to emit bay-point matrices on a 6m cadence; viewer to debug.
- Feed matrices to instancing (walls/windows/arches), then bake results into `OL_GOTHIC_LAYOUT` via a helper script so the main scene isn’t dependent on live nodes.

## Repeatable workflow for study-pod assets (so adding a desk is simple)
- Intake each GLB through a prep script (e.g., `blender/setup_concrete_desk.py`): delete old attempts, join meshes, clear parents, apply transforms, set origin to bottom-center, zero location, and rename to `ol_*`. A bad pivot is the most common cause of “slabs under the floor.”
- Map the cleaned source in `INSTANCE_MAP` (`blender/sverchok_bake.py`) under the `desks` output, with any `z_offset` / `pos_offset` / `scale`. Keep chair/lamp siblings in the same list so the pod kit moves together without touching Sverchok node code.
- Use the bake harness (`blender/verify_desk_update.py` pattern) after edits: prep script → `ensure_layout_tree` → `bake_bays(purge_existing=True)` → `populate_study_props`. Clearing target collections on each bake prevents stale slabs.
- Debug checklist when instances look wrong:
  - Ensure the target collections (`OL_Furniture`, etc.) are empty before the bake; rely on `purge_existing=True`.
  - Confirm the source pivot sits at Z=0; if the GLB imported with an offset, every instance lands below the floor.
  - Run `blender/debug_sverchok.py` to verify the `desks` socket emits the expected matrix count (no zeroed entries).
  - If an asset is retired, remove it from `INSTANCE_MAP` rather than leaving hidden meshes in the scene.

## Study pod QA pocket guide
- Source objects: `ol_desk_concrete` (pivot at base, upright), `WoodenChair_01`, `desk_lamp_arm_01`; all mapped under `desks` in `blender/sverchok_bake.py`.
- Camera: `ol_cam_pod` lives in `OL_Cameras`, pointed at the first desk instance. Re-run snippet:  
  ```python
  import importlib, setup_concrete_desk, sverchok_layout, sverchok_bake
  setup_concrete_desk.run()
  sverchok_layout.ensure_layout_tree()
  outs = sverchok_bake.get_sv_outputs()
  sverchok_bake.bake_bays(purge_existing=True, outputs=outs)
  import bpy
  from mathutils import Vector
  desk = next(o for o in bpy.data.objects if o.name.startswith('ol_desk_concrete.'))
  cam = bpy.data.objects.get('ol_cam_pod') or bpy.data.objects.new('ol_cam_pod', bpy.data.cameras.new('ol_cam_pod'))
  cam.location = desk.location + Vector((2.2, -3.0, 1.5))
  cam.rotation_euler = (desk.location - cam.location).to_track_quat('-Z', 'Y').to_euler()
  bpy.context.scene.camera = cam
  ```
- Screenshot via MCP: `mcp_blender_get_viewport_screenshot(max_size=1200)` after setting `ol_cam_pod` as the active scene camera.
- Ground-truth expectations: desks upright on floor facing +Y; chair sits behind desk (`pos_offset=(0,-0.8,0)`); lamp sits on top (`z_offset=0.75`).

## Caveats
- Some Sverchok classes don’t appear in `bpy.types` under “Sv*Node” search until the add-on is enabled.
- `SverchCustomTree` lives in `sverchok.node_tree`; access via `bpy.data.node_groups.new(..., 'SverchCustomTreeType')`.
- Version string not exposed; rely on node presence rather than version checks.
