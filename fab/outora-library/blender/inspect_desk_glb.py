import bpy
import os


def import_desk():
    # Path to the GLB
    glb_path = os.path.abspath("blender/concrete_table_desk.glb")

    if not os.path.exists(glb_path):
        print(f"File not found: {glb_path}")
        return

    # Import GLB
    bpy.ops.import_scene.gltf(filepath=glb_path)

    # Print imported objects (selected after import)
    print("Imported objects:")
    for obj in bpy.context.selected_objects:
        print(f" - Name: {obj.name}, Type: {obj.type}, Dimensions: {obj.dimensions}")
        # Rename for consistency if it's the mesh
        if obj.type == "MESH":
            obj.name = "ol_desk_concrete"
            print(f"   -> Renamed to: {obj.name}")


import_desk()
