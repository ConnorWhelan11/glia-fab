import bpy

def cleanup_skybox():
    # Remove the Bedroom Geometry
    obj_room = bpy.data.objects.get("Room.001")
    if obj_room:
        bpy.data.objects.remove(obj_room, do_unlink=True)
        print("Removed Room.001 (Bedroom geometry)")
        
    # Check the Wallpaper object (Space Background)
    obj_paper = bpy.data.objects.get("Wallpaper")
    if obj_paper:
        print("Found Wallpaper object (Space Background)")
        
        # Ensure it is in the OL_ENVIRONMENT collection
        coll_env = bpy.data.collections.get("OL_ENVIRONMENT")
        if coll_env and obj_paper.name not in coll_env.objects:
            coll_env.objects.link(obj_paper)
            
        # Scale and Position
        # It was scaled 100x before.
        # Let's make sure it's centered and huge.
        # If it's a curved plane, we might need to rotate it to face the window.
        # Outora Window is at +Y.
        # Let's ensure it's visible.
        
        # If it's just a plane, we might want to convert its texture to a World Shader (Environment Texture) 
        # instead of using the mesh, so it wraps perfectly.
        # But let's stick to the mesh for a moment if the user specifically wanted this "model".
        
        # Optimization: If it's a mesh, ensure Backface Culling is OFF so we see it from inside if it's a sphere,
        # or ON if it's outside. 
        # Usually skyboxes are inward facing spheres.
        
        pass

if __name__ == "__main__":
    cleanup_skybox()

