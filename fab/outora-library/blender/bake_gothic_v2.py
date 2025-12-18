"""
Bake Gothic Layout V2 - Convert layout positions to instanced geometry.

This script reads the positions from sverchok_layout_v2.py and instances
the appropriate kit pieces from the OL_Assets collection.

Run in Blender after loading outora_library_v0.x.blend:
    exec(open("bake_gothic_v2.py").read())

Or:
    import importlib
    import bake_gothic_v2
    importlib.reload(bake_gothic_v2)
    bake_gothic_v2.bake_all()
"""

import bpy
import mathutils
import importlib
from math import pi, radians
from pathlib import Path
import sys

# Add the blender scripts directory to path
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import the layout generator
try:
    import sverchok_layout_v2 as layout

    importlib.reload(layout)
except ImportError:
    from . import sverchok_layout_v2 as layout


# =============================================================================
# KIT PIECE MAPPING
# =============================================================================

# Structural Hierarchy Tiers:
#   TIER 1 (Primary): Main load-bearing elements - clustered piers, crossing arches
#   TIER 2 (Secondary): Arcade columns, buttresses, nave arches
#   TIER 3 (Tertiary): Windows, tracery, balustrades, decorative elements

# Map layout output types to kit piece object names
# Priority: GK_ (Gothic Kit generated) > GIK_ (Gothic Interior Kit) > ol_ (Outora Library)
KIT_MAPPING = {
    # =========================================================================
    # TIER 1: PRIMARY STRUCTURE (Massive, Load-Bearing)
    # =========================================================================
    "main_piers": {
        "source": "GK_ClusteredPier_Large",  # Generated Gothic kit
        "fallback": "GIK_Pier_Large",
        "scale": (1.0, 1.0, 1.0),
        "tier": 1,
        "description": "Clustered compound piers at crossing and major intersections",
    },
    "crossing_arches": {
        "source": "GK_CrossingArch",
        "fallback": "GIK_Arch1",
        "scale": (1.0, 1.0, 1.0),
        "tier": 1,
        "description": "The four great arches framing the central crossing",
    },
    "transverse_ribs": {
        "source": "GK_VaultRib",
        "fallback": "ol_arch",
        "scale": (1.0, 1.0, 1.0),
        "tier": 1,
        "description": "Vault ribs spanning across bays",
    },
    # =========================================================================
    # TIER 2: SECONDARY STRUCTURE (Arcade, Mezzanine Support)
    # =========================================================================
    "arcade_columns": {
        "source": "GK_ArcadeColumn",
        "fallback": "GK_ClusteredPier_Small",
        "scale": (1.0, 1.0, 1.0),
        "tier": 2,
        "description": "Columns in the triforium/gallery arcade",
    },
    "buttresses": {
        "source": "GK_Buttress",
        "fallback": "Cube.006",
        "scale": (1.0, 1.0, 1.0),
        "tier": 2,
        "description": "External buttresses providing lateral thrust resistance",
    },
    "nave_arches": {
        "source": "GK_CrossingArch",  # Reuse with smaller scale
        "fallback": "GIK_Arch1",
        "scale": (0.7, 0.7, 0.7),
        "tier": 2,
        "description": "Arcade arches along the nave",
    },
    "exterior_walls": {
        "source": "GIK_Wall",
        "fallback": "Wall2",
        "scale": (1.0, 1.0, 1.0),
        "tier": 2,
        "description": "Exterior wall sections between buttresses",
    },
    "clerestory_walls": {
        "source": "GIK_UpperWall.001",
        "fallback": "Plane.006",
        "scale": (1.0, 1.0, 0.5),
        "tier": 2,
        "description": "Upper walls in the clerestory zone",
    },
    # =========================================================================
    # TIER 3: TERTIARY ELEMENTS (Windows, Railings, Decorative)
    # =========================================================================
    "lancet_windows_ground": {
        "source": "GK_LancetWindow",
        "fallback": "GIK_Window",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Ground floor lancet windows with tracery",
    },
    "lancet_windows_clerestory": {
        "source": "GK_LancetWindow_Small",
        "fallback": "MinWindow",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Clerestory lancet windows (smaller)",
    },
    "rose_windows": {
        "source": "GK_RoseWindow",
        "fallback": "GIK_Window",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Rose windows at wing terminations",
    },
    "balustrades": {
        "source": "GK_Balustrade",
        "fallback": "GIK_LongStair1",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Mezzanine railings with balusters",
    },
    # =========================================================================
    # FLOORS AND HORIZONTAL SURFACES
    # =========================================================================
    "ground_floor": {
        "source": "ol_floor_tile",
        "fallback": None,
        "scale": (6.0, 6.0, 0.1),
        "tier": 2,
        "description": "Ground floor tiles (6m x 6m bays)",
    },
    "mezzanine_floor": {
        "source": "ol_mezzanine_tile",
        "fallback": None,
        "scale": (6.0, 6.0, 0.15),
        "tier": 2,
        "description": "Mezzanine/gallery floor tiles",
    },
    "mezzanine_beams": {
        "source": "ol_beam",
        "fallback": None,
        "scale": (6.0, 0.3, 0.4),
        "tier": 2,
        "description": "Underslung support beams for mezzanine",
    },
    # =========================================================================
    # CIRCULATION
    # =========================================================================
    "grand_stairs": {
        "source": "GIK_LongStair1",
        "fallback": "GIK_CornerStair1",
        "scale": (1.0, 1.0, 1.0),
        "tier": 2,
        "description": "Grand stairs at crossing corners",
    },
    "spiral_stairs": {
        "source": "GIK_CornerStair1",
        "fallback": None,
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Service/spiral stairs in wing corners",
    },
    # =========================================================================
    # FURNITURE AND STUDY SPACES
    # =========================================================================
    "study_pod_positions": {
        "source": "StudyPod_Template",
        "fallback": "ol_desk",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Study pod positions (desk + chair + shelves)",
    },
    "shelf_wall_positions": {
        "source": "ol_shelf_wall",
        "fallback": "ol_bookshelf",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Wall-mounted bookshelves",
    },
    "reading_alcove_positions": {
        "source": "ol_reading_alcove",
        "fallback": "ol_desk",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Reading nook alcoves at wing ends",
    },
    # =========================================================================
    # DECORATIVE ELEMENTS
    # =========================================================================
    "statue_positions": {
        "source": "Statue1",
        "fallback": "Statue2",
        "scale": (1.0, 1.0, 1.0),
        "tier": 3,
        "description": "Guardian statues at thresholds",
    },
    "plinth_positions": {
        "source": "ol_plinth",
        "fallback": None,
        "scale": (0.8, 0.8, 0.6),
        "tier": 3,
        "description": "Statue bases/plinths",
    },
    "chandelier_positions": {
        "source": "ol_chandelier",
        "fallback": None,
        "scale": (2.0, 2.0, 2.0),
        "tier": 3,
        "description": "Hanging chandeliers/light fixtures",
    },
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


def clear_collection(col):
    """Remove all objects from a collection."""
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def find_source_object(primary: str, fallback: str = None):
    """Find a source object for instancing."""
    # Check all collections
    obj = bpy.data.objects.get(primary)
    if obj:
        return obj

    if fallback:
        obj = bpy.data.objects.get(fallback)
        if obj:
            return obj

    return None


def create_procedural_mesh(name: str, mesh_type: str, size: tuple):
    """Create a simple procedural mesh for elements without kit pieces."""
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj = bpy.data.objects.new(name, mesh)

    import bmesh

    bm = bmesh.new()

    if mesh_type == "floor":
        # Simple plane
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size[0] / 2)
    elif mesh_type == "beam":
        # Box
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    elif mesh_type == "column":
        # Cylinder
        bmesh.ops.create_cone(
            bm,
            segments=16,
            radius1=size[0],
            radius2=size[0],
            depth=size[2],
            cap_ends=True,
            cap_tris=False,
        )
    elif mesh_type == "plinth":
        # Tapered box
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    else:
        # Default cube
        bmesh.ops.create_cube(bm, size=size[0])

    bm.to_mesh(mesh)
    bm.free()

    return obj


def instance_at_matrices(
    source_obj, matrices, collection, name_prefix: str, base_scale: tuple = (1, 1, 1)
):
    """Create instances of source_obj at the given matrices."""
    instances = []

    for i, mat in enumerate(matrices):
        # Create linked duplicate (instance)
        instance = bpy.data.objects.new(f"{name_prefix}_{i:04d}", source_obj.data)

        # Apply matrix
        instance.matrix_world = mat

        # Apply additional scale
        instance.scale = (
            instance.scale[0] * base_scale[0],
            instance.scale[1] * base_scale[1],
            instance.scale[2] * base_scale[2],
        )

        # Link to collection
        collection.objects.link(instance)
        instances.append(instance)

    return instances


# =============================================================================
# MAIN BAKING FUNCTIONS
# =============================================================================


def bake_element(
    element_name: str, matrices: list, parent_col, kit_config: dict, stats: dict
):
    """Bake a single element type."""
    if not matrices:
        return

    # Get or create sub-collection
    col = get_or_create_collection(f"OL_{element_name}", parent_col)
    clear_collection(col)

    # Find source object
    source = find_source_object(kit_config.get("source"), kit_config.get("fallback"))

    if source:
        # Instance from kit piece
        instances = instance_at_matrices(
            source, matrices, col, element_name, kit_config.get("scale", (1, 1, 1))
        )
        stats["instanced"] += len(instances)
        print(f"   ✅ {element_name}: {len(instances)} instances from '{source.name}'")
    else:
        # Create procedural fallback
        print(
            f"   ⚠️ {element_name}: No source found, creating procedural ({len(matrices)} positions)"
        )

        scale = kit_config.get("scale", (1, 1, 1))

        # Determine mesh type
        if "floor" in element_name.lower():
            mesh_type = "floor"
        elif "beam" in element_name.lower():
            mesh_type = "beam"
        elif "column" in element_name.lower() or "pier" in element_name.lower():
            mesh_type = "column"
        elif "plinth" in element_name.lower():
            mesh_type = "plinth"
        else:
            mesh_type = "cube"

        # Create a single source and instance it
        proc_source = create_procedural_mesh(f"proc_{element_name}", mesh_type, scale)
        col.objects.link(proc_source)
        proc_source.hide_set(True)  # Hide the source

        instances = instance_at_matrices(
            proc_source, matrices, col, element_name, (1, 1, 1)
        )
        stats["procedural"] += len(instances)


def bake_all(clear_existing: bool = True):
    """
    Generate the layout and bake all elements.
    """
    print("\n" + "=" * 60)
    print("BAKING GOTHIC LAYOUT V2")
    print("=" * 60 + "\n")

    # Generate layout
    print("📐 Generating layout positions...")
    generator = layout.GothicLayoutGenerator()
    outputs = generator.generate()

    # Create root collection
    root_col = get_or_create_collection("OL_Gothic_Baked")

    if clear_existing:
        # Clear all child collections
        for child in list(root_col.children):
            clear_collection(child)
            bpy.data.collections.remove(child)
        clear_collection(root_col)

    # Stats
    stats = {"instanced": 0, "procedural": 0}

    # Bake each element type
    print("\n🏗️ Baking elements...")

    for element_name, matrices in outputs.items():
        if element_name in KIT_MAPPING:
            bake_element(
                element_name, matrices, root_col, KIT_MAPPING[element_name], stats
            )
        else:
            print(f"   ❌ {element_name}: No kit mapping defined")

    # Summary
    print("\n" + "=" * 60)
    print("BAKE COMPLETE")
    print("=" * 60)
    print(f"   Instanced from kit: {stats['instanced']}")
    print(f"   Procedural fallbacks: {stats['procedural']}")
    print(f"   Total objects: {stats['instanced'] + stats['procedural']}")
    print("=" * 60 + "\n")

    return outputs


def bake_floors_only():
    """Bake just the floor elements for quick preview."""
    print("📐 Generating floor layout...")
    generator = layout.GothicLayoutGenerator()
    outputs = generator.generate()

    root_col = get_or_create_collection("OL_Gothic_Floors")
    stats = {"instanced": 0, "procedural": 0}

    for element_name in ["ground_floor", "mezzanine_floor"]:
        if element_name in outputs:
            bake_element(
                element_name,
                outputs[element_name],
                root_col,
                KIT_MAPPING.get(element_name, {}),
                stats,
            )

    return outputs


def bake_structure_only():
    """Bake structural elements (piers, columns, arches) for preview."""
    print("📐 Generating structural layout...")
    generator = layout.GothicLayoutGenerator()
    outputs = generator.generate()

    root_col = get_or_create_collection("OL_Gothic_Structure")
    stats = {"instanced": 0, "procedural": 0}

    structural_elements = [
        "main_piers",
        "arcade_columns",
        "buttresses",
        "crossing_arches",
        "nave_arches",
        "transverse_ribs",
    ]

    for element_name in structural_elements:
        if element_name in outputs:
            bake_element(
                element_name,
                outputs[element_name],
                root_col,
                KIT_MAPPING.get(element_name, {}),
                stats,
            )

    return outputs


def bake_by_tier(tier: int):
    """
    Bake elements of a specific structural tier.

    Tier 1: Primary structure (main piers, crossing arches, vault ribs)
    Tier 2: Secondary structure (arcade columns, buttresses, floors)
    Tier 3: Tertiary elements (windows, railings, decorative)
    """
    print(f"\n📐 Generating Tier {tier} elements...")
    generator = layout.GothicLayoutGenerator()
    outputs = generator.generate()

    tier_names = {1: "Primary", 2: "Secondary", 3: "Tertiary"}
    root_col = get_or_create_collection(
        f"OL_Gothic_Tier{tier}_{tier_names.get(tier, '')}"
    )

    # Clear existing
    for obj in list(root_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for child in list(root_col.children):
        for obj in list(child.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(child)

    stats = {"instanced": 0, "procedural": 0}

    # Filter elements by tier
    tier_elements = [
        name for name, config in KIT_MAPPING.items() if config.get("tier") == tier
    ]

    print(f"   Elements in Tier {tier}: {tier_elements}")

    for element_name in tier_elements:
        if element_name in outputs:
            bake_element(
                element_name,
                outputs[element_name],
                root_col,
                KIT_MAPPING[element_name],
                stats,
            )

    print(
        f"\n✅ Tier {tier} complete: {stats['instanced']} instanced, {stats['procedural']} procedural"
    )
    return outputs


def bake_hierarchy_visualization():
    """
    Bake all tiers with color-coded materials to visualize structural hierarchy.

    - Tier 1 (Primary): Warm stone color
    - Tier 2 (Secondary): Medium stone color
    - Tier 3 (Tertiary): Cool stone color
    """
    print("\n" + "=" * 60)
    print("STRUCTURAL HIERARCHY VISUALIZATION")
    print("=" * 60)

    # Define tier colors
    tier_colors = {
        1: (0.8, 0.65, 0.5, 1.0),  # Warm amber (primary)
        2: (0.6, 0.55, 0.5, 1.0),  # Neutral stone (secondary)
        3: (0.5, 0.55, 0.6, 1.0),  # Cool blue-grey (tertiary)
    }

    # Create tier materials
    for tier, color in tier_colors.items():
        mat_name = f"tier_{tier}_viz"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = color
                bsdf.inputs["Roughness"].default_value = 0.7

    generator = layout.GothicLayoutGenerator()
    outputs = generator.generate()

    root_col = get_or_create_collection("OL_Hierarchy_Viz")

    # Clear existing
    for obj in list(root_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for child in list(root_col.children):
        for obj in list(child.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(child)

    total_stats = {"instanced": 0, "procedural": 0}

    for tier in [1, 2, 3]:
        tier_col = get_or_create_collection(f"Tier_{tier}", root_col)
        stats = {"instanced": 0, "procedural": 0}

        tier_elements = [
            name for name, config in KIT_MAPPING.items() if config.get("tier") == tier
        ]

        print(f"\n🏛️ Tier {tier}: {len(tier_elements)} element types")

        for element_name in tier_elements:
            if element_name in outputs:
                bake_element(
                    element_name,
                    outputs[element_name],
                    tier_col,
                    KIT_MAPPING[element_name],
                    stats,
                )

        # Apply tier material to all objects in this tier
        tier_mat = bpy.data.materials.get(f"tier_{tier}_viz")
        if tier_mat:
            for obj in tier_col.all_objects:
                if obj.type == "MESH":
                    obj.data.materials.clear()
                    obj.data.materials.append(tier_mat)

        total_stats["instanced"] += stats["instanced"]
        total_stats["procedural"] += stats["procedural"]
        print(f"   ✅ {stats['instanced'] + stats['procedural']} objects")

    print("\n" + "=" * 60)
    print("HIERARCHY VISUALIZATION COMPLETE")
    print("=" * 60)
    print(f"   Total: {total_stats['instanced'] + total_stats['procedural']} objects")
    print("   Color coding:")
    print("     - Tier 1 (Primary): Warm amber")
    print("     - Tier 2 (Secondary): Neutral stone")
    print("     - Tier 3 (Tertiary): Cool blue-grey")
    print("=" * 60 + "\n")

    return outputs


def generate_kit_pieces():
    """Generate all Gothic kit pieces using the gothic_kit_generator."""
    try:
        import gothic_kit_generator as kit

        return kit.generate_all_pieces()
    except ImportError:
        print("⚠️ gothic_kit_generator not found. Run it first to create kit pieces.")
        return None


# =============================================================================
# VALIDATION HELPERS
# =============================================================================


def validate_kit_pieces():
    """Check which kit pieces are available."""
    print("\n🔍 Validating kit pieces...")
    print("-" * 40)

    available = []
    missing = []

    for element_name, config in KIT_MAPPING.items():
        primary = config.get("source")
        fallback = config.get("fallback")

        source = find_source_object(primary, fallback)

        if source:
            available.append((element_name, source.name))
            print(f"   ✅ {element_name}: {source.name}")
        else:
            missing.append((element_name, primary, fallback))
            print(f"   ❌ {element_name}: Missing ({primary} / {fallback})")

    print("-" * 40)
    print(f"Available: {len(available)} / {len(KIT_MAPPING)}")
    print(f"Missing: {len(missing)}")

    return available, missing


def create_missing_kit_pieces():
    """Create placeholder kit pieces for missing elements."""
    available, missing = validate_kit_pieces()

    if not missing:
        print("All kit pieces available!")
        return

    kit_col = get_or_create_collection("OL_Kit_Placeholders")

    print(f"\n🔧 Creating {len(missing)} placeholder kit pieces...")

    for element_name, primary, fallback in missing:
        config = KIT_MAPPING[element_name]
        scale = config.get("scale", (1, 1, 1))

        # Create placeholder
        obj = create_procedural_mesh(primary or element_name, "cube", scale)
        kit_col.objects.link(obj)

        # Add basic material
        mat = bpy.data.materials.new(f"mat_{element_name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Give each type a different color for visualization
            colors = {
                "pier": (0.4, 0.35, 0.3, 1),
                "column": (0.45, 0.4, 0.35, 1),
                "arch": (0.5, 0.45, 0.4, 1),
                "wall": (0.55, 0.5, 0.45, 1),
                "window": (0.3, 0.5, 0.7, 1),
                "floor": (0.35, 0.3, 0.25, 1),
                "stair": (0.4, 0.35, 0.3, 1),
                "railing": (0.25, 0.2, 0.15, 1),
            }

            for key, color in colors.items():
                if key in element_name.lower():
                    bsdf.inputs["Base Color"].default_value = color
                    break

        obj.data.materials.append(mat)
        print(f"   Created: {obj.name}")

    print(f"\n✅ Placeholders created in '{kit_col.name}' collection")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Print layout summary
    layout.print_layout_summary()

    # Validate kit pieces
    validate_kit_pieces()

    # Bake
    bake_all()
