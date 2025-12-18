"""
Gothic Materials System - Hyper-realistic material library for the Outora Library.

Creates a comprehensive material palette based on real Gothic cathedral materials:
- Stone: Limestone variants (light, dark, weathered, polished, mossy)
- Wood: Oak variants (desk, shelf, rail, aged, polished)
- Metal: Brass, iron, gold leaf accents
- Glass: Stained glass with emission, frosted glass
- Fabric: Velvet, leather for furniture

Usage in Blender:
    exec(open("gothic_materials.py").read())

Or:
    import gothic_materials as mats
    mats.create_all_materials()
    mats.apply_materials_to_scene()
"""

import bpy
from math import pi
from typing import Dict, Any, Optional, List, Tuple


# =============================================================================
# MATERIAL DEFINITIONS
# =============================================================================

# Color palettes based on real Gothic cathedral materials
STONE_COLORS = {
    "limestone_light": (0.82, 0.78, 0.70),  # Notre Dame limestone
    "limestone_warm": (0.78, 0.72, 0.62),  # Warm aged limestone
    "limestone_dark": (0.55, 0.52, 0.48),  # Shadowed/dirty stone
    "limestone_weathered": (0.62, 0.58, 0.52),  # Weathered exterior
    "sandstone": (0.85, 0.75, 0.60),  # Sandy warm stone
    "granite_dark": (0.35, 0.33, 0.32),  # Dark accent stone
    "marble_white": (0.92, 0.90, 0.88),  # White marble accents
}

WOOD_COLORS = {
    "oak_dark": (0.25, 0.18, 0.12),  # Dark aged oak
    "oak_medium": (0.40, 0.28, 0.18),  # Medium oak
    "oak_light": (0.55, 0.42, 0.28),  # Light oak
    "walnut": (0.30, 0.20, 0.12),  # Rich walnut
    "mahogany": (0.35, 0.15, 0.10),  # Deep mahogany
    "ebony": (0.12, 0.10, 0.08),  # Near-black ebony
}

METAL_COLORS = {
    "brass_polished": (0.85, 0.70, 0.35),  # Shiny brass
    "brass_aged": (0.65, 0.55, 0.35),  # Tarnished brass
    "bronze": (0.55, 0.45, 0.30),  # Dark bronze
    "iron_wrought": (0.25, 0.23, 0.22),  # Wrought iron
    "gold_leaf": (0.95, 0.80, 0.40),  # Gold accents
    "copper_patina": (0.35, 0.55, 0.45),  # Green patina
}

GLASS_COLORS = {
    "clear": (0.95, 0.95, 0.98),
    "stained_blue": (0.15, 0.25, 0.65),
    "stained_red": (0.70, 0.15, 0.12),
    "stained_gold": (0.85, 0.70, 0.20),
    "stained_green": (0.20, 0.50, 0.25),
    "stained_purple": (0.45, 0.20, 0.55),
    "frosted": (0.85, 0.88, 0.92),
}

FABRIC_COLORS = {
    "velvet_red": (0.50, 0.12, 0.10),
    "velvet_green": (0.12, 0.30, 0.18),
    "velvet_blue": (0.12, 0.18, 0.35),
    "leather_brown": (0.35, 0.25, 0.18),
    "leather_black": (0.08, 0.07, 0.06),
}


# Material configurations
MATERIAL_CONFIGS = {
    # =========================================================================
    # STONE MATERIALS (Tier 1-2 Structure)
    # =========================================================================
    "gm_stone_light": {
        "category": "stone",
        "base_color": STONE_COLORS["limestone_light"],
        "roughness": 0.75,
        "metallic": 0.0,
        "subsurface": 0.02,
        "bump_strength": 0.3,
        "description": "Primary limestone for main piers and arches",
    },
    "gm_stone_warm": {
        "category": "stone",
        "base_color": STONE_COLORS["limestone_warm"],
        "roughness": 0.80,
        "metallic": 0.0,
        "subsurface": 0.02,
        "bump_strength": 0.35,
        "description": "Warm limestone for interior walls",
    },
    "gm_stone_dark": {
        "category": "stone",
        "base_color": STONE_COLORS["limestone_dark"],
        "roughness": 0.70,
        "metallic": 0.0,
        "subsurface": 0.01,
        "bump_strength": 0.4,
        "description": "Dark stone for bases and shadow areas",
    },
    "gm_stone_weathered": {
        "category": "stone",
        "base_color": STONE_COLORS["limestone_weathered"],
        "roughness": 0.90,
        "metallic": 0.0,
        "subsurface": 0.01,
        "bump_strength": 0.5,
        "description": "Weathered stone for exterior buttresses",
    },
    "gm_stone_polished": {
        "category": "stone",
        "base_color": STONE_COLORS["marble_white"],
        "roughness": 0.25,
        "metallic": 0.0,
        "subsurface": 0.05,
        "bump_strength": 0.1,
        "description": "Polished marble for special accents",
    },
    "gm_stone_floor": {
        "category": "stone",
        "base_color": (0.45, 0.42, 0.38),
        "roughness": 0.65,
        "metallic": 0.0,
        "subsurface": 0.01,
        "bump_strength": 0.2,
        "description": "Floor stone tiles",
    },
    # =========================================================================
    # WOOD MATERIALS (Furniture, Rails, Details)
    # =========================================================================
    "gm_wood_desk": {
        "category": "wood",
        "base_color": WOOD_COLORS["oak_dark"],
        "roughness": 0.45,
        "metallic": 0.0,
        "subsurface": 0.03,
        "clearcoat": 0.3,
        "bump_strength": 0.2,
        "description": "Polished dark oak for desks",
    },
    "gm_wood_shelf": {
        "category": "wood",
        "base_color": WOOD_COLORS["oak_medium"],
        "roughness": 0.55,
        "metallic": 0.0,
        "subsurface": 0.02,
        "clearcoat": 0.1,
        "bump_strength": 0.25,
        "description": "Medium oak for bookshelves",
    },
    "gm_wood_rail": {
        "category": "wood",
        "base_color": WOOD_COLORS["walnut"],
        "roughness": 0.40,
        "metallic": 0.0,
        "subsurface": 0.03,
        "clearcoat": 0.4,
        "bump_strength": 0.15,
        "description": "Rich walnut for balustrade rails",
    },
    "gm_wood_aged": {
        "category": "wood",
        "base_color": WOOD_COLORS["oak_dark"],
        "roughness": 0.70,
        "metallic": 0.0,
        "subsurface": 0.01,
        "clearcoat": 0.0,
        "bump_strength": 0.4,
        "description": "Aged unfinished wood",
    },
    "gm_wood_beam": {
        "category": "wood",
        "base_color": (0.30, 0.22, 0.15),
        "roughness": 0.65,
        "metallic": 0.0,
        "subsurface": 0.02,
        "clearcoat": 0.0,
        "bump_strength": 0.35,
        "description": "Structural beams",
    },
    # =========================================================================
    # METAL MATERIALS (Accents, Fixtures)
    # =========================================================================
    "gm_brass_polished": {
        "category": "metal",
        "base_color": METAL_COLORS["brass_polished"],
        "roughness": 0.25,
        "metallic": 0.95,
        "description": "Polished brass for lamp fixtures",
    },
    "gm_brass_aged": {
        "category": "metal",
        "base_color": METAL_COLORS["brass_aged"],
        "roughness": 0.45,
        "metallic": 0.85,
        "description": "Tarnished brass for hardware",
    },
    "gm_iron_wrought": {
        "category": "metal",
        "base_color": METAL_COLORS["iron_wrought"],
        "roughness": 0.60,
        "metallic": 0.90,
        "description": "Wrought iron for railings and gates",
    },
    "gm_gold_leaf": {
        "category": "metal",
        "base_color": METAL_COLORS["gold_leaf"],
        "roughness": 0.20,
        "metallic": 1.0,
        "description": "Gold leaf for decorative accents",
    },
    "gm_bronze_dark": {
        "category": "metal",
        "base_color": METAL_COLORS["bronze"],
        "roughness": 0.50,
        "metallic": 0.90,
        "description": "Dark bronze for statues",
    },
    # =========================================================================
    # GLASS MATERIALS (Windows)
    # =========================================================================
    "gm_glass_clear": {
        "category": "glass",
        "base_color": GLASS_COLORS["clear"],
        "roughness": 0.05,
        "metallic": 0.0,
        "transmission": 0.95,
        "ior": 1.45,
        "description": "Clear glass for clerestory",
    },
    "gm_glass_frosted": {
        "category": "glass",
        "base_color": GLASS_COLORS["frosted"],
        "roughness": 0.35,
        "metallic": 0.0,
        "transmission": 0.85,
        "ior": 1.45,
        "description": "Frosted glass diffusing light",
    },
    "gm_stained_blue": {
        "category": "glass",
        "base_color": GLASS_COLORS["stained_blue"],
        "roughness": 0.15,
        "metallic": 0.0,
        "transmission": 0.70,
        "emission": 0.3,
        "ior": 1.52,
        "description": "Blue stained glass",
    },
    "gm_stained_red": {
        "category": "glass",
        "base_color": GLASS_COLORS["stained_red"],
        "roughness": 0.15,
        "metallic": 0.0,
        "transmission": 0.65,
        "emission": 0.4,
        "ior": 1.52,
        "description": "Red stained glass",
    },
    "gm_stained_gold": {
        "category": "glass",
        "base_color": GLASS_COLORS["stained_gold"],
        "roughness": 0.15,
        "metallic": 0.0,
        "transmission": 0.75,
        "emission": 0.5,
        "ior": 1.52,
        "description": "Gold/amber stained glass",
    },
    "gm_stained_purple": {
        "category": "glass",
        "base_color": GLASS_COLORS["stained_purple"],
        "roughness": 0.15,
        "metallic": 0.0,
        "transmission": 0.60,
        "emission": 0.3,
        "ior": 1.52,
        "description": "Purple stained glass (Outora cosmic)",
    },
    # =========================================================================
    # FABRIC MATERIALS (Furniture)
    # =========================================================================
    "gm_velvet_red": {
        "category": "fabric",
        "base_color": FABRIC_COLORS["velvet_red"],
        "roughness": 0.85,
        "metallic": 0.0,
        "sheen": 0.5,
        "subsurface": 0.05,
        "description": "Red velvet for chair seats",
    },
    "gm_leather_brown": {
        "category": "fabric",
        "base_color": FABRIC_COLORS["leather_brown"],
        "roughness": 0.55,
        "metallic": 0.0,
        "sheen": 0.2,
        "clearcoat": 0.15,
        "description": "Brown leather for desk chairs",
    },
}


# =============================================================================
# MATERIAL CREATION FUNCTIONS
# =============================================================================


def create_material(name: str, config: Dict[str, Any]) -> bpy.types.Material:
    """Create a Principled BSDF material from configuration."""

    # Check if exists
    mat = bpy.data.materials.get(name)
    if mat:
        return mat

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Get or create Principled BSDF
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")

    output = nodes.get("Material Output")
    if not output:
        output = nodes.new("ShaderNodeOutputMaterial")

    # Base color
    base_color = config.get("base_color", (0.5, 0.5, 0.5))
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)

    # Roughness
    bsdf.inputs["Roughness"].default_value = config.get("roughness", 0.5)

    # Metallic
    bsdf.inputs["Metallic"].default_value = config.get("metallic", 0.0)

    # Subsurface (for organic materials)
    if "subsurface" in config:
        bsdf.inputs["Subsurface Weight"].default_value = config["subsurface"]
        bsdf.inputs["Subsurface Radius"].default_value = (0.1, 0.05, 0.02)

    # Clearcoat (for polished surfaces)
    if "clearcoat" in config:
        bsdf.inputs["Coat Weight"].default_value = config["clearcoat"]
        bsdf.inputs["Coat Roughness"].default_value = 0.1

    # Sheen (for fabric)
    if "sheen" in config:
        bsdf.inputs["Sheen Weight"].default_value = config["sheen"]

    # Transmission (for glass)
    if "transmission" in config:
        bsdf.inputs["Transmission Weight"].default_value = config["transmission"]

    # IOR
    if "ior" in config:
        bsdf.inputs["IOR"].default_value = config["ior"]

    # Emission (for stained glass glow)
    if "emission" in config and config["emission"] > 0:
        emission_color = config.get("base_color", (1, 1, 1))
        bsdf.inputs["Emission Color"].default_value = (*emission_color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = config["emission"]

    # Add procedural bump for stone/wood
    if config.get("bump_strength", 0) > 0:
        add_procedural_bump(
            mat, config["bump_strength"], config.get("category", "stone")
        )

    # Connect
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return mat


def add_procedural_bump(mat: bpy.types.Material, strength: float, category: str):
    """Add procedural bump/normal mapping based on material category."""
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return

    # Create noise texture
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, -200)

    # Create bump node
    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -200)
    bump.inputs["Strength"].default_value = strength

    if category == "stone":
        noise.inputs["Scale"].default_value = 15.0
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Roughness"].default_value = 0.6
        bump.inputs["Distance"].default_value = 0.02
    elif category == "wood":
        noise.inputs["Scale"].default_value = 50.0
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.4
        noise.inputs["Distortion"].default_value = 2.0
        bump.inputs["Distance"].default_value = 0.005
    else:
        noise.inputs["Scale"].default_value = 20.0
        noise.inputs["Detail"].default_value = 5.0

    # Connect
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def create_all_materials() -> Dict[str, bpy.types.Material]:
    """Create all materials in the library."""
    print("\n" + "=" * 60)
    print("GOTHIC MATERIALS SYSTEM")
    print("=" * 60)

    materials = {}
    categories = {}

    for name, config in MATERIAL_CONFIGS.items():
        mat = create_material(name, config)
        materials[name] = mat

        cat = config.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)

    # Print summary
    print("\n📦 Materials created by category:")
    for cat, names in categories.items():
        print(f"\n   {cat.upper()} ({len(names)}):")
        for name in names:
            desc = MATERIAL_CONFIGS[name].get("description", "")
            print(f"      • {name}: {desc}")

    print("\n" + "=" * 60)
    print(f"Total: {len(materials)} materials created")
    print("=" * 60 + "\n")

    return materials


# =============================================================================
# MATERIAL APPLICATION
# =============================================================================

# Mapping from object name patterns to materials
OBJECT_MATERIAL_MAP = {
    # Structural (stone)
    "Pier": "gm_stone_light",
    "Column": "gm_stone_light",
    "Arch": "gm_stone_warm",
    "Rib": "gm_stone_light",
    "Buttress": "gm_stone_weathered",
    "Wall": "gm_stone_warm",
    "Floor": "gm_stone_floor",
    "floor": "gm_stone_floor",
    # Windows (glass)
    "Window": "gm_stained_gold",
    "Lancet": "gm_stained_blue",
    "Rose": "gm_stained_purple",
    "Clerestory": "gm_glass_frosted",
    # Wood elements
    "Desk": "gm_wood_desk",
    "desk": "gm_wood_desk",
    "Shelf": "gm_wood_shelf",
    "shelf": "gm_wood_shelf",
    "Balustrade": "gm_wood_rail",
    "Rail": "gm_wood_rail",
    "Beam": "gm_wood_beam",
    "beam": "gm_wood_beam",
    "Book": "gm_wood_aged",
    # Metal
    "Chandelier": "gm_brass_polished",
    "Lamp": "gm_brass_aged",
    "lamp": "gm_brass_aged",
    "Statue": "gm_bronze_dark",
    "statue": "gm_bronze_dark",
    "Plinth": "gm_stone_polished",
    # Furniture
    "Chair": "gm_leather_brown",
    "chair": "gm_leather_brown",
    "Cushion": "gm_velvet_red",
}


def apply_material_to_object(obj: bpy.types.Object, mat_name: str):
    """Apply a material to an object."""
    if obj.type != "MESH":
        return False

    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = create_material(mat_name, MATERIAL_CONFIGS.get(mat_name, {}))

    if mat:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        return True
    return False


def auto_assign_material(obj: bpy.types.Object) -> Optional[str]:
    """Automatically assign material based on object name."""
    name = obj.name

    for pattern, mat_name in OBJECT_MATERIAL_MAP.items():
        if pattern in name:
            if apply_material_to_object(obj, mat_name):
                return mat_name

    return None


def apply_materials_to_scene(collection_name: Optional[str] = None):
    """Apply materials to all objects in scene or specified collection."""
    print("\n🎨 Applying materials to scene...")

    if collection_name:
        col = bpy.data.collections.get(collection_name)
        if not col:
            print(f"   ❌ Collection '{collection_name}' not found")
            return
        objects = col.all_objects
    else:
        objects = bpy.context.scene.objects

    applied = 0
    skipped = 0

    for obj in objects:
        if obj.type != "MESH":
            continue

        mat_name = auto_assign_material(obj)
        if mat_name:
            applied += 1
        else:
            skipped += 1

    print(f"   ✅ Applied materials to {applied} objects")
    if skipped > 0:
        print(f"   ⚠️ Skipped {skipped} objects (no matching pattern)")


def apply_materials_to_collection(collection_name: str, material_name: str):
    """Apply a single material to all objects in a collection."""
    col = bpy.data.collections.get(collection_name)
    if not col:
        print(f"❌ Collection '{collection_name}' not found")
        return

    mat = bpy.data.materials.get(material_name)
    if not mat:
        if material_name in MATERIAL_CONFIGS:
            mat = create_material(material_name, MATERIAL_CONFIGS[material_name])
        else:
            print(f"❌ Material '{material_name}' not found")
            return

    count = 0
    for obj in col.all_objects:
        if obj.type == "MESH":
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            count += 1

    print(f"✅ Applied '{material_name}' to {count} objects in '{collection_name}'")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    create_all_materials()
    apply_materials_to_scene()
