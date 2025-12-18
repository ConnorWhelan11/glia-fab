#!/usr/bin/env python3
"""
Render Library Preview - Canonical views of the Outora Library.

Creates a set of preview renders showcasing:
1. Grand nave view (main axis)
2. Crossing overview (bird's eye)
3. Study pod closeup
4. Transept view
5. Personal item detail

Run with:
    blender outora_library_v0.3.0.blend --background --python render_library_preview.py -- --output /tmp/library_renders
"""

import bpy
import math
import sys
import os
from pathlib import Path
from mathutils import Vector


# ============================================================================
# RENDER SETTINGS
# ============================================================================

RENDER_SETTINGS = {
    "engine": "CYCLES",
    "device": "CPU",  # For determinism
    "samples": 64,  # Quick preview
    "resolution": (1280, 720),
    "film_transparent": False,
}

# Camera positions for library views
CAMERA_VIEWS = [
    {
        "name": "01_nave_grand",
        "location": (0, -45, 8),
        "target": (0, 0, 5),
        "description": "Grand nave view looking north",
    },
    {
        "name": "02_crossing_aerial",
        "location": (0, 0, 35),
        "target": (0, 0, 0),
        "rotation": (0, 0, 0),  # Top-down
        "description": "Aerial view of crossing and four wings",
    },
    {
        "name": "03_pod_astronomer",
        "location": (-22, -12, 3),
        "target": (-24, -9, 1),
        "description": "Astronomer Kai's study pod with telescope",
    },
    {
        "name": "04_transept_east",
        "location": (-35, 0, 6),
        "target": (0, 0, 4),
        "description": "East transept view",
    },
    {
        "name": "05_mezzanine_level",
        "location": (15, 15, 8),
        "target": (-5, -5, 5),
        "description": "Mezzanine level with railings",
    },
    {
        "name": "06_pod_philosopher",
        "location": (22, 12, 3),
        "target": (24, 9, 1),
        "description": "Philosopher Sage's study pod with hourglass",
    },
    {
        "name": "07_gothic_detail",
        "location": (-12, -6, 12),
        "target": (-6, 0, 8),
        "description": "Gothic arch and column detail",
    },
    {
        "name": "08_full_overview",
        "location": (40, -40, 25),
        "target": (0, 0, 3),
        "description": "Full library overview",
    },
]


# ============================================================================
# SETUP FUNCTIONS
# ============================================================================


def setup_render_settings():
    """Configure Cycles render settings."""
    scene = bpy.context.scene

    # Engine
    scene.render.engine = RENDER_SETTINGS["engine"]

    # Resolution
    scene.render.resolution_x = RENDER_SETTINGS["resolution"][0]
    scene.render.resolution_y = RENDER_SETTINGS["resolution"][1]
    scene.render.resolution_percentage = 100

    # Cycles settings
    if hasattr(scene, "cycles"):
        scene.cycles.samples = RENDER_SETTINGS["samples"]
        scene.cycles.use_denoising = True
        scene.cycles.device = RENDER_SETTINGS["device"]

    # Film
    scene.render.film_transparent = RENDER_SETTINGS["film_transparent"]

    # Output format
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    print(
        f"  Render settings: {RENDER_SETTINGS['resolution'][0]}x{RENDER_SETTINGS['resolution'][1]}, {RENDER_SETTINGS['samples']} samples"
    )


def create_camera(name, location, target):
    """Create a camera aimed at target point."""
    # Create camera data
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 35  # Standard lens
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500

    # Create camera object
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

    # Position
    cam_obj.location = location

    # Point at target
    direction = Vector(target) - Vector(location)
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    return cam_obj


def setup_lighting():
    """Ensure proper lighting for renders."""
    scene = bpy.context.scene

    # Check if world has nodes
    world = scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes

    # Find or create background node
    bg_node = None
    for node in nodes:
        if node.type == "BACKGROUND":
            bg_node = node
            break

    if bg_node:
        # Warm ambient light for library
        bg_node.inputs["Color"].default_value = (0.05, 0.04, 0.03, 1.0)
        bg_node.inputs["Strength"].default_value = 0.5

    # Add sun light if not present
    sun_exists = any(
        obj.type == "LIGHT" and obj.data.type == "SUN" for obj in bpy.data.objects
    )
    if not sun_exists:
        bpy.ops.object.light_add(type="SUN", location=(10, -10, 30))
        sun = bpy.context.object
        sun.name = "Library_Sun"
        sun.data.energy = 3.0
        sun.data.color = (1.0, 0.95, 0.9)  # Warm
        sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))
        print("  Added sun light")


def render_view(camera, output_path, description):
    """Render from specified camera."""
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.filepath = str(output_path)

    print(f"  Rendering: {camera.name}")
    print(f"    {description}")

    bpy.ops.render.render(write_still=True)

    print(f"    Saved: {output_path}")


# ============================================================================
# MAIN
# ============================================================================


def main():
    # Parse output directory from command line
    argv = sys.argv
    output_dir = Path("/tmp/library_renders")

    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
        for i, arg in enumerate(args):
            if arg == "--output" and i + 1 < len(args):
                output_dir = Path(args[i + 1])

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("OUTORA LIBRARY - CANONICAL RENDERS")
    print("=" * 60)
    print(f"\nOutput directory: {output_dir}")

    # Setup
    print("\nSetting up render...")
    setup_render_settings()
    setup_lighting()

    # Create cameras and render
    print(f"\nRendering {len(CAMERA_VIEWS)} views...")

    # Collection for preview cameras
    preview_col = bpy.data.collections.get("Preview_Cameras")
    if not preview_col:
        preview_col = bpy.data.collections.new("Preview_Cameras")
        bpy.context.scene.collection.children.link(preview_col)

    rendered = []

    for view_cfg in CAMERA_VIEWS:
        name = view_cfg["name"]
        location = view_cfg["location"]
        target = view_cfg["target"]
        description = view_cfg["description"]

        # Create camera
        cam = create_camera(f"Cam_{name}", location, target)

        # Move to preview collection
        bpy.context.scene.collection.objects.unlink(cam)
        preview_col.objects.link(cam)

        # Render
        output_path = output_dir / f"{name}.png"
        render_view(cam, output_path, description)
        rendered.append(output_path)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Rendered {len(rendered)} views")
    print("=" * 60)
    print("\nOutput files:")
    for path in rendered:
        print(f"  {path}")


if __name__ == "__main__":
    main()
