import bpy
import os

def import_skybox():
    # Path to the GLTF
    # Using absolute path based on user context or relative if possible. 
    # User provided: assets/room1107/source/20211107_skybox/20211107_skybox.gltf
    
    base_path = bpy.path.abspath("//") # blender/ directory if opened from there?
    # actually .blend is in blender/ folder.
    # project root is one up.
    
    # Let's construct absolute path to be safe, assuming standard layout
    # We know workspace root is /Users/connor/Medica/outora-library
    
    gltf_path = "/Users/connor/Medica/outora-library/assets/room1107/source/20211107_skybox/20211107_skybox.gltf"
    
    if not os.path.exists(gltf_path):
        print(f"ERROR: Skybox file not found at {gltf_path}")
        return

    # Import
    bpy.ops.import_scene.gltf(filepath=gltf_path)
    
    # The imported objects are selected.
    selected_objects = bpy.context.selected_objects
    
    # Create Collection
    coll_env = bpy.data.collections.get("OL_ENVIRONMENT")
    if not coll_env:
        coll_env = bpy.data.collections.new("OL_ENVIRONMENT")
        bpy.context.scene.collection.children.link(coll_env)
    
    # Move objects and Setup
    for obj in selected_objects:
        # Link to Env Collection
        if obj.name not in coll_env.objects:
            coll_env.objects.link(obj)
            
        # Unlink from others
        cols_to_unlink = [c for c in obj.users_collection if c != coll_env]
        for c in cols_to_unlink:
            c.objects.unlink(obj)
            
        # Scale Up
        # Room is ~20m wide. Let's make skybox huge.
        obj.scale = (100, 100, 100)
        
        # Location 0,0,0
        obj.location = (0,0,0)
        
        # Ensure Emission
        # The GLTF likely has a material. We want it to be unlit/emission so it acts like a sky.
        if obj.data and obj.data.materials:
            mat = obj.data.materials[0]
            if mat.use_nodes:
                bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if bsdf:
                    # If texture is connected to Base Color, connect it to Emission too
                    if bsdf.inputs['Base Color'].is_linked:
                        link = bsdf.inputs['Base Color'].links[0]
                        # Connect to Emission Color
                        mat.node_tree.links.new(link.from_socket, bsdf.inputs['Emission Color'])
                        # Set Strength
                        bsdf.inputs['Emission Strength'].default_value = 1.0
                        # Turn off Specular/Roughness to avoid reflections of sun on the sky itself
                        bsdf.inputs['Roughness'].default_value = 1.0
                        bsdf.inputs['Specular IOR Level'].default_value = 0.0 # Specular in 4.0 is different, check version. 
                        # In 3.6/4.0+ usually Specular is separate.
                        
    # Disable World Background (make it black so we only see skybox)
    if bpy.context.scene.world:
        world = bpy.context.scene.world
        if world.use_nodes:
            bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
            if bg:
                bg.inputs['Color'].default_value = (0,0,0,1)
                bg.inputs['Strength'].default_value = 0.0

if __name__ == "__main__":
    import_skybox()

