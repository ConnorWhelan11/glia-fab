import bpy
import math

def fix_skybox():
    obj_paper = bpy.data.objects.get("Wallpaper")
    if not obj_paper:
        print("Wallpaper object not found!")
        return

    # Ensure in OL_ENVIRONMENT
    coll_env = bpy.data.collections.get("OL_ENVIRONMENT")
    
    # 1. Center and Rotate Initial Piece
    # Outora Window is +Y. We want the nice part of space visible there.
    # Currently it seems arbitrary.
    # Let's assume we want the curve to wrap around the +Y axis.
    
    obj_paper.location = (0,0,0)
    
    # Dimensions are ~200m wide. Scene is ~20m.
    # We want it FAR away.
    # Scale 100x was probably too big if the base unit was already meters.
    # The dimensions (200, 119, 100) are actually reasonable (200m wide).
    # Let's keep scale or adjust.
    
    # Create 3 duplicates rotated 90, 180, 270 degrees to close the loop?
    # It's a curved strip, maybe 90 degrees arc?
    # From screenshot it looks like a quarter circle or so.
    # Let's try 4 copies.
    
    # Rename original
    obj_paper.name = "ol_skybox_0"
    
    for i in range(1, 4):
        name = f"ol_skybox_{i}"
        if bpy.data.objects.get(name):
             bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
             
        dup = obj_paper.copy()
        dup.data = obj_paper.data # Link mesh
        dup.name = name
        
        # Rotate around Z
        # 90 degrees = pi/2
        dup.rotation_euler.z += (i * math.pi / 2)
        
        coll_env.objects.link(dup)
        
    # Adjust height
    # It might be too low/high. Move all up slightly?
    for i in range(4):
        o = bpy.data.objects.get(f"ol_skybox_{i}")
        if o:
            o.location.z = -20 # Lower slightly so we see more "sky"
            
    print("Skybox ring created.")

def setup_lighting():
    coll_env = bpy.data.collections.get("OL_ENVIRONMENT")
    
    # 1. Sun Light (Moon/Planet Light)
    # Directional light coming from +Y (Window)
    light_data = bpy.data.lights.new(name="ol_light_sun", type='SUN')
    light_data.energy = 2.0 # Strength
    light_data.color = (0.8, 0.9, 1.0) # Cool blue-white
    light_data.angle = 0.1 # Soft shadows (approx 5 deg)
    
    obj_light = bpy.data.objects.new(name="ol_sun", object_data=light_data)
    coll_env.objects.link(obj_light)
    
    # Position irrelevant for SUN, but good for visualization
    obj_light.location = (0, 20, 20)
    # Rotation: Pointing towards origin from +Y +Z
    # Euler X ~ 45 deg? 
    # Pointing -Y, -Z.
    obj_light.rotation_euler = (math.radians(45), 0, math.radians(180)) 
    
    # 2. Practical Lights (Interior Warmth)
    coll_final = bpy.data.collections.get("OL_SCENE_FINAL")
    
    # A. Lamp Light (Point)
    # We already have an emissive material, but let's add a real light for casting light.
    # Find the lamp instance location?
    # It's hard to track the exact instance location in Python without iterating graph.
    # For MVP, let's just place a Point Light near the Desk.
    # Hero Desk Proxy was at (0, 1.2, 0.75/2). Real desk is similar.
    # Lamp is at (-0.6, 0.3, 0.75) relative to desk?
    # Desk ~ (0, 1.2, 0)
    # Lamp ~ (-0.6, 1.5, 0.8)
    
    lamp_data = bpy.data.lights.new(name="ol_light_lamp", type='POINT')
    lamp_data.energy = 50.0 # Watts
    lamp_data.color = (1.0, 0.6, 0.4) # Warm Orange
    lamp_data.shadow_soft_size = 0.1
    
    obj_lamp_light = bpy.data.objects.new(name="ol_practical_desk", object_data=lamp_data)
    coll_final.objects.link(obj_lamp_light)
    obj_lamp_light.location = (-0.6, 1.5, 1.2) # Slightly above table
    
    # B. Ambient Fill (Area Light - Ceiling)
    # Soft warm fill from top
    fill_data = bpy.data.lights.new(name="ol_light_fill", type='AREA')
    fill_data.energy = 100.0
    fill_data.color = (1.0, 0.8, 0.7)
    fill_data.shape = 'DISK'
    fill_data.size = 5.0
    
    obj_fill = bpy.data.objects.new(name="ol_fill_ceiling", object_data=fill_data)
    coll_final.objects.link(obj_fill)
    obj_fill.location = (0, 0, 4.0) # Ceiling height
    obj_fill.rotation_euler = (0, 0, 0) # Pointing down (-Z) is default for Area? 
    # Blender Area Light default points -Z.
    
    print("Lights setup.")

if __name__ == "__main__":
    fix_skybox()
    setup_lighting()

