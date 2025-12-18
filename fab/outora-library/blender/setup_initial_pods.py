#!/usr/bin/env python3
"""
Setup Initial Study Pods for Outora Library.

This script:
1. Fixes material issues on placeholder objects (Alpha, Beta, etc.)
2. Creates 8 hand-tuned study pods at specific positions
3. Each pod has a unique configuration (desk style, books, personal items)

Run with:
    blender outora_library_v0.1.1.blend --background --python setup_initial_pods.py

Or interactively in Blender's Text Editor.
"""

import bpy
import math
import random
from mathutils import Vector, Matrix


# ============================================================================
# CONFIGURATION
# ============================================================================

# Study pod configurations - 8 unique students with personality
STUDENT_PODS = [
    {
        "name": "astronomer_kai",
        "position": (-24.0, -9.0, 0.0),
        "rotation_z": 0.0,
        "desk_style": "wood",
        "chair_type": "armchair",
        "book_density": 0.9,
        "theme": "astronomy",  # For future personal items
        "description": "Kai studies celestial mechanics and star charts",
    },
    {
        "name": "historian_elena",
        "position": (-24.0, 9.0, 0.0),
        "rotation_z": math.pi,
        "desk_style": "wood",
        "chair_type": "wooden",
        "book_density": 0.8,
        "theme": "history",
        "description": "Elena researches ancient civilizations",
    },
    {
        "name": "alchemist_marcus",
        "position": (-18.0, -9.0, 0.0),
        "rotation_z": 0.0,
        "desk_style": "metal",
        "chair_type": "stool",
        "book_density": 0.6,
        "theme": "alchemy",
        "description": "Marcus experiments with elemental transformations",
    },
    {
        "name": "botanist_flora",
        "position": (-18.0, 9.0, 0.0),
        "rotation_z": math.pi,
        "desk_style": "wood",
        "chair_type": "wooden",
        "book_density": 0.5,
        "theme": "botany",
        "description": "Flora studies rare magical plants",
    },
    {
        "name": "architect_pierre",
        "position": (18.0, -9.0, 0.0),
        "rotation_z": 0.0,
        "desk_style": "concrete",
        "chair_type": "modern",
        "book_density": 0.7,
        "theme": "architecture",
        "description": "Pierre designs impossible structures",
    },
    {
        "name": "musician_aria",
        "position": (18.0, 9.0, 0.0),
        "rotation_z": math.pi,
        "desk_style": "glass",
        "chair_type": "modern",
        "book_density": 0.4,
        "theme": "music",
        "description": "Aria composes symphonies of light",
    },
    {
        "name": "cartographer_nemo",
        "position": (24.0, -9.0, 0.0),
        "rotation_z": 0.0,
        "desk_style": "wood",
        "chair_type": "armchair",
        "book_density": 0.8,
        "theme": "cartography",
        "description": "Nemo maps uncharted dimensions",
    },
    {
        "name": "philosopher_sage",
        "position": (24.0, 9.0, 0.0),
        "rotation_z": math.pi,
        "desk_style": "concrete",
        "chair_type": "wooden",
        "book_density": 1.0,
        "theme": "philosophy",
        "description": "Sage contemplates the nature of knowledge itself",
    },
]

# Greek letter objects to fix materials on
GREEK_LETTERS = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", 
    "Zeta", "Eta", "Theta", "Iota", "Kappa",
    "Lambda", "Mu", "Nu", "Xi", "Omicron",
    "Pi", "Rho", "Sigma", "Tau", "Upsilon",
    "Phi", "Chi", "Psi", "Omega"
]

# Material definitions
MATERIALS = {
    "ol_mat_gothic_stone": (0.92, 0.90, 0.85, 0.4),  # RGBA + roughness
    "ol_mat_wood_dark": (0.10, 0.05, 0.02, 0.4),
    "ol_mat_brass": (0.80, 0.60, 0.20, 0.2),  # Metallic
    "ol_mat_glass": (0.85, 0.95, 1.00, 0.02),
    "ol_mat_placeholder": (0.5, 0.5, 0.5, 0.5),  # Gray for placeholders
}


# ============================================================================
# MATERIAL HELPERS
# ============================================================================

def get_or_create_material(name, color, roughness=0.5, metallic=0.0):
    """Get existing material or create new one."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
            bsdf.inputs["Roughness"].default_value = roughness
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def fix_placeholder_materials():
    """Add materials to Greek letter placeholder objects."""
    print("\n=== Fixing Placeholder Materials ===")
    
    # Get or create placeholder material
    placeholder_mat = get_or_create_material(
        "ol_mat_greek_letter",
        (0.8, 0.75, 0.65),  # Warm stone color
        roughness=0.3,
        metallic=0.1
    )
    
    fixed_count = 0
    for letter in GREEK_LETTERS:
        obj = bpy.data.objects.get(letter)
        if obj and obj.type == "MESH":
            if not obj.data.materials:
                obj.data.materials.append(placeholder_mat)
                print(f"  Fixed: {letter}")
                fixed_count += 1
            elif obj.data.materials[0] is None:
                obj.data.materials[0] = placeholder_mat
                print(f"  Fixed empty slot: {letter}")
                fixed_count += 1
    
    print(f"  Total fixed: {fixed_count} objects")
    return fixed_count


# ============================================================================
# POD CREATION HELPERS
# ============================================================================

def find_source_object(name):
    """Find source object for instancing."""
    obj = bpy.data.objects.get(name)
    if obj:
        return obj
    
    # Check common collections
    for col_name in ["OL_Assets", "OL_PodSources", "OL_Furniture"]:
        col = bpy.data.collections.get(col_name)
        if col:
            for obj in col.objects:
                if obj.name == name or obj.name.startswith(name):
                    return obj
    return None


def instance_object(src, name, location, rotation_z=0.0, scale=(1, 1, 1)):
    """Create a linked duplicate of source object."""
    if not src:
        return None
    
    inst = src.copy()
    if src.data:
        inst.data = src.data.copy()
    
    inst.name = name
    inst.location = location
    inst.rotation_euler = (0, 0, rotation_z)
    inst.scale = scale
    return inst


def create_simple_desk(name, style="wood"):
    """Create a basic desk if source not found."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.375))
    desk = bpy.context.object
    desk.name = name
    desk.scale = (1.2, 0.6, 0.75)
    bpy.ops.object.transform_apply(scale=True)
    
    # Style-based color
    colors = {
        "wood": (0.3, 0.2, 0.1),
        "concrete": (0.5, 0.5, 0.5),
        "metal": (0.4, 0.4, 0.45),
        "glass": (0.7, 0.8, 0.9),
    }
    color = colors.get(style, colors["wood"])
    
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6 if style != "glass" else 0.1
    if style == "glass":
        bsdf.inputs["Transmission Weight"].default_value = 0.5
    desk.data.materials.append(mat)
    
    return desk


def create_simple_chair(name, style="wooden"):
    """Create a basic chair if source not found."""
    # Seat
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 0.45))
    seat = bpy.context.object
    seat.scale = (1.0, 1.0, 0.1)
    bpy.ops.object.transform_apply(scale=True)
    
    # Back
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, -0.18, 0.7))
    back = bpy.context.object
    back.scale = (1.0, 0.1, 0.6)
    bpy.ops.object.transform_apply(scale=True)
    
    # Legs (4)
    leg_positions = [(-0.15, -0.15, 0.2), (0.15, -0.15, 0.2), 
                     (-0.15, 0.15, 0.2), (0.15, 0.15, 0.2)]
    legs = []
    for i, pos in enumerate(leg_positions):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.4, location=pos)
        leg = bpy.context.object
        legs.append(leg)
    
    # Join all parts
    seat.select_set(True)
    back.select_set(True)
    for leg in legs:
        leg.select_set(True)
    bpy.context.view_layer.objects.active = seat
    bpy.ops.object.join()
    
    chair = bpy.context.object
    chair.name = name
    
    # Material
    mat = bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.4, 0.25, 0.1, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    chair.data.materials.append(mat)
    
    return chair


def create_book_stack(name, num_books=5, seed=42):
    """Create a stack of books with varied colors."""
    rng = random.Random(seed)
    
    books = []
    z = 0
    for i in range(num_books):
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, z + 0.015))
        book = bpy.context.object
        book.scale = (
            0.18 + rng.uniform(-0.02, 0.02),
            0.12 + rng.uniform(-0.02, 0.02),
            0.03 + rng.uniform(-0.01, 0.01)
        )
        bpy.ops.object.transform_apply(scale=True)
        
        # Random book color (muted tones)
        mat = bpy.data.materials.new(name=f"book_{name}_{i}_mat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (
            rng.uniform(0.15, 0.6),
            rng.uniform(0.1, 0.4),
            rng.uniform(0.1, 0.35),
            1.0
        )
        bsdf.inputs["Roughness"].default_value = 0.7
        book.data.materials.append(mat)
        books.append(book)
        z += 0.032
    
    # Join all books
    for b in books:
        b.select_set(True)
    bpy.context.view_layer.objects.active = books[0]
    bpy.ops.object.join()
    
    stack = bpy.context.object
    stack.name = name
    return stack


def create_study_pod(config):
    """Create a complete study pod from configuration."""
    name = config["name"]
    pos = config["position"]
    rot_z = config["rotation_z"]
    desk_style = config.get("desk_style", "wood")
    chair_type = config.get("chair_type", "wooden")
    book_density = config.get("book_density", 0.5)
    seed = hash(name) % 10000
    
    print(f"\n  Creating pod: {name}")
    print(f"    Position: {pos}")
    print(f"    Desk: {desk_style}, Chair: {chair_type}")
    
    # Create or get collection
    pod_col_name = f"StudyPod_{name}"
    pod_col = bpy.data.collections.get(pod_col_name)
    if not pod_col:
        pod_col = bpy.data.collections.new(pod_col_name)
        
        # Link to scene
        bpy.context.scene.collection.children.link(pod_col)
    
    # Clear existing objects in collection
    for obj in list(pod_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    
    created_objects = []
    
    # --- DESK ---
    desk_sources = {
        "concrete": "ol_desk_concrete",
        "wood": "ol_desk_wood", 
        "glass": "ol_desk_glass",
        "metal": "ol_desk_metal",
    }
    desk_src = find_source_object(desk_sources.get(desk_style, "ol_desk_concrete"))
    
    if desk_src:
        desk = instance_object(
            desk_src,
            f"{pod_col_name}_desk",
            pos,
            rot_z,
            (1.35, 1.35, 1.35)
        )
    else:
        desk = create_simple_desk(f"{pod_col_name}_desk", desk_style)
        desk.location = pos
        desk.rotation_euler.z = rot_z
    
    if desk:
        pod_col.objects.link(desk)
        if desk.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(desk)
        created_objects.append(desk)
    
    # --- CHAIR ---
    chair_configs = {
        "wooden": {"source": "WoodenChair_01", "scale": (0.85, 0.85, 0.85), "offset": (0, 1.2, 0)},
        "modern": {"source": "ol_chair_modern", "scale": (1.0, 1.0, 1.0), "offset": (0, 1.0, 0)},
        "stool": {"source": "ol_stool", "scale": (1.0, 1.0, 1.0), "offset": (0, 0.8, 0)},
        "armchair": {"source": "ol_armchair", "scale": (1.0, 1.0, 1.0), "offset": (0, 1.4, 0)},
    }
    chair_cfg = chair_configs.get(chair_type, chair_configs["wooden"])
    
    # Calculate chair position with rotation
    offset = chair_cfg["offset"]
    chair_pos = (
        pos[0] + offset[0] * math.cos(rot_z) - offset[1] * math.sin(rot_z),
        pos[1] + offset[0] * math.sin(rot_z) + offset[1] * math.cos(rot_z),
        pos[2] + offset[2]
    )
    
    chair_src = find_source_object(chair_cfg["source"])
    if chair_src:
        chair = instance_object(
            chair_src,
            f"{pod_col_name}_chair",
            chair_pos,
            rot_z + math.pi,
            chair_cfg["scale"]
        )
    else:
        chair = create_simple_chair(f"{pod_col_name}_chair", chair_type)
        chair.location = chair_pos
        chair.rotation_euler.z = rot_z + math.pi
    
    if chair:
        pod_col.objects.link(chair)
        if chair.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(chair)
        created_objects.append(chair)
    
    # --- BOOKS ---
    if book_density > 0:
        desk_top_z = 0.75
        rng = random.Random(seed)
        
        # Book placement slots
        book_slots = [
            (-0.25, -0.15),
            (0.20, 0.08),
            (-0.35, 0.12),
            (0.28, -0.12),
        ]
        
        num_stacks = max(1, int(len(book_slots) * book_density))
        for i in range(num_stacks):
            slot = book_slots[i]
            stack_pos = (
                pos[0] + slot[0] * math.cos(rot_z) - slot[1] * math.sin(rot_z),
                pos[1] + slot[0] * math.sin(rot_z) + slot[1] * math.cos(rot_z),
                pos[2] + desk_top_z
            )
            
            # Try to find existing book stack source
            book_sources = [
                "ol_book_stack_a", "ol_book_stack_b", "ol_book_stack_c",
                "ol_book_stack_d", "ol_book_stack_e"
            ]
            book_src = None
            for src_name in book_sources:
                book_src = find_source_object(src_name)
                if book_src:
                    break
            
            if book_src:
                stack = instance_object(
                    book_src,
                    f"{pod_col_name}_books_{i}",
                    stack_pos,
                    rot_z + rng.uniform(-0.3, 0.3),
                    (0.02, 0.02, 0.02)
                )
            else:
                num_books = rng.randint(3, 6)
                stack = create_book_stack(
                    f"{pod_col_name}_books_{i}",
                    num_books,
                    seed + i
                )
                stack.location = stack_pos
                stack.rotation_euler.z = rot_z + rng.uniform(-0.3, 0.3)
            
            if stack:
                pod_col.objects.link(stack)
                if stack.name in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.unlink(stack)
                created_objects.append(stack)
    
    # --- LAMP ---
    lamp_offset = (0.35, 0.25, 0.75)
    lamp_pos = (
        pos[0] + lamp_offset[0] * math.cos(rot_z) - lamp_offset[1] * math.sin(rot_z),
        pos[1] + lamp_offset[0] * math.sin(rot_z) + lamp_offset[1] * math.cos(rot_z),
        pos[2] + lamp_offset[2]
    )
    
    lamp_src = find_source_object("desk_lamp_arm_01")
    if lamp_src:
        lamp = instance_object(
            lamp_src,
            f"{pod_col_name}_lamp",
            lamp_pos,
            rot_z,
            (1.0, 1.0, 1.0)
        )
        if lamp:
            pod_col.objects.link(lamp)
            if lamp.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(lamp)
            created_objects.append(lamp)
    
    print(f"    Created {len(created_objects)} objects")
    return created_objects


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 60)
    print("OUTORA LIBRARY - INITIAL POD SETUP")
    print("=" * 60)
    
    # Step 1: Fix placeholder materials
    fixed = fix_placeholder_materials()
    
    # Step 2: Create study pods
    print("\n=== Creating Study Pods ===")
    total_objects = 0
    
    for config in STUDENT_PODS:
        objects = create_study_pod(config)
        total_objects += len(objects)
    
    print("\n" + "=" * 60)
    print(f"SETUP COMPLETE")
    print(f"  - Fixed {fixed} placeholder materials")
    print(f"  - Created {len(STUDENT_PODS)} study pods")
    print(f"  - Total objects created: {total_objects}")
    print("=" * 60)
    
    # Optionally save
    # bpy.ops.wm.save_mainfile()


if __name__ == "__main__":
    main()

