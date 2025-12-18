import bpy
import math
from mathutils import Vector
import os

# Path setup
repo_root = "/Users/connor/Medica/outora-library"
setup_script = os.path.join(repo_root, "blender/setup_concrete_desk.py")
bake_script = os.path.join(repo_root, "blender/sverchok_bake.py")
layout_script = os.path.join(repo_root, "blender/sverchok_layout.py")

# 0. Run Setup
print("Running Setup...")
setup_globals = {}
exec(compile(open(setup_script).read(), setup_script, "exec"), setup_globals)
if "run" in setup_globals:
    setup_globals["run"]()
else:
    print("ERROR: run() not found in setup script")

# 1. Run Layout Update
print("Updating layout tree...")
layout_globals = {}
exec(compile(open(layout_script).read(), layout_script, "exec"), layout_globals)
if "ensure_layout_tree" in layout_globals:
    layout_globals["ensure_layout_tree"]()

# 2. Run Bake & Populate
print("Running bake and population...")
if not bpy.data.objects.get("ol_desk_concrete"):
    print("Source object 'ol_desk_concrete' not found! Cannot bake.")
else:
    bake_globals = {}
    exec(compile(open(bake_script).read(), bake_script, "exec"), bake_globals)
    if "bake_bays" in bake_globals:
        bake_globals["bake_bays"]()
    if "populate_study_props" in bake_globals:
        bake_globals["populate_study_props"]()

# 3. Verify
desk_instance = None
col = bpy.data.collections.get("OL_Furniture")
if col:
    for obj in col.objects:
        if obj.name.startswith("ol_desk_concrete") and obj.name != "ol_desk_concrete":
            desk_instance = obj
            break

if desk_instance:
    print(f"Found desk instance: {desk_instance.name} at {desk_instance.location}")
    print(f"Dims: {desk_instance.dimensions}")

    # Camera
    cam = bpy.data.objects.get("Camera")
    if not cam:
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    target = desk_instance.location
    cam.location = target + Vector((1.5, -2.5, 1.8))
    direction = target - cam.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()

    props = []
    prop_col = bpy.data.collections.get("OL_PodProps")
    if prop_col:
        for obj in prop_col.objects:
            if (obj.location - desk_instance.location).length < 1.5:
                props.append(obj.name)
    print(f"Props found near desk: {len(props)}")
else:
    print("No desk instances found.")
