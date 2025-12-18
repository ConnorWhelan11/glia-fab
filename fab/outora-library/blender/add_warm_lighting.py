#!/usr/bin/env python3
"""
Add Warm Library Lighting.

Enhances the Outora Library with warm, atmospheric lighting:
- Overhead area lights (simulating skylights)
- Point lights near study pods (desk lamps)
- Accent lights on columns and arches
- Warm ambient fill

Run with:
    blender outora_library_v0.3.0.blend --background --python add_warm_lighting.py
"""

import bpy
import math
from mathutils import Vector


# Lighting configuration
LIGHTING_CONFIG = {
    "ambient_color": (1.0, 0.92, 0.85),  # Warm white
    "ambient_strength": 0.15,
    "skylights": {
        "count": 4,  # One per wing
        "color": (1.0, 0.95, 0.88),
        "energy": 2000,
        "size": 8.0,
        "height": 18,
    },
    "crossing_light": {
        "color": (1.0, 0.98, 0.92),
        "energy": 5000,
        "size": 12.0,
        "height": 22,
    },
    "desk_lamps": {
        "color": (1.0, 0.85, 0.65),  # Warm orange
        "energy": 50,
        "radius": 6.0,
    },
    "column_accents": {
        "color": (1.0, 0.75, 0.5),  # Amber
        "energy": 100,
        "radius": 8.0,
    },
    "world_hdri": {
        "use_hdri": False,  # Set to True if you have an HDRI
        "hdri_path": "",
        "strength": 0.5,
    },
}


def ensure_collection(name):
    """Get or create a collection."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def clear_existing_lights():
    """Remove existing lights we might have added."""
    lights_col = bpy.data.collections.get("OL_Lighting")
    if lights_col:
        for obj in list(lights_col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(lights_col)

    print("  Cleared existing OL_Lighting collection")


def create_area_light(name, location, color, energy, size, rotation=(0, 0, 0)):
    """Create an area light."""
    light_data = bpy.data.lights.new(name=name, type="AREA")
    light_data.color = color
    light_data.energy = energy
    light_data.size = size
    light_data.use_shadow = True

    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.location = location
    light_obj.rotation_euler = rotation

    return light_obj


def create_point_light(name, location, color, energy, radius):
    """Create a point light."""
    light_data = bpy.data.lights.new(name=name, type="POINT")
    light_data.color = color
    light_data.energy = energy
    light_data.shadow_soft_size = radius
    light_data.use_shadow = True

    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.location = location

    return light_obj


def setup_world():
    """Setup world/environment lighting."""
    scene = bpy.context.scene

    if not scene.world:
        scene.world = bpy.data.worlds.new("OuturaWorld")

    world = scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing nodes
    nodes.clear()

    # Create nodes
    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (300, 0)

    bg = nodes.new("ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs["Color"].default_value = (*LIGHTING_CONFIG["ambient_color"], 1.0)
    bg.inputs["Strength"].default_value = LIGHTING_CONFIG["ambient_strength"]

    links.new(bg.outputs["Background"], output.inputs["Surface"])

    print("  Configured world background")


def add_skylights(lights_col):
    """Add overhead area lights for each wing."""
    cfg = LIGHTING_CONFIG["skylights"]

    # Wing positions (approximate centers)
    wing_positions = [
        (0, -25, cfg["height"]),  # South nave
        (0, 25, cfg["height"]),  # North nave
        (-25, 0, cfg["height"]),  # West transept
        (25, 0, cfg["height"]),  # East transept
    ]

    for i, pos in enumerate(wing_positions):
        name = f"OL_Skylight_{i:02d}"
        light = create_area_light(
            name=name,
            location=pos,
            color=cfg["color"],
            energy=cfg["energy"],
            size=cfg["size"],
            rotation=(0, 0, 0),  # Pointing down
        )
        lights_col.objects.link(light)

    print(f"  Added {len(wing_positions)} skylights")


def add_crossing_light(lights_col):
    """Add main light at the crossing."""
    cfg = LIGHTING_CONFIG["crossing_light"]

    light = create_area_light(
        name="OL_CrossingLight",
        location=(0, 0, cfg["height"]),
        color=cfg["color"],
        energy=cfg["energy"],
        size=cfg["size"],
        rotation=(0, 0, 0),
    )
    lights_col.objects.link(light)

    print("  Added crossing light")


def add_desk_lamps(lights_col):
    """Add warm point lights near study pods."""
    cfg = LIGHTING_CONFIG["desk_lamps"]

    # Find study pod collections and add lights near desks
    lamps_added = 0

    for col in bpy.data.collections:
        if col.name.startswith("StudyPod_"):
            # Find desk in this pod
            for obj in col.objects:
                if "desk" in obj.name.lower():
                    # Add lamp above desk
                    lamp_pos = (obj.location.x, obj.location.y, obj.location.z + 1.5)

                    name = f"OL_DeskLamp_{col.name.replace('StudyPod_', '')}"
                    light = create_point_light(
                        name=name,
                        location=lamp_pos,
                        color=cfg["color"],
                        energy=cfg["energy"],
                        radius=cfg["radius"],
                    )
                    lights_col.objects.link(light)
                    lamps_added += 1
                    break

    print(f"  Added {lamps_added} desk lamps")


def add_column_accents(lights_col):
    """Add accent lights near columns."""
    cfg = LIGHTING_CONFIG["column_accents"]

    # Place accent lights at regular intervals along main axes
    positions = []

    # Along nave (Y axis)
    for y in range(-40, 41, 10):
        if abs(y) > 5:  # Skip crossing area
            positions.append((-8, y, 4))
            positions.append((8, y, 4))

    # Along transept (X axis)
    for x in range(-40, 41, 10):
        if abs(x) > 5:
            positions.append((x, -8, 4))
            positions.append((x, 8, 4))

    for i, pos in enumerate(positions):
        name = f"OL_ColumnAccent_{i:02d}"
        light = create_point_light(
            name=name,
            location=pos,
            color=cfg["color"],
            energy=cfg["energy"],
            radius=cfg["radius"],
        )
        lights_col.objects.link(light)

    print(f"  Added {len(positions)} column accent lights")


def add_spotlight_drama(lights_col):
    """Add dramatic spotlights on key areas."""
    # Spotlight on crossing from angle
    spot_data = bpy.data.lights.new(name="OL_DramaSpot", type="SPOT")
    spot_data.color = (1.0, 0.9, 0.7)
    spot_data.energy = 3000
    spot_data.spot_size = math.radians(60)
    spot_data.spot_blend = 0.3
    spot_data.use_shadow = True

    spot = bpy.data.objects.new("OL_DramaSpot", spot_data)
    spot.location = (20, -20, 25)

    # Point at center
    direction = Vector((0, 0, 0)) - Vector(spot.location)
    spot.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    lights_col.objects.link(spot)

    print("  Added dramatic spotlight")


def main():
    print("\n" + "=" * 60)
    print("ADDING WARM LIBRARY LIGHTING")
    print("=" * 60)

    # Clear existing
    clear_existing_lights()

    # Create lighting collection
    lights_col = ensure_collection("OL_Lighting")

    # Setup world
    setup_world()

    # Add lights
    add_skylights(lights_col)
    add_crossing_light(lights_col)
    add_desk_lamps(lights_col)
    add_column_accents(lights_col)
    add_spotlight_drama(lights_col)

    # Count total lights
    total_lights = len(lights_col.objects)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Added {total_lights} lights")
    print("=" * 60)
    print("\nLighting collection: OL_Lighting")
    print("To adjust, select lights and modify in Properties panel")


if __name__ == "__main__":
    main()
