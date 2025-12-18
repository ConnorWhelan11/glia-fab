"""
Gothic Kit Generator - Creates hyper-realistic architectural elements.

Generates procedural Gothic architectural pieces with proper proportions:
- Clustered piers with bases and capitals
- Ribbed vault segments
- Lancet windows with tracery
- Buttresses with proper profiles
- Arcade arches with moldings

Based on real Gothic architecture measurements (Notre Dame, Chartres, etc.)

Usage in Blender:
    exec(open("gothic_kit_generator.py").read())
    
Or:
    import gothic_kit_generator as kit
    kit.generate_all_pieces()
"""

import bpy
import bmesh
from math import pi, sin, cos, radians, sqrt
from mathutils import Vector, Matrix
from typing import List, Tuple, Optional


# =============================================================================
# ARCHITECTURAL CONSTANTS (Based on Gothic Proportions)
# =============================================================================

# Golden ratio and Gothic proportions
PHI = 1.618033988749895
GOTHIC_RATIO = 2.5  # Height to width for lancets

# Standard dimensions
PIER_BASE_HEIGHT = 0.4      # Plinth/base height
PIER_CAPITAL_HEIGHT = 0.35  # Capital zone height
COLUMN_SHAFT_TAPER = 0.95   # Slight taper ratio

# Molding profiles (depth from surface)
MOLDING_DEPTH_MAJOR = 0.08
MOLDING_DEPTH_MINOR = 0.04
FILLET_SIZE = 0.02

# Materials (will be created if not exist)
MATERIALS = {
    "stone_light": {"color": (0.75, 0.70, 0.62, 1), "roughness": 0.85},
    "stone_dark": {"color": (0.45, 0.42, 0.38, 1), "roughness": 0.75},
    "stone_weathered": {"color": (0.55, 0.52, 0.48, 1), "roughness": 0.95},
    "wood_dark": {"color": (0.25, 0.18, 0.12, 1), "roughness": 0.65},
    "brass_aged": {"color": (0.65, 0.55, 0.35, 1), "roughness": 0.45, "metallic": 0.8},
    "glass_stained": {"color": (0.3, 0.2, 0.5, 0.7), "roughness": 0.1, "transmission": 0.8},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_or_create_collection(name: str, parent=None):
    """Get or create a collection."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def get_or_create_material(name: str, config: dict):
    """Get or create a material with given config."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = config.get("color", (0.5, 0.5, 0.5, 1))
        bsdf.inputs["Roughness"].default_value = config.get("roughness", 0.5)
        if "metallic" in config:
            bsdf.inputs["Metallic"].default_value = config["metallic"]
        if "transmission" in config:
            bsdf.inputs["Transmission Weight"].default_value = config["transmission"]
    
    return mat


def create_mesh_object(name: str, mesh_data) -> bpy.types.Object:
    """Create a mesh object from bmesh data."""
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh_data.to_mesh(mesh)
    mesh_data.free()
    
    obj = bpy.data.objects.new(name, mesh)
    return obj


def add_loop_cut_profile(bm, edges, segments: int = 1):
    """Add loop cuts to edges for detail."""
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=segments)


# =============================================================================
# TIER 1: PRIMARY STRUCTURE (Massive, Load-Bearing)
# =============================================================================

def create_clustered_pier(
    name: str = "GK_ClusteredPier",
    height: float = 6.0,
    base_radius: float = 0.8,
    num_shafts: int = 8,
    with_base: bool = True,
    with_capital: bool = True,
) -> bpy.types.Object:
    """
    Create a clustered pier (compound pier) typical of Gothic architecture.
    
    These consist of a central core with attached colonettes (small shafts)
    that continue up to support individual vault ribs.
    """
    bm = bmesh.new()
    
    # Core cylinder
    core_radius = base_radius * 0.5
    shaft_radius = base_radius * 0.15
    shaft_offset = base_radius * 0.7
    
    shaft_height = height
    if with_base:
        shaft_height -= PIER_BASE_HEIGHT
    if with_capital:
        shaft_height -= PIER_CAPITAL_HEIGHT
    
    base_z = PIER_BASE_HEIGHT if with_base else 0
    
    # Create core shaft
    bmesh.ops.create_cone(
        bm,
        segments=16,
        radius1=core_radius,
        radius2=core_radius * COLUMN_SHAFT_TAPER,
        depth=shaft_height,
        cap_ends=True,
        cap_tris=False,
    )
    
    # Move core up
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, base_z + shaft_height / 2))
    
    # Add colonettes around the core
    for i in range(num_shafts):
        angle = (i / num_shafts) * 2 * pi
        x = cos(angle) * shaft_offset
        y = sin(angle) * shaft_offset
        
        # Create colonette
        col_bm = bmesh.new()
        bmesh.ops.create_cone(
            col_bm,
            segments=12,
            radius1=shaft_radius,
            radius2=shaft_radius * COLUMN_SHAFT_TAPER,
            depth=shaft_height,
            cap_ends=True,
            cap_tris=False,
        )
        
        # Move colonette
        bmesh.ops.translate(col_bm, verts=col_bm.verts, vec=(x, y, base_z + shaft_height / 2))
        
        # Merge into main bmesh
        temp_mesh = bpy.data.meshes.new("temp")
        col_bm.to_mesh(temp_mesh)
        col_bm.free()
        bm.from_mesh(temp_mesh)
        bpy.data.meshes.remove(temp_mesh)
    
    # Base (Attic base profile)
    if with_base:
        # Lower torus (large)
        base_bm = bmesh.new()
        bmesh.ops.create_cone(
            base_bm,
            segments=24,
            radius1=base_radius * 1.2,
            radius2=base_radius * 1.1,
            depth=PIER_BASE_HEIGHT * 0.4,
            cap_ends=True,
        )
        bmesh.ops.translate(base_bm, verts=base_bm.verts, vec=(0, 0, PIER_BASE_HEIGHT * 0.2))
        
        # Upper scotia (concave)
        bmesh.ops.create_cone(
            base_bm,
            segments=24,
            radius1=base_radius * 1.1,
            radius2=base_radius * 1.0,
            depth=PIER_BASE_HEIGHT * 0.3,
            cap_ends=True,
        )
        bmesh.ops.translate(
            base_bm, 
            verts=[v for v in base_bm.verts if v.co.z > PIER_BASE_HEIGHT * 0.3],
            vec=(0, 0, PIER_BASE_HEIGHT * 0.5)
        )
        
        # Plinth (square base)
        bmesh.ops.create_cube(base_bm, size=base_radius * 2.4)
        for v in base_bm.verts:
            if abs(v.co.z) > base_radius:
                v.co.z = 0.05 if v.co.z > 0 else -0.05
        bmesh.ops.translate(
            base_bm,
            verts=[v for v in base_bm.verts if v.co.z < 0.1],
            vec=(0, 0, 0.05)
        )
        
        temp_mesh = bpy.data.meshes.new("temp")
        base_bm.to_mesh(temp_mesh)
        base_bm.free()
        bm.from_mesh(temp_mesh)
        bpy.data.meshes.remove(temp_mesh)
    
    # Capital (simplified Gothic capital)
    if with_capital:
        cap_z = base_z + shaft_height
        cap_bm = bmesh.new()
        
        # Abacus (top square slab)
        bmesh.ops.create_cube(cap_bm, size=base_radius * 2.2)
        for v in cap_bm.verts:
            v.co.z = v.co.z * 0.15 + cap_z + PIER_CAPITAL_HEIGHT - 0.05
        
        # Bell (curved transition)
        bmesh.ops.create_cone(
            cap_bm,
            segments=24,
            radius1=base_radius * 0.9,
            radius2=base_radius * 1.1,
            depth=PIER_CAPITAL_HEIGHT * 0.6,
            cap_ends=True,
        )
        bmesh.ops.translate(
            cap_bm,
            verts=[v for v in cap_bm.verts if v.co.z < cap_z + PIER_CAPITAL_HEIGHT * 0.5],
            vec=(0, 0, cap_z + PIER_CAPITAL_HEIGHT * 0.35)
        )
        
        # Necking (thin ring)
        bmesh.ops.create_cone(
            cap_bm,
            segments=24,
            radius1=base_radius * 0.85,
            radius2=base_radius * 0.85,
            depth=PIER_CAPITAL_HEIGHT * 0.15,
            cap_ends=True,
        )
        bmesh.ops.translate(
            cap_bm,
            verts=[v for v in cap_bm.verts if v.co.z < 0.1],
            vec=(0, 0, cap_z + 0.05)
        )
        
        temp_mesh = bpy.data.meshes.new("temp")
        cap_bm.to_mesh(temp_mesh)
        cap_bm.free()
        bm.from_mesh(temp_mesh)
        bpy.data.meshes.remove(temp_mesh)
    
    obj = create_mesh_object(name, bm)
    
    # Add material
    mat = get_or_create_material("stone_light", MATERIALS["stone_light"])
    obj.data.materials.append(mat)
    
    return obj


def create_crossing_arch(
    name: str = "GK_CrossingArch",
    span: float = 12.0,
    rise: float = 8.0,
    depth: float = 1.2,
    num_orders: int = 3,
) -> bpy.types.Object:
    """
    Create a major crossing arch with multiple orders (receding moldings).
    
    Gothic arches use pointed (ogival) profiles. Each "order" is a step
    back in the arch, creating depth and shadow lines.
    """
    bm = bmesh.new()
    
    half_span = span / 2
    segments = 24
    
    # Pointed arch profile (two arcs meeting at apex)
    # The center of each arc is at the opposite springer
    def get_arch_point(t: float, radius_offset: float = 0) -> Tuple[float, float]:
        """Get point on pointed arch. t goes 0->1 from left to apex to right."""
        r = half_span + radius_offset
        
        if t <= 0.5:
            # Left arc (center at right springer)
            angle = pi - (t * 2) * (pi / 2 + 0.3)  # Slightly more than 90 degrees
            cx = half_span  # Center at right
            x = cx + r * cos(angle)
            y = r * sin(angle)
        else:
            # Right arc (center at left springer)
            angle = (t - 0.5) * 2 * (pi / 2 + 0.3)
            cx = -half_span  # Center at left
            x = cx + r * cos(angle)
            y = r * sin(angle)
        
        return x, max(0, y)
    
    # Create each order
    for order in range(num_orders):
        order_offset = order * 0.15  # Step back
        order_depth = depth - order * 0.1
        z_offset = order * 0.05  # Slight height variation
        
        # Create arch profile as vertices
        verts = []
        for i in range(segments + 1):
            t = i / segments
            x, y = get_arch_point(t, -order_offset)
            
            # Front face
            verts.append(bm.verts.new((x, -order_depth / 2, y + z_offset)))
            # Back face
            verts.append(bm.verts.new((x, order_depth / 2, y + z_offset)))
        
        bm.verts.ensure_lookup_table()
        
        # Create faces between front and back
        for i in range(segments):
            idx = order * (segments + 1) * 2 + i * 2
            try:
                # Quad between this segment and next
                v1 = verts[i * 2]
                v2 = verts[i * 2 + 1]
                v3 = verts[i * 2 + 3]
                v4 = verts[i * 2 + 2]
                bm.faces.new([v1, v2, v3, v4])
            except (IndexError, ValueError):
                pass
    
    # Clean up
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_light", MATERIALS["stone_light"])
    obj.data.materials.append(mat)
    
    return obj


def create_vault_rib(
    name: str = "GK_VaultRib",
    span: float = 6.0,
    rise: float = 2.0,
    rib_width: float = 0.25,
    rib_depth: float = 0.35,
) -> bpy.types.Object:
    """
    Create a vault rib (the structural ribs that support Gothic vaults).
    
    Ribs have a molded profile and follow an arc across the vault bay.
    """
    bm = bmesh.new()
    
    segments = 16
    half_span = span / 2
    
    # Rib profile (cross-section) - pointed with filleted edges
    profile_points = [
        (-rib_width / 2, 0),
        (-rib_width / 2, rib_depth * 0.6),
        (-rib_width / 4, rib_depth * 0.85),
        (0, rib_depth),  # Peak
        (rib_width / 4, rib_depth * 0.85),
        (rib_width / 2, rib_depth * 0.6),
        (rib_width / 2, 0),
    ]
    
    # Create rib along arc
    for i in range(segments + 1):
        t = i / segments
        # Parabolic arc
        x = (t - 0.5) * span
        z = rise * (1 - (2 * t - 1) ** 2)  # Parabola
        
        # Direction tangent for orienting profile
        if i < segments:
            t_next = (i + 1) / segments
            x_next = (t_next - 0.5) * span
            z_next = rise * (1 - (2 * t_next - 1) ** 2)
            dx = x_next - x
            dz = z_next - z
        else:
            dx = span / segments
            dz = -rise * 4 / segments
        
        # Normalize and get perpendicular
        length = sqrt(dx * dx + dz * dz)
        if length > 0:
            dx /= length
            dz /= length
        
        # Create profile at this point
        for px, py in profile_points:
            # Rotate profile to align with arc
            vx = x + px * dz  # Perpendicular in XZ plane
            vz = z + py
            bm.verts.new((vx, 0, vz))
    
    bm.verts.ensure_lookup_table()
    
    # Create faces
    n_profile = len(profile_points)
    for i in range(segments):
        for j in range(n_profile - 1):
            idx = i * n_profile + j
            try:
                v1 = bm.verts[idx]
                v2 = bm.verts[idx + 1]
                v3 = bm.verts[idx + n_profile + 1]
                v4 = bm.verts[idx + n_profile]
                bm.faces.new([v1, v2, v3, v4])
            except (IndexError, ValueError):
                pass
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_light", MATERIALS["stone_light"])
    obj.data.materials.append(mat)
    
    return obj


# =============================================================================
# TIER 2: SECONDARY STRUCTURE (Arcade, Mezzanine)
# =============================================================================

def create_arcade_column(
    name: str = "GK_ArcadeColumn",
    height: float = 5.0,
    radius: float = 0.3,
    with_base: bool = True,
    with_capital: bool = True,
) -> bpy.types.Object:
    """
    Create a simpler arcade column (smaller than clustered piers).
    
    Used in the triforium/gallery level and between main piers.
    """
    bm = bmesh.new()
    
    shaft_height = height
    base_h = 0.25 if with_base else 0
    cap_h = 0.2 if with_capital else 0
    shaft_height -= (base_h + cap_h)
    
    # Shaft with entasis (slight bulge)
    segments_v = 8
    segments_h = 16
    
    for i in range(segments_v + 1):
        t = i / segments_v
        z = base_h + t * shaft_height
        
        # Entasis curve (subtle bulge at 1/3 height)
        entasis = 1.0 + 0.02 * sin(t * pi)
        r = radius * entasis * (1.0 - t * (1 - COLUMN_SHAFT_TAPER))
        
        for j in range(segments_h):
            angle = (j / segments_h) * 2 * pi
            x = cos(angle) * r
            y = sin(angle) * r
            bm.verts.new((x, y, z))
    
    bm.verts.ensure_lookup_table()
    
    # Create faces
    for i in range(segments_v):
        for j in range(segments_h):
            idx = i * segments_h + j
            next_j = (j + 1) % segments_h
            
            v1 = bm.verts[idx]
            v2 = bm.verts[i * segments_h + next_j]
            v3 = bm.verts[(i + 1) * segments_h + next_j]
            v4 = bm.verts[(i + 1) * segments_h + j]
            
            bm.faces.new([v1, v2, v3, v4])
    
    # Base
    if with_base:
        bmesh.ops.create_cone(
            bm,
            segments=segments_h,
            radius1=radius * 1.3,
            radius2=radius * 1.1,
            depth=base_h,
            cap_ends=True,
        )
        # Move base down
        for v in bm.verts:
            if v.co.z < base_h * 0.6:
                v.co.z += base_h / 2
    
    # Capital
    if with_capital:
        cap_bm = bmesh.new()
        bmesh.ops.create_cone(
            cap_bm,
            segments=segments_h,
            radius1=radius * 0.95,
            radius2=radius * 1.25,
            depth=cap_h,
            cap_ends=True,
        )
        bmesh.ops.translate(cap_bm, verts=cap_bm.verts, vec=(0, 0, height - cap_h / 2))
        
        temp = bpy.data.meshes.new("temp")
        cap_bm.to_mesh(temp)
        cap_bm.free()
        bm.from_mesh(temp)
        bpy.data.meshes.remove(temp)
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_light", MATERIALS["stone_light"])
    obj.data.materials.append(mat)
    
    return obj


def create_buttress(
    name: str = "GK_Buttress",
    height: float = 10.0,
    width: float = 1.2,
    depth: float = 2.0,
    num_setbacks: int = 3,
) -> bpy.types.Object:
    """
    Create a stepped buttress with setbacks at each level.
    
    Gothic buttresses step back as they rise, with weathering slopes.
    """
    bm = bmesh.new()
    
    setback_height = height / (num_setbacks + 1)
    current_depth = depth
    current_width = width
    
    for level in range(num_setbacks + 1):
        z_base = level * setback_height
        z_top = (level + 1) * setback_height
        
        # Main mass
        verts = [
            bm.verts.new((-current_width / 2, 0, z_base)),
            bm.verts.new((current_width / 2, 0, z_base)),
            bm.verts.new((current_width / 2, -current_depth, z_base)),
            bm.verts.new((-current_width / 2, -current_depth, z_base)),
            bm.verts.new((-current_width / 2, 0, z_top)),
            bm.verts.new((current_width / 2, 0, z_top)),
            bm.verts.new((current_width / 2, -current_depth, z_top)),
            bm.verts.new((-current_width / 2, -current_depth, z_top)),
        ]
        
        # Create faces
        # Bottom
        bm.faces.new([verts[0], verts[1], verts[2], verts[3]])
        # Top
        bm.faces.new([verts[7], verts[6], verts[5], verts[4]])
        # Sides
        bm.faces.new([verts[0], verts[4], verts[5], verts[1]])
        bm.faces.new([verts[1], verts[5], verts[6], verts[2]])
        bm.faces.new([verts[2], verts[6], verts[7], verts[3]])
        bm.faces.new([verts[3], verts[7], verts[4], verts[0]])
        
        # Setback for next level
        current_depth *= 0.85
        current_width *= 0.9
    
    # Cap/finial
    cap_height = 0.4
    bmesh.ops.create_cone(
        bm,
        segments=4,
        radius1=current_width * 0.6,
        radius2=0.05,
        depth=cap_height,
        cap_ends=True,
    )
    # Rotate to align with buttress
    for v in bm.verts:
        if v.co.z > height - 0.1:
            v.co.z += cap_height / 2
            v.co.y -= current_depth / 2
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_weathered", MATERIALS["stone_weathered"])
    obj.data.materials.append(mat)
    
    return obj


# =============================================================================
# TIER 3: TERTIARY ELEMENTS (Windows, Tracery, Decorative)
# =============================================================================

def create_lancet_window(
    name: str = "GK_LancetWindow",
    width: float = 1.2,
    height: float = 4.0,
    depth: float = 0.4,
    with_tracery: bool = True,
) -> bpy.types.Object:
    """
    Create a lancet (pointed arch) window with optional tracery.
    
    Lancets are tall, narrow windows with pointed tops - the signature
    Gothic window shape.
    """
    bm = bmesh.new()
    
    half_w = width / 2
    straight_height = height * 0.6  # Portion below the arch
    arch_height = height * 0.4
    
    segments = 16
    
    # Window opening (negative space frame)
    # Front frame
    frame_thickness = 0.08
    
    # Create outer profile
    outer_verts = []
    
    # Bottom corners
    outer_verts.append((-half_w, 0))
    
    # Left side up
    outer_verts.append((-half_w, straight_height))
    
    # Arch (pointed)
    for i in range(segments + 1):
        t = i / segments
        if t <= 0.5:
            # Left arc
            angle = pi - t * pi
            x = -half_w + half_w * (1 - cos(angle))
            y = straight_height + arch_height * sin(angle) * (2 * t)
        else:
            # Right arc
            angle = (t - 0.5) * pi
            x = half_w * cos(angle)
            y = straight_height + arch_height * sin(angle) * (2 * (1 - t))
        outer_verts.append((x, y))
    
    # Right side down
    outer_verts.append((half_w, straight_height))
    outer_verts.append((half_w, 0))
    
    # Create front face vertices
    for x, y in outer_verts:
        bm.verts.new((x, -depth / 2, y))
        bm.verts.new((x, depth / 2, y))
    
    bm.verts.ensure_lookup_table()
    
    # Create faces
    n = len(outer_verts)
    for i in range(n - 1):
        idx = i * 2
        try:
            v1 = bm.verts[idx]
            v2 = bm.verts[idx + 1]
            v3 = bm.verts[idx + 3]
            v4 = bm.verts[idx + 2]
            bm.faces.new([v1, v2, v3, v4])
        except (IndexError, ValueError):
            pass
    
    # Tracery (simplified geometric pattern)
    if with_tracery:
        # Central mullion
        mullion_width = 0.05
        mullion_verts = [
            bm.verts.new((-mullion_width, 0, 0)),
            bm.verts.new((mullion_width, 0, 0)),
            bm.verts.new((mullion_width, 0, straight_height + arch_height * 0.7)),
            bm.verts.new((-mullion_width, 0, straight_height + arch_height * 0.7)),
        ]
        bm.faces.new(mullion_verts)
        
        # Horizontal bar
        bar_height = straight_height * 0.7
        bar_verts = [
            bm.verts.new((-half_w * 0.9, 0, bar_height - mullion_width)),
            bm.verts.new((half_w * 0.9, 0, bar_height - mullion_width)),
            bm.verts.new((half_w * 0.9, 0, bar_height + mullion_width)),
            bm.verts.new((-half_w * 0.9, 0, bar_height + mullion_width)),
        ]
        bm.faces.new(bar_verts)
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_dark", MATERIALS["stone_dark"])
    obj.data.materials.append(mat)
    
    return obj


def create_rose_window(
    name: str = "GK_RoseWindow",
    radius: float = 3.0,
    depth: float = 0.5,
    num_petals: int = 12,
) -> bpy.types.Object:
    """
    Create a rose window (circular window with radiating tracery).
    
    Rose windows are the iconic circular windows found above portals
    and at transept ends.
    """
    bm = bmesh.new()
    
    # Outer ring
    outer_segments = 32
    inner_radius = radius * 0.9
    
    for i in range(outer_segments):
        angle = (i / outer_segments) * 2 * pi
        
        # Outer edge
        bm.verts.new((cos(angle) * radius, -depth / 2, sin(angle) * radius))
        bm.verts.new((cos(angle) * radius, depth / 2, sin(angle) * radius))
        
        # Inner edge
        bm.verts.new((cos(angle) * inner_radius, -depth / 2, sin(angle) * inner_radius))
        bm.verts.new((cos(angle) * inner_radius, depth / 2, sin(angle) * inner_radius))
    
    bm.verts.ensure_lookup_table()
    
    # Create ring faces
    for i in range(outer_segments):
        next_i = (i + 1) % outer_segments
        idx = i * 4
        next_idx = next_i * 4
        
        # Outer surface
        bm.faces.new([
            bm.verts[idx], bm.verts[idx + 1],
            bm.verts[next_idx + 1], bm.verts[next_idx]
        ])
        
        # Inner surface
        bm.faces.new([
            bm.verts[idx + 2], bm.verts[next_idx + 2],
            bm.verts[next_idx + 3], bm.verts[idx + 3]
        ])
        
        # Front
        bm.faces.new([
            bm.verts[idx], bm.verts[next_idx],
            bm.verts[next_idx + 2], bm.verts[idx + 2]
        ])
        
        # Back
        bm.faces.new([
            bm.verts[idx + 1], bm.verts[idx + 3],
            bm.verts[next_idx + 3], bm.verts[next_idx + 1]
        ])
    
    # Radial spokes (tracery)
    spoke_width = 0.06
    hub_radius = radius * 0.15
    
    base_vert_count = len(bm.verts)
    
    for i in range(num_petals):
        angle = (i / num_petals) * 2 * pi
        
        # Spoke from hub to inner ring
        x_dir = cos(angle)
        z_dir = sin(angle)
        
        # Create spoke as thin box
        spoke_verts = [
            bm.verts.new((x_dir * hub_radius - z_dir * spoke_width, 0, 
                         z_dir * hub_radius + x_dir * spoke_width)),
            bm.verts.new((x_dir * hub_radius + z_dir * spoke_width, 0,
                         z_dir * hub_radius - x_dir * spoke_width)),
            bm.verts.new((x_dir * inner_radius + z_dir * spoke_width, 0,
                         z_dir * inner_radius - x_dir * spoke_width)),
            bm.verts.new((x_dir * inner_radius - z_dir * spoke_width, 0,
                         z_dir * inner_radius + x_dir * spoke_width)),
        ]
        bm.faces.new(spoke_verts)
    
    # Central hub
    bmesh.ops.create_cone(
        bm,
        segments=num_petals,
        radius1=hub_radius,
        radius2=hub_radius,
        depth=depth * 0.8,
        cap_ends=True,
    )
    # Rotate hub to face forward
    for v in bm.verts:
        if v.index >= base_vert_count + num_petals * 4:
            # Rotate 90 degrees around X
            old_y = v.co.y
            old_z = v.co.z
            v.co.y = -old_z
            v.co.z = old_y
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_dark", MATERIALS["stone_dark"])
    obj.data.materials.append(mat)
    
    return obj


def create_balustrade_section(
    name: str = "GK_Balustrade",
    length: float = 6.0,
    height: float = 1.1,
    num_balusters: int = 8,
) -> bpy.types.Object:
    """
    Create a balustrade (railing) section with balusters.
    """
    bm = bmesh.new()
    
    rail_height = 0.08
    rail_width = 0.12
    baluster_radius = 0.04
    
    # Top rail
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= length / 2
        v.co.y *= rail_width / 2
        v.co.z = v.co.z * rail_height / 2 + height - rail_height / 2
    
    # Bottom rail
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        if v.co.z < height * 0.5:  # Only the new cube
            v.co.x *= length / 2
            v.co.y *= rail_width / 2
            v.co.z = v.co.z * rail_height / 2 + rail_height / 2
    
    # Balusters
    spacing = length / (num_balusters + 1)
    baluster_height = height - rail_height * 2
    
    for i in range(num_balusters):
        x = -length / 2 + spacing * (i + 1)
        
        # Simple turned baluster
        col_bm = bmesh.new()
        
        # Base bulge
        bmesh.ops.create_cone(
            col_bm,
            segments=8,
            radius1=baluster_radius * 0.8,
            radius2=baluster_radius * 1.2,
            depth=baluster_height * 0.15,
            cap_ends=True,
        )
        
        # Shaft
        bmesh.ops.create_cone(
            col_bm,
            segments=8,
            radius1=baluster_radius,
            radius2=baluster_radius * 0.9,
            depth=baluster_height * 0.7,
            cap_ends=True,
        )
        
        # Move to position
        bmesh.ops.translate(col_bm, verts=col_bm.verts, vec=(x, 0, rail_height + baluster_height / 2))
        
        temp = bpy.data.meshes.new("temp")
        col_bm.to_mesh(temp)
        col_bm.free()
        bm.from_mesh(temp)
        bpy.data.meshes.remove(temp)
    
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    obj = create_mesh_object(name, bm)
    
    mat = get_or_create_material("stone_dark", MATERIALS["stone_dark"])
    obj.data.materials.append(mat)
    
    return obj


# =============================================================================
# MAIN GENERATION FUNCTION
# =============================================================================

def generate_all_pieces(collection_name: str = "OL_Gothic_Kit"):
    """Generate all Gothic kit pieces and organize in a collection."""
    
    print("\n" + "=" * 60)
    print("GOTHIC KIT GENERATOR")
    print("=" * 60)
    
    # Create collection
    kit_col = get_or_create_collection(collection_name)
    
    # Clear existing
    for obj in list(kit_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    
    # Create materials first
    print("\n📦 Creating materials...")
    for mat_name, config in MATERIALS.items():
        get_or_create_material(mat_name, config)
        print(f"   ✅ {mat_name}")
    
    # Generate pieces by tier
    pieces = {}
    
    # TIER 1: Primary Structure
    print("\n🏛️ TIER 1: Primary Structure")
    
    pieces["GK_ClusteredPier_Large"] = create_clustered_pier(
        "GK_ClusteredPier_Large", height=6.0, base_radius=0.8, num_shafts=8
    )
    print("   ✅ Clustered Pier (Large)")
    
    pieces["GK_ClusteredPier_Small"] = create_clustered_pier(
        "GK_ClusteredPier_Small", height=5.0, base_radius=0.6, num_shafts=4
    )
    print("   ✅ Clustered Pier (Small)")
    
    pieces["GK_CrossingArch"] = create_crossing_arch(
        "GK_CrossingArch", span=12.0, rise=8.0, depth=1.2, num_orders=3
    )
    print("   ✅ Crossing Arch")
    
    pieces["GK_VaultRib"] = create_vault_rib(
        "GK_VaultRib", span=6.0, rise=2.0
    )
    print("   ✅ Vault Rib")
    
    # TIER 2: Secondary Structure
    print("\n🏗️ TIER 2: Secondary Structure")
    
    pieces["GK_ArcadeColumn"] = create_arcade_column(
        "GK_ArcadeColumn", height=5.0, radius=0.3
    )
    print("   ✅ Arcade Column")
    
    pieces["GK_Buttress"] = create_buttress(
        "GK_Buttress", height=10.0, width=1.2, depth=2.0
    )
    print("   ✅ Buttress")
    
    # TIER 3: Tertiary Elements
    print("\n✨ TIER 3: Tertiary Elements")
    
    pieces["GK_LancetWindow"] = create_lancet_window(
        "GK_LancetWindow", width=1.2, height=4.0, with_tracery=True
    )
    print("   ✅ Lancet Window")
    
    pieces["GK_LancetWindow_Small"] = create_lancet_window(
        "GK_LancetWindow_Small", width=0.8, height=2.5, with_tracery=False
    )
    print("   ✅ Lancet Window (Small)")
    
    pieces["GK_RoseWindow"] = create_rose_window(
        "GK_RoseWindow", radius=3.0, num_petals=12
    )
    print("   ✅ Rose Window")
    
    pieces["GK_Balustrade"] = create_balustrade_section(
        "GK_Balustrade", length=6.0, height=1.1
    )
    print("   ✅ Balustrade")
    
    # Link all to collection and arrange for display
    print("\n📐 Arranging pieces...")
    x_offset = 0
    for name, obj in pieces.items():
        kit_col.objects.link(obj)
        obj.location.x = x_offset
        x_offset += 4  # Spacing
    
    # Summary
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"   Created {len(pieces)} kit pieces in '{collection_name}'")
    print("   Pieces:")
    for name in pieces.keys():
        print(f"      - {name}")
    print("=" * 60 + "\n")
    
    return pieces


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    generate_all_pieces()

