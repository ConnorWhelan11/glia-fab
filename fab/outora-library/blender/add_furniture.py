"""
Add Furniture to Gothic Library - Desks, chairs, and additional items.

This script adds furniture objects at study pod positions to satisfy
the gate validation furniture requirements.

Usage in Blender:
    exec(open("add_furniture.py").read())
"""

import bpy
from math import pi, radians
from mathutils import Vector
import random

# =============================================================================
# FURNITURE CONFIGURATIONS
# =============================================================================

# Study pod positions (from sverchok_layout_v2.py)
BAY = 6.0

def get_study_positions():
    """Generate study pod positions in the aisles."""
    positions = []
    
    # Positions in wing aisles
    for wing_sign in [-1, 1]:
        for aisle_sign in [-1, 1]:
            # X-wing positions
            for i in range(3):
                x = wing_sign * (12 + i * BAY)
                y = aisle_sign * 2 * BAY
                positions.append((x, y, 0))
            
            # Y-wing positions
            for i in range(3):
                x = aisle_sign * 2 * BAY
                y = wing_sign * (12 + i * BAY)
                positions.append((x, y, 0))
    
    return positions


# =============================================================================
# FURNITURE CREATION
# =============================================================================

def create_desk(name: str, location: tuple, rotation_z: float = 0) -> bpy.types.Object:
    """Create a study desk."""
    # Desk dimensions
    width = 1.2
    depth = 0.7
    height = 0.75
    thickness = 0.04
    
    # Create desk top
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, height - thickness/2))
    desk_top = bpy.context.active_object
    desk_top.scale = (width/2, depth/2, thickness/2)
    desk_top.name = f"desk_{name}_top"
    
    # Create legs
    leg_positions = [
        (width/2 - 0.05, depth/2 - 0.05),
        (-width/2 + 0.05, depth/2 - 0.05),
        (width/2 - 0.05, -depth/2 + 0.05),
        (-width/2 + 0.05, -depth/2 + 0.05),
    ]
    
    legs = []
    for i, (lx, ly) in enumerate(leg_positions):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(lx, ly, height/2 - thickness))
        leg = bpy.context.active_object
        leg.scale = (0.03, 0.03, height/2 - thickness)
        leg.name = f"desk_{name}_leg_{i}"
        legs.append(leg)
    
    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    desk_top.select_set(True)
    for leg in legs:
        leg.select_set(True)
    bpy.context.view_layer.objects.active = desk_top
    bpy.ops.object.join()
    
    desk = bpy.context.active_object
    desk.name = f"desk_{name}"
    desk.location = location
    desk.rotation_euler.z = rotation_z
    
    # Apply material
    mat = bpy.data.materials.get("gm_wood_desk")
    if mat:
        desk.data.materials.append(mat)
    
    return desk


def create_chair(name: str, location: tuple, rotation_z: float = 0) -> bpy.types.Object:
    """Create a study chair."""
    seat_height = 0.45
    seat_size = 0.45
    back_height = 0.4
    
    # Seat
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, seat_height))
    seat = bpy.context.active_object
    seat.scale = (seat_size/2, seat_size/2, 0.03)
    seat.name = f"chair_{name}_seat"
    
    # Back
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, seat_size/2 - 0.02, seat_height + back_height/2))
    back = bpy.context.active_object
    back.scale = (seat_size/2, 0.02, back_height/2)
    back.name = f"chair_{name}_back"
    
    # Legs
    leg_positions = [
        (seat_size/2 - 0.04, seat_size/2 - 0.04),
        (-seat_size/2 + 0.04, seat_size/2 - 0.04),
        (seat_size/2 - 0.04, -seat_size/2 + 0.04),
        (-seat_size/2 + 0.04, -seat_size/2 + 0.04),
    ]
    
    legs = []
    for i, (lx, ly) in enumerate(leg_positions):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=seat_height - 0.03, location=(lx, ly, seat_height/2 - 0.015))
        leg = bpy.context.active_object
        leg.name = f"chair_{name}_leg_{i}"
        legs.append(leg)
    
    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    seat.select_set(True)
    back.select_set(True)
    for leg in legs:
        leg.select_set(True)
    bpy.context.view_layer.objects.active = seat
    bpy.ops.object.join()
    
    chair = bpy.context.active_object
    chair.name = f"chair_{name}"
    chair.location = location
    chair.rotation_euler.z = rotation_z
    
    # Apply material
    mat = bpy.data.materials.get("gm_leather_brown")
    if mat:
        chair.data.materials.append(mat)
    
    return chair


def create_bookshelf(name: str, location: tuple, rotation_z: float = 0) -> bpy.types.Object:
    """Create a bookshelf."""
    width = 1.0
    depth = 0.35
    height = 2.0
    shelf_count = 5
    thickness = 0.025
    
    parts = []
    
    # Side panels
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(side * (width/2 - thickness/2), 0, height/2))
        panel = bpy.context.active_object
        panel.scale = (thickness/2, depth/2, height/2)
        panel.name = f"bookshelf_{name}_side_{side}"
        parts.append(panel)
    
    # Shelves
    for i in range(shelf_count):
        z = (i / (shelf_count - 1)) * (height - thickness) + thickness/2
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
        shelf = bpy.context.active_object
        shelf.scale = (width/2 - thickness, depth/2, thickness/2)
        shelf.name = f"bookshelf_{name}_shelf_{i}"
        parts.append(shelf)
    
    # Back panel
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, depth/2 - 0.01, height/2))
    back = bpy.context.active_object
    back.scale = (width/2, 0.01, height/2)
    back.name = f"bookshelf_{name}_back"
    parts.append(back)
    
    # Join all parts
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    
    bookshelf = bpy.context.active_object
    bookshelf.name = f"bookshelf_{name}"
    bookshelf.location = location
    bookshelf.rotation_euler.z = rotation_z
    
    # Apply material
    mat = bpy.data.materials.get("gm_wood_shelf")
    if mat:
        bookshelf.data.materials.append(mat)
    
    return bookshelf


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def add_all_furniture():
    """Add furniture to all study positions."""
    print("\n" + "=" * 60)
    print("ADDING FURNITURE")
    print("=" * 60)
    
    # Get or create furniture collection
    furniture_col = bpy.data.collections.get("OL_Furniture")
    if not furniture_col:
        furniture_col = bpy.data.collections.new("OL_Furniture")
        bpy.context.scene.collection.children.link(furniture_col)
    
    # Clear existing furniture
    for obj in list(furniture_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    
    positions = get_study_positions()
    
    desks = []
    chairs = []
    
    print(f"\n📦 Creating furniture at {len(positions)} positions...")
    
    for i, pos in enumerate(positions):
        # Random rotation for variety
        rot = random.choice([0, pi/2, pi, 3*pi/2])
        
        # Create desk
        desk = create_desk(f"study_{i}", pos, rot)
        bpy.context.scene.collection.objects.unlink(desk)
        furniture_col.objects.link(desk)
        desks.append(desk)
        
        # Create chair (offset from desk)
        chair_offset = Vector((0, -0.6, 0))
        chair_offset.rotate(desk.rotation_euler)
        chair_pos = (pos[0] + chair_offset.x, pos[1] + chair_offset.y, pos[2])
        
        chair = create_chair(f"study_{i}", chair_pos, rot + pi)
        bpy.context.scene.collection.objects.unlink(chair)
        furniture_col.objects.link(chair)
        chairs.append(chair)
    
    # Add some bookshelves along walls
    print("\n📚 Adding bookshelves...")
    
    bookshelf_positions = [
        # Along wing ends
        (30, 0, 0, 0),
        (-30, 0, 0, pi),
        (0, 30, 0, -pi/2),
        (0, -30, 0, pi/2),
        # Along aisles
        (18, 12, 0, 0),
        (-18, 12, 0, pi),
        (18, -12, 0, 0),
        (-18, -12, 0, pi),
        (12, 18, 0, -pi/2),
        (-12, 18, 0, pi/2),
        (12, -18, 0, -pi/2),
        (-12, -18, 0, pi/2),
    ]
    
    bookshelves = []
    for i, (x, y, z, rot) in enumerate(bookshelf_positions):
        bs = create_bookshelf(f"wall_{i}", (x, y, z), rot)
        bpy.context.scene.collection.objects.unlink(bs)
        furniture_col.objects.link(bs)
        bookshelves.append(bs)
    
    print(f"\n✅ Furniture created:")
    print(f"   Desks: {len(desks)}")
    print(f"   Chairs: {len(chairs)}")
    print(f"   Bookshelves: {len(bookshelves)}")
    print("=" * 60 + "\n")
    
    return {
        "desks": desks,
        "chairs": chairs,
        "bookshelves": bookshelves,
    }


if __name__ == "__main__":
    add_all_furniture()

