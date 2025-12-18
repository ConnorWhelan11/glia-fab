#!/usr/bin/env python3
"""
Add Personal Items to Study Pods.

Each student gets themed personal items based on their study focus:
- astronomer_kai: telescope, star chart, celestial globe
- historian_elena: scrolls, antique clock, magnifying glass
- alchemist_marcus: flask set, mortar & pestle, crystal
- botanist_flora: potted plants, watering can, pressed flowers
- architect_pierre: compass, ruler set, model building
- musician_aria: metronome, sheet music stand, tuning fork
- cartographer_nemo: globe, compass, sextant
- philosopher_sage: hourglass, quill set, thinking bust

Run with:
    blender outora_library_v0.2.0.blend --background --python add_personal_items.py
"""

import bpy
import math
import random
from mathutils import Vector, Matrix


# ============================================================================
# PERSONAL ITEM CONFIGURATIONS
# ============================================================================

# Item placements relative to desk center (local space before rotation)
# Format: (x_offset, y_offset, z_height, scale, rotation_variance)

STUDENT_ITEMS = {
    "astronomer_kai": {
        "theme_color": (0.1, 0.15, 0.3),  # Deep blue
        "items": [
            {"name": "telescope", "offset": (-0.4, 0.0, 0.75), "scale": 0.15},
            {"name": "celestial_globe", "offset": (0.35, -0.2, 0.78), "scale": 0.08},
            {
                "name": "star_chart",
                "offset": (0.0, 0.25, 0.76),
                "scale": 0.12,
                "flat": True,
            },
        ],
    },
    "historian_elena": {
        "theme_color": (0.5, 0.35, 0.2),  # Parchment brown
        "items": [
            {"name": "scroll_rack", "offset": (-0.35, 0.1, 0.75), "scale": 0.1},
            {"name": "antique_clock", "offset": (0.38, -0.15, 0.78), "scale": 0.06},
            {"name": "magnifying_glass", "offset": (0.15, 0.2, 0.76), "scale": 0.05},
        ],
    },
    "alchemist_marcus": {
        "theme_color": (0.4, 0.6, 0.3),  # Green potion
        "items": [
            {"name": "flask_set", "offset": (-0.3, 0.0, 0.75), "scale": 0.08},
            {"name": "mortar_pestle", "offset": (0.3, 0.15, 0.76), "scale": 0.06},
            {
                "name": "crystal",
                "offset": (0.0, -0.2, 0.78),
                "scale": 0.04,
                "emissive": True,
            },
        ],
    },
    "botanist_flora": {
        "theme_color": (0.2, 0.5, 0.2),  # Leaf green
        "items": [
            {"name": "potted_plant", "offset": (-0.35, 0.1, 0.75), "scale": 0.12},
            {"name": "small_plant", "offset": (0.35, -0.1, 0.76), "scale": 0.08},
            {
                "name": "pressed_flowers",
                "offset": (0.1, 0.25, 0.755),
                "scale": 0.1,
                "flat": True,
            },
        ],
    },
    "architect_pierre": {
        "theme_color": (0.6, 0.55, 0.5),  # Stone gray
        "items": [
            {"name": "drafting_compass", "offset": (-0.25, 0.15, 0.76), "scale": 0.05},
            {
                "name": "ruler_set",
                "offset": (0.3, 0.0, 0.755),
                "scale": 0.08,
                "flat": True,
            },
            {"name": "model_tower", "offset": (0.0, -0.25, 0.75), "scale": 0.1},
        ],
    },
    "musician_aria": {
        "theme_color": (0.6, 0.4, 0.5),  # Rose gold
        "items": [
            {"name": "metronome", "offset": (-0.3, 0.0, 0.75), "scale": 0.07},
            {
                "name": "sheet_music",
                "offset": (0.2, 0.2, 0.755),
                "scale": 0.1,
                "flat": True,
            },
            {"name": "tuning_fork", "offset": (0.35, -0.15, 0.76), "scale": 0.04},
        ],
    },
    "cartographer_nemo": {
        "theme_color": (0.3, 0.4, 0.5),  # Ocean blue-gray
        "items": [
            {"name": "world_globe", "offset": (-0.35, 0.05, 0.75), "scale": 0.1},
            {"name": "compass_nav", "offset": (0.3, -0.1, 0.77), "scale": 0.04},
            {"name": "rolled_map", "offset": (0.15, 0.25, 0.76), "scale": 0.08},
        ],
    },
    "philosopher_sage": {
        "theme_color": (0.4, 0.3, 0.4),  # Deep purple
        "items": [
            {"name": "hourglass", "offset": (-0.3, 0.1, 0.75), "scale": 0.08},
            {"name": "quill_inkwell", "offset": (0.35, 0.0, 0.76), "scale": 0.05},
            {"name": "thinking_bust", "offset": (0.0, -0.25, 0.75), "scale": 0.07},
        ],
    },
}


# ============================================================================
# PROCEDURAL ITEM GENERATORS
# ============================================================================


def create_telescope(name, scale=0.15):
    """Create a simple telescope."""
    # Main tube
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.8, location=(0, 0, 0.2))
    tube = bpy.context.object
    tube.rotation_euler = (math.radians(30), 0, 0)

    # Lens end (larger)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=0.1, location=(0, 0.35, 0.4))
    lens = bpy.context.object
    lens.rotation_euler = (math.radians(30), 0, 0)

    # Eyepiece
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.08, depth=0.15, location=(0, -0.45, 0.0)
    )
    eye = bpy.context.object
    eye.rotation_euler = (math.radians(30), 0, 0)

    # Tripod legs (3)
    legs = []
    for i in range(3):
        angle = i * (2 * math.pi / 3)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.02,
            depth=0.5,
            location=(0.15 * math.cos(angle), 0.15 * math.sin(angle), -0.15),
        )
        leg = bpy.context.object
        leg.rotation_euler = (
            math.radians(15) * math.cos(angle),
            math.radians(15) * math.sin(angle),
            0,
        )
        legs.append(leg)

    # Join all
    for obj in [tube, lens, eye] + legs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = tube
    bpy.ops.object.join()

    telescope = bpy.context.object
    telescope.name = name
    telescope.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)

    # Material - brass
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.7, 0.55, 0.3, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.8
    bsdf.inputs["Roughness"].default_value = 0.3
    telescope.data.materials.append(mat)

    return telescope


def create_globe(name, scale=0.1, theme_color=(0.2, 0.4, 0.6)):
    """Create a globe on stand."""
    # Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(0, 0, 0.35))
    sphere = bpy.context.object

    # Ring around equator
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.32,
        minor_radius=0.02,
        location=(0, 0, 0.35),
        rotation=(math.radians(23.5), 0, 0),  # Tilted like Earth
    )
    ring = bpy.context.object

    # Stand base
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=0.05, location=(0, 0, 0.025))
    base = bpy.context.object

    # Stand pillar
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.3, location=(0, 0, 0.15))
    pillar = bpy.context.object

    # Join
    for obj in [sphere, ring, base, pillar]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = sphere
    bpy.ops.object.join()

    globe = bpy.context.object
    globe.name = name
    globe.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)

    # Material
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*theme_color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    globe.data.materials.append(mat)

    return globe


def create_potted_plant(name, scale=0.12):
    """Create a potted plant."""
    # Pot
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.2, location=(0, 0, 0.1))
    pot = bpy.context.object

    # Soil
    bpy.ops.mesh.primitive_cylinder_add(radius=0.13, depth=0.03, location=(0, 0, 0.185))
    soil = bpy.context.object

    # Plant leaves (simple cones)
    leaves = []
    for i in range(5):
        angle = i * (2 * math.pi / 5) + random.uniform(-0.2, 0.2)
        height = 0.25 + random.uniform(0, 0.1)
        bpy.ops.mesh.primitive_cone_add(
            radius1=0.08,
            depth=height,
            location=(0.05 * math.cos(angle), 0.05 * math.sin(angle), 0.2 + height / 2),
        )
        leaf = bpy.context.object
        leaf.rotation_euler = (
            random.uniform(-0.3, 0.3),
            random.uniform(-0.3, 0.3),
            angle,
        )
        leaves.append(leaf)

    # Join pot and soil
    pot.select_set(True)
    soil.select_set(True)
    bpy.context.view_layer.objects.active = pot
    bpy.ops.object.join()

    plant_pot = bpy.context.object

    # Material for pot
    pot_mat = bpy.data.materials.new(name=f"{name}_pot_mat")
    pot_mat.use_nodes = True
    bsdf = pot_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.6, 0.35, 0.2, 1.0)  # Terracotta
    plant_pot.data.materials.append(pot_mat)

    # Join leaves separately with green material
    bpy.ops.object.select_all(action="DESELECT")
    for leaf in leaves:
        leaf.select_set(True)
    bpy.context.view_layer.objects.active = leaves[0]
    bpy.ops.object.join()
    leaves_obj = bpy.context.object

    leaf_mat = bpy.data.materials.new(name=f"{name}_leaf_mat")
    leaf_mat.use_nodes = True
    bsdf = leaf_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.15, 0.45, 0.15, 1.0)  # Green
    leaves_obj.data.materials.append(leaf_mat)

    # Join pot and leaves
    plant_pot.select_set(True)
    leaves_obj.select_set(True)
    bpy.context.view_layer.objects.active = plant_pot
    bpy.ops.object.join()

    plant = bpy.context.object
    plant.name = name
    plant.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)

    return plant


def create_hourglass(name, scale=0.08):
    """Create an hourglass."""
    # Top bulb
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 0.25))
    top = bpy.context.object
    top.scale = (1, 1, 1.2)
    bpy.ops.object.transform_apply(scale=True)

    # Bottom bulb
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, -0.25))
    bottom = bpy.context.object
    bottom.scale = (1, 1, 1.2)
    bpy.ops.object.transform_apply(scale=True)

    # Neck
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.2, location=(0, 0, 0))
    neck = bpy.context.object

    # Frame posts (4)
    posts = []
    for i in range(4):
        angle = i * (math.pi / 2) + math.pi / 4
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.015,
            depth=0.7,
            location=(0.12 * math.cos(angle), 0.12 * math.sin(angle), 0),
        )
        posts.append(bpy.context.object)

    # Join all
    for obj in [top, bottom, neck] + posts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.join()

    hourglass = bpy.context.object
    hourglass.name = name
    hourglass.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)

    # Glass material
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.9, 0.85, 0.7, 1.0)
    bsdf.inputs["Transmission Weight"].default_value = 0.3
    bsdf.inputs["Roughness"].default_value = 0.1
    hourglass.data.materials.append(mat)

    return hourglass


def create_simple_item(
    name, item_type, scale=0.1, theme_color=(0.5, 0.5, 0.5), flat=False, emissive=False
):
    """Create a simple placeholder item based on type."""

    if "telescope" in item_type:
        return create_telescope(name, scale)
    elif "globe" in item_type:
        return create_globe(name, scale, theme_color)
    elif "plant" in item_type:
        return create_potted_plant(name, scale)
    elif "hourglass" in item_type:
        return create_hourglass(name, scale)

    # Generic items
    if flat:
        # Flat items (papers, charts, maps)
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
        obj = bpy.context.object
        obj.scale = (scale * 2, scale * 1.5, 1)
    elif "crystal" in item_type or emissive:
        # Crystal/gem
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=scale, subdivisions=2, location=(0, 0, scale)
        )
        obj = bpy.context.object
    elif "clock" in item_type or "metronome" in item_type:
        # Tall rectangular
        bpy.ops.mesh.primitive_cube_add(size=scale, location=(0, 0, scale))
        obj = bpy.context.object
        obj.scale = (0.6, 0.4, 1.5)
    elif "flask" in item_type:
        # Flask shape
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=scale * 0.8, location=(0, 0, scale * 0.8)
        )
        sphere = bpy.context.object
        bpy.ops.mesh.primitive_cylinder_add(
            radius=scale * 0.3, depth=scale, location=(0, 0, scale * 1.8)
        )
        neck = bpy.context.object
        sphere.select_set(True)
        neck.select_set(True)
        bpy.context.view_layer.objects.active = sphere
        bpy.ops.object.join()
        obj = bpy.context.object
    elif "bust" in item_type:
        # Simple bust shape
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=scale * 0.8, location=(0, 0, scale * 1.2)
        )
        head = bpy.context.object
        bpy.ops.mesh.primitive_cone_add(
            radius1=scale * 0.6, depth=scale * 0.8, location=(0, 0, scale * 0.4)
        )
        base = bpy.context.object
        head.select_set(True)
        base.select_set(True)
        bpy.context.view_layer.objects.active = head
        bpy.ops.object.join()
        obj = bpy.context.object
    else:
        # Default: small cube
        bpy.ops.mesh.primitive_cube_add(size=scale, location=(0, 0, scale / 2))
        obj = bpy.context.object

    bpy.ops.object.transform_apply(scale=True)
    obj.name = name

    # Material
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*theme_color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4

    if emissive:
        bsdf.inputs["Emission Color"].default_value = (*theme_color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 2.0

    obj.data.materials.append(mat)

    return obj


# ============================================================================
# MAIN
# ============================================================================


def add_items_to_pod(student_name, pod_config):
    """Add personal items to a specific student's pod."""

    pod_col_name = f"StudyPod_{student_name}"
    pod_col = bpy.data.collections.get(pod_col_name)

    if not pod_col:
        print(f"  Warning: Pod collection '{pod_col_name}' not found")
        return 0

    # Find the desk to get position/rotation
    desk = None
    for obj in pod_col.objects:
        if "desk" in obj.name.lower():
            desk = obj
            break

    if not desk:
        print(f"  Warning: No desk found in {pod_col_name}")
        return 0

    pos = desk.location
    rot_z = desk.rotation_euler.z
    theme_color = pod_config["theme_color"]

    items_created = 0

    for item_cfg in pod_config["items"]:
        item_name = item_cfg["name"]
        offset = item_cfg["offset"]
        scale = item_cfg.get("scale", 0.1)
        flat = item_cfg.get("flat", False)
        emissive = item_cfg.get("emissive", False)

        # Calculate world position
        world_pos = (
            pos.x + offset[0] * math.cos(rot_z) - offset[1] * math.sin(rot_z),
            pos.y + offset[0] * math.sin(rot_z) + offset[1] * math.cos(rot_z),
            pos.z + offset[2],
        )

        # Create item
        full_name = f"{pod_col_name}_{item_name}"

        # Check if already exists
        if bpy.data.objects.get(full_name):
            continue

        item = create_simple_item(
            full_name, item_name, scale, theme_color, flat, emissive
        )
        item.location = world_pos
        item.rotation_euler.z = rot_z + random.uniform(-0.2, 0.2)

        # Add to collection
        pod_col.objects.link(item)
        if item.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(item)

        items_created += 1

    return items_created


def main():
    print("\n" + "=" * 60)
    print("ADDING PERSONAL ITEMS TO STUDY PODS")
    print("=" * 60)

    total_items = 0

    for student_name, pod_config in STUDENT_ITEMS.items():
        print(f"\n  {student_name}:")
        items = add_items_to_pod(student_name, pod_config)
        print(f"    Added {items} items")
        total_items += items

    print("\n" + "=" * 60)
    print(f"COMPLETE: Added {total_items} personal items")
    print("=" * 60)


if __name__ == "__main__":
    main()
