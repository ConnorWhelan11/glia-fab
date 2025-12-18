"""
Create Car Lookdev Scene v001

Run this script inside Blender to create the standardized lookdev scene
for car asset evaluation.

Usage:
    blender --background --python create_car_lookdev_v001.py -- --output ../scenes/car_lookdev_v001.blend

Or from Blender's scripting interface.
"""

import argparse
import math
import sys
from pathlib import Path

import bpy


def clear_scene():
    """Clear all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Clear orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        if block.users == 0:
            bpy.data.lights.remove(block)


def setup_world():
    """Setup world with HDRI-ready node setup."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world

    # Enable nodes (compatible with Blender 4.x and 5.x)
    if hasattr(world, "use_nodes"):
        world.use_nodes = True

    # Ensure node tree exists
    if world.node_tree is None:
        return  # Blender will create default nodes

    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing nodes
    nodes.clear()

    # Create nodes
    node_bg = nodes.new(type="ShaderNodeBackground")
    node_bg.location = (0, 0)
    node_bg.inputs["Color"].default_value = (0.05, 0.05, 0.08, 1.0)  # Dark blue-gray
    node_bg.inputs["Strength"].default_value = 1.0

    node_output = nodes.new(type="ShaderNodeOutputWorld")
    node_output.location = (200, 0)

    # Link
    links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

    # Add environment texture node (disconnected, ready for HDRI)
    node_env = nodes.new(type="ShaderNodeTexEnvironment")
    node_env.location = (-300, 0)
    node_env.label = "HDRI (connect to Background)"

    # Add mapping for rotation control
    node_mapping = nodes.new(type="ShaderNodeMapping")
    node_mapping.location = (-500, 0)
    node_mapping.label = "HDRI Rotation"

    node_texcoord = nodes.new(type="ShaderNodeTexCoord")
    node_texcoord.location = (-700, 0)

    # Link environment setup (ready but not connected to output)
    links.new(node_texcoord.outputs["Generated"], node_mapping.inputs["Vector"])
    links.new(node_mapping.outputs["Vector"], node_env.inputs["Vector"])


def create_ground_plane():
    """Create ground plane with shadow catcher material."""
    # Create plane
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground_Plane"

    # Create material
    mat = bpy.data.materials.new(name="Ground_Material")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True

    if mat.node_tree:
        nodes = mat.node_tree.nodes
        # Setup neutral gray with slight roughness
        principled = nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.4, 0.4, 0.4, 1.0)
            principled.inputs["Roughness"].default_value = 0.85
            principled.inputs["Metallic"].default_value = 0.0

    ground.data.materials.append(mat)

    # Shadow catcher settings (compatible with Blender 4.x and 5.x)
    if hasattr(ground, "is_shadow_catcher"):
        ground.is_shadow_catcher = True
    # In newer Blender, shadow catcher is set via visibility settings
    if hasattr(ground, "visible_shadow") and hasattr(ground, "visible_camera"):
        ground.visible_shadow = True

    return ground


def create_backdrop():
    """Create curved backdrop for studio look."""
    # Create curved backdrop using bezier curve
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 12, 5))
    backdrop = bpy.context.object
    backdrop.name = "Backdrop"
    backdrop.rotation_euler = (math.radians(90), 0, 0)

    # Create material
    mat = bpy.data.materials.new(name="Backdrop_Material")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True

    if mat.node_tree:
        nodes = mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.3, 0.3, 0.32, 1.0)
            principled.inputs["Roughness"].default_value = 0.9

    backdrop.data.materials.append(mat)

    return backdrop


def create_three_point_lighting():
    """Create standard three-point lighting setup."""
    lights = []

    # Key Light (main light, camera left, high)
    bpy.ops.object.light_add(type="AREA", location=(4, -4, 5))
    key = bpy.context.object
    key.name = "Key_Light"
    key.data.energy = 800
    key.data.size = 3
    key.data.color = (1.0, 0.98, 0.95)  # Slightly warm

    # Point at origin
    direction = key.location.copy()
    direction.negate()
    key.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    lights.append(key)

    # Fill Light (camera right, lower intensity)
    bpy.ops.object.light_add(type="AREA", location=(-4, -3, 3))
    fill = bpy.context.object
    fill.name = "Fill_Light"
    fill.data.energy = 300
    fill.data.size = 4
    fill.data.color = (0.95, 0.97, 1.0)  # Slightly cool

    direction = fill.location.copy()
    direction.negate()
    fill.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    lights.append(fill)

    # Rim/Back Light (behind subject)
    bpy.ops.object.light_add(type="AREA", location=(0, 5, 4))
    rim = bpy.context.object
    rim.name = "Rim_Light"
    rim.data.energy = 500
    rim.data.size = 2
    rim.data.color = (1.0, 1.0, 1.0)

    direction = rim.location.copy()
    direction.z = 0.5
    direction.negate()
    rim.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    lights.append(rim)

    return lights


def create_cameras():
    """Create camera rig for canonical views."""
    cameras = {}

    # Camera settings
    focal_length = 50
    sensor_width = 36
    distance = 6.0
    look_at = (0, 0, 0.5)  # Slightly above ground

    camera_specs = [
        # (name, azimuth_deg, elevation_deg, distance_factor, focal_mm)
        ("cam_front_3q", 45, 15, 1.0, 50),
        ("cam_rear_3q", 225, 15, 1.0, 50),
        ("cam_side_left", 90, 5, 1.1, 50),
        ("cam_front", 0, 10, 1.0, 50),
        ("cam_top", 0, 75, 1.2, 35),
        ("cam_close_wheel_front", 60, 10, 0.6, 85),
    ]

    for name, azimuth, elevation, dist_factor, focal in camera_specs:
        # Create camera
        cam_data = bpy.data.cameras.new(name=name)
        cam_data.lens = focal
        cam_data.sensor_width = sensor_width

        cam_obj = bpy.data.objects.new(name, cam_data)
        bpy.context.collection.objects.link(cam_obj)

        # Position camera
        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        d = distance * dist_factor

        cam_obj.location.x = math.sin(az_rad) * math.cos(el_rad) * d
        cam_obj.location.y = -math.cos(az_rad) * math.cos(el_rad) * d
        cam_obj.location.z = math.sin(el_rad) * d + look_at[2]

        # Point at look_at target
        from mathutils import Vector

        target = Vector(look_at)
        direction = target - cam_obj.location
        rot_quat = direction.to_track_quat("-Z", "Y")
        cam_obj.rotation_euler = rot_quat.to_euler()

        cameras[name] = cam_obj

    # Set default camera
    bpy.context.scene.camera = cameras["cam_front_3q"]

    return cameras


def create_asset_collection():
    """Create collection for imported assets."""
    asset_col = bpy.data.collections.new("Asset")
    bpy.context.scene.collection.children.link(asset_col)
    return asset_col


def setup_render_settings():
    """Configure render settings for determinism."""
    scene = bpy.context.scene

    # Engine
    scene.render.engine = "CYCLES"

    # Device (CPU for determinism)
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "NONE"
    except Exception:
        pass
    scene.cycles.device = "CPU"

    # Resolution
    scene.render.resolution_x = 768
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100

    # Samples
    scene.cycles.samples = 128
    scene.cycles.seed = 1337
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False

    # Output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    scene.render.image_settings.color_mode = "RGBA"

    # Color management
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    # Film
    scene.render.film_transparent = False


def setup_view_layers():
    """Setup view layers for beauty and clay renders."""
    scene = bpy.context.scene

    # Beauty layer (default)
    beauty_layer = scene.view_layers[0]
    beauty_layer.name = "beauty"
    if hasattr(beauty_layer, "use_pass_combined"):
        beauty_layer.use_pass_combined = True

    # Clay layer (material override)
    clay_layer = scene.view_layers.new("clay")
    if hasattr(clay_layer, "use_pass_combined"):
        clay_layer.use_pass_combined = True

    # Create clay override material
    clay_mat = bpy.data.materials.new(name="Clay_Override")
    if hasattr(clay_mat, "use_nodes"):
        clay_mat.use_nodes = True

    if clay_mat.node_tree:
        nodes = clay_mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
            principled.inputs["Roughness"].default_value = 0.7
            principled.inputs["Metallic"].default_value = 0.0

    # Note: Material override would need to be set per render
    # Store reference for later use
    clay_mat["is_clay_override"] = True


def organize_collections():
    """Organize objects into collections."""
    scene_col = bpy.context.scene.collection

    # Create collections
    lighting_col = bpy.data.collections.new("Lighting")
    scene_col.children.link(lighting_col)

    environment_col = bpy.data.collections.new("Environment")
    scene_col.children.link(environment_col)

    cameras_col = bpy.data.collections.new("Cameras")
    scene_col.children.link(cameras_col)

    # Move objects to collections
    for obj in list(scene_col.objects):
        if obj.type == "LIGHT":
            scene_col.objects.unlink(obj)
            lighting_col.objects.link(obj)
        elif obj.type == "CAMERA":
            scene_col.objects.unlink(obj)
            cameras_col.objects.link(obj)
        elif obj.type == "MESH" and "Ground" in obj.name or "Backdrop" in obj.name:
            scene_col.objects.unlink(obj)
            environment_col.objects.link(obj)


def create_lookdev_scene(output_path: str = None):
    """Create the complete lookdev scene."""
    print("Creating car lookdev scene v001...")

    # Clear existing scene
    clear_scene()

    # Setup components
    print("  Setting up world...")
    setup_world()

    print("  Creating environment...")
    create_ground_plane()
    create_backdrop()

    print("  Creating lighting...")
    create_three_point_lighting()

    print("  Creating cameras...")
    create_cameras()

    print("  Creating asset collection...")
    create_asset_collection()

    print("  Configuring render settings...")
    setup_render_settings()

    print("  Setting up view layers...")
    setup_view_layers()

    print("  Organizing collections...")
    organize_collections()

    # Save if output path provided
    if output_path:
        print(f"  Saving to: {output_path}")
        bpy.ops.wm.save_as_mainfile(filepath=output_path)

    print("Done!")


def main():
    # Parse arguments after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Create car lookdev scene")
    parser.add_argument("--output", "-o", help="Output .blend file path")
    args = parser.parse_args(argv)

    output_path = args.output
    if output_path:
        output_path = str(Path(output_path).absolute())

    create_lookdev_scene(output_path)


if __name__ == "__main__":
    main()
