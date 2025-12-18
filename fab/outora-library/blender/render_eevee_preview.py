#!/usr/bin/env python3
"""
Render Library Preview with Eevee - Fast previews.

Eevee is much faster than Cycles for preview renders.

Run with:
    blender outora_library_v0.3.0.blend --background --python render_eevee_preview.py
"""

import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector


OUTPUT_DIR = Path("/tmp/outora-library-renders")

# Camera views - subset for quick preview
CAMERA_VIEWS = [
    {
        "name": "01_overview",
        "location": (40, -40, 25),
        "target": (0, 0, 3),
    },
    {
        "name": "02_nave",
        "location": (0, -40, 8),
        "target": (0, 0, 5),
    },
    {
        "name": "03_crossing",
        "location": (0, 0, 30),
        "target": (0, 0, 0),
    },
    {
        "name": "04_pod_closeup",
        "location": (-20, -10, 4),
        "target": (-24, -9, 1.5),
    },
]


def setup_eevee():
    """Configure Eevee for fast, quality renders."""
    scene = bpy.context.scene

    # Switch to Eevee (BLENDER_EEVEE for Blender 5.x)
    scene.render.engine = "BLENDER_EEVEE"

    # Resolution
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100

    # Eevee settings (Blender 5.x compatible)
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 64
        # Note: use_gtao, use_bloom, use_ssr may not exist in Blender 5.x
        # Using try/except for compatibility
        try:
            scene.eevee.use_gtao = True
        except AttributeError:
            pass
        try:
            scene.eevee.use_bloom = True
        except AttributeError:
            pass
        try:
            scene.eevee.use_ssr = True
        except AttributeError:
            pass

    # Output
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    print("  Eevee configured: 1920x1080, 64 samples")


def setup_lighting():
    """Setup lighting for Eevee."""
    scene = bpy.context.scene

    # World background
    if not scene.world:
        scene.world = bpy.data.worlds.new("World")

    world = scene.world
    world.use_nodes = True

    bg = None
    for node in world.node_tree.nodes:
        if node.type == "BACKGROUND":
            bg = node
            break

    if bg:
        bg.inputs["Color"].default_value = (0.02, 0.02, 0.03, 1.0)
        bg.inputs["Strength"].default_value = 0.3

    # Add area lights for interior
    lights_to_add = [
        {"name": "Main_Light", "location": (0, 0, 15), "energy": 5000, "size": 10},
        {"name": "Fill_North", "location": (0, 30, 10), "energy": 2000, "size": 8},
        {"name": "Fill_South", "location": (0, -30, 10), "energy": 2000, "size": 8},
        {"name": "Fill_East", "location": (30, 0, 10), "energy": 2000, "size": 8},
        {"name": "Fill_West", "location": (-30, 0, 10), "energy": 2000, "size": 8},
    ]

    for light_cfg in lights_to_add:
        if bpy.data.objects.get(light_cfg["name"]):
            continue

        bpy.ops.object.light_add(type="AREA", location=light_cfg["location"])
        light = bpy.context.object
        light.name = light_cfg["name"]
        light.data.energy = light_cfg["energy"]
        light.data.size = light_cfg["size"]
        light.data.color = (1.0, 0.95, 0.85)  # Warm
        light.rotation_euler = (0, 0, 0)

    print("  Lighting setup complete")


def create_camera(name, location, target):
    """Create camera aimed at target."""
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = 28
    cam_data.clip_end = 500

    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location

    direction = Vector(target) - Vector(location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return cam


def render_views():
    """Render all camera views."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nRendering {len(CAMERA_VIEWS)} views to {OUTPUT_DIR}")

    for i, view in enumerate(CAMERA_VIEWS):
        name = view["name"]
        cam = create_camera(f"EeveeCam_{name}", view["location"], view["target"])

        bpy.context.scene.camera = cam
        output_path = OUTPUT_DIR / f"eevee_{name}.png"
        bpy.context.scene.render.filepath = str(output_path)

        print(f"  [{i+1}/{len(CAMERA_VIEWS)}] Rendering {name}...")
        bpy.ops.render.render(write_still=True)
        print(f"       Saved: {output_path}")

    return OUTPUT_DIR


def main():
    print("\n" + "=" * 60)
    print("OUTORA LIBRARY - EEVEE PREVIEW RENDERS")
    print("=" * 60)

    setup_eevee()
    setup_lighting()

    output = render_views()

    print("\n" + "=" * 60)
    print(f"COMPLETE! Renders saved to: {output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
