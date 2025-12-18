import bpy
import os
import math
from mathutils import Vector, Matrix


def run():
    """Import the concrete desk GLB, normalize pivot/orientation, and register as ol_desk_concrete."""
    # Clean up previous attempts
    for obj in bpy.data.objects:
        if (
            obj.name == "ol_desk_concrete"
            or "beton" in obj.name
            or "Sketchfab" in obj.name
        ):
            obj.select_set(True)
        else:
            obj.select_set(False)
    bpy.ops.object.delete()

    glb_path = "/Users/connor/Medica/outora-library/blender/concrete_table_desk.glb"
    if not os.path.exists(glb_path):
        print(f"GLB not found at {glb_path}")
        return

    # Import GLB
    bpy.ops.import_scene.gltf(filepath=glb_path)

    imported = bpy.context.selected_objects
    meshes = [o for o in imported if o.type == "MESH"]

    if not meshes:
        print("No meshes found in GLB")
        return

    # Join
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    desk = meshes[0]
    desk.name = "ol_desk_concrete"

    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

    # Remove empties
    for obj in imported:
        if obj != desk and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Normalize orientation/scale if import came in sideways
    dims = desk.dimensions
    print(f"Imported dims: {dims}")
    if dims.y < 0.2 and dims.z > dims.y:  # flat on its side
        print("Desk looks sideways; rotating X 90 deg to stand upright")
        desk.rotation_euler.x = math.radians(90)
        bpy.ops.object.transform_apply(rotation=True)

    def recenter_to_base(obj):
        """Shift mesh so pivot is at min Z and centered in X/Y."""
        xs = [v.co.x for v in obj.data.vertices]
        ys = [v.co.y for v in obj.data.vertices]
        zs = [v.co.z for v in obj.data.vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        mid_x = (min_x + max_x) / 2
        mid_y = (min_y + max_y) / 2
        translate = Matrix.Translation((-mid_x, -mid_y, -min_z))
        obj.data.transform(translate)
        obj.data.update()
        return max_z - min_z

    # Center pivot to bottom before scaling
    height = recenter_to_base(desk)

    # Rotate mesh to stand upright (desk top horizontal) if it came in sideways
    # Rotate mesh -90 deg around X to lay tabletop flat (flipped from previous 90 deg)
    desk.data.transform(Matrix.Rotation(math.radians(-90), 4, "X"))
    desk.data.update()
    recenter_to_base(desk)

    # Optional gentle up-scale so it reads as a desk inside a 6m bay rhythm
    TARGET_HEIGHT = 0.75
    current_height = height if height > 1e-4 else 0.6
    scale_factor = TARGET_HEIGHT / current_height
    desk.scale = (scale_factor, scale_factor, scale_factor)
    bpy.ops.object.transform_apply(scale=True)

    # Recenter again after scaling to guarantee min_z = 0
    recenter_to_base(desk)

    # Ensure it lives in the OL_Assets collection only (so it doesn't get purged by bake)
    target_col = bpy.data.collections.get("OL_Assets")
    if not target_col:
        target_col = bpy.data.collections.new("OL_Assets")
        bpy.context.scene.collection.children.link(target_col)
    for col in list(desk.users_collection):
        col.objects.unlink(desk)
    target_col.objects.link(desk)

    desk.location = (0, 0, 0)
    corners = [Vector(c) for c in desk.bound_box]
    mins = (
        min(v.x for v in corners),
        min(v.y for v in corners),
        min(v.z for v in corners),
    )
    maxs = (
        max(v.x for v in corners),
        max(v.y for v in corners),
        max(v.z for v in corners),
    )
    print(
        f"Setup complete: {desk.name}, dims {desk.dimensions}, bounds {mins} -> {maxs}"
    )


if __name__ == "__main__":
    run()
