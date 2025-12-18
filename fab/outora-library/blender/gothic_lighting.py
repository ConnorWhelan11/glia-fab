"""
Gothic Lighting System - Dramatic cathedral lighting for the Outora Library.

Creates a comprehensive lighting setup inspired by Gothic cathedral interiors:
- Skylights through oculus with volumetric god rays
- Clerestory light shafts (high side windows)
- Stained glass color bleeding
- Practical desk lamps with warm pools
- Ambient fill from multiple sources

Based on real Gothic cathedral lighting:
- Primary: High clerestory windows create dramatic shafts
- Secondary: Rose windows cast colored light
- Tertiary: Practical lamps for reading areas
- Ambient: Soft fill from multiple bounces

Usage in Blender:
    exec(open("gothic_lighting.py").read())

Or:
    import gothic_lighting as lights
    lights.create_lighting_setup()
"""

import bpy
from math import pi, radians, sin, cos
from mathutils import Vector
from typing import Dict, List, Tuple, Optional


# =============================================================================
# LIGHTING CONSTANTS
# =============================================================================

# Layout dimensions (must match sverchok_layout_v2.py)
BAY = 6.0
CROSSING_CENTER = (0, 0, 0)
WING_EXTENT = 36.0  # How far wings extend from center
VAULT_CREST = 14.0
CLERESTORY_BASE = 8.0
MEZZANINE_HEIGHT = 5.0

# Color temperatures
WARM_GOLDEN = (1.0, 0.85, 0.65)  # Warm sunlight through amber glass
COOL_BLUE = (0.75, 0.85, 1.0)  # Cool ambient/skylight
CANDLE_WARM = (1.0, 0.75, 0.45)  # Candlelight/lamp warmth
STAINED_PURPLE = (0.6, 0.4, 0.8)  # Outora cosmic purple
STAINED_GOLD = (1.0, 0.85, 0.5)  # Golden stained glass
STAINED_BLUE = (0.4, 0.5, 0.9)  # Blue stained glass


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


def create_light(
    name: str,
    light_type: str,
    location: Tuple[float, float, float],
    rotation: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (1, 1, 1),
    energy: float = 100,
    **kwargs,
) -> bpy.types.Object:
    """Create a light object with given parameters."""

    # Create light data
    light_data = bpy.data.lights.new(name=f"{name}_data", type=light_type)
    light_data.color = color
    light_data.energy = energy

    # Type-specific settings
    if light_type == "SPOT":
        light_data.spot_size = kwargs.get("spot_size", radians(45))
        light_data.spot_blend = kwargs.get("spot_blend", 0.15)
        light_data.use_shadow = kwargs.get("shadow", True)
        if hasattr(light_data, "shadow_soft_size"):
            light_data.shadow_soft_size = kwargs.get("shadow_soft_size", 0.5)

    elif light_type == "AREA":
        light_data.shape = kwargs.get("shape", "RECTANGLE")
        light_data.size = kwargs.get("size", 2.0)
        if light_data.shape == "RECTANGLE":
            light_data.size_y = kwargs.get("size_y", light_data.size)
        light_data.use_shadow = kwargs.get("shadow", True)

    elif light_type == "POINT":
        light_data.use_shadow = kwargs.get("shadow", True)
        if hasattr(light_data, "shadow_soft_size"):
            light_data.shadow_soft_size = kwargs.get("shadow_soft_size", 0.25)

    elif light_type == "SUN":
        light_data.angle = kwargs.get("angle", radians(1.0))
        light_data.use_shadow = kwargs.get("shadow", True)

    # Create object
    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.location = location
    light_obj.rotation_euler = rotation

    return light_obj


def clear_collection_lights(col):
    """Remove all light objects from a collection."""
    for obj in list(col.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)


# =============================================================================
# WORLD/ENVIRONMENT
# =============================================================================


def setup_world():
    """Set up world environment for Gothic interior."""
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("GothicWorld")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing nodes
    nodes.clear()

    # Create nodes
    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (300, 0)

    background = nodes.new("ShaderNodeBackground")
    background.location = (0, 0)

    # Very dark blue-grey ambient (interior darkness)
    background.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1.0)
    background.inputs["Strength"].default_value = 0.3

    links.new(background.outputs["Background"], output.inputs["Surface"])

    # Note: Ambient occlusion is handled in render settings in Blender 5.x
    # For Cycles, AO is automatic; for Eevee, it's in render properties

    print("   ✅ World environment configured")


# =============================================================================
# OCULUS SKYLIGHT
# =============================================================================


def create_oculus_light(col) -> List[bpy.types.Object]:
    """
    Create dramatic skylight through the central oculus.

    This is the primary dramatic light source - a shaft of light
    descending through the central opening.
    """
    lights = []

    # Main oculus shaft - large area light pointing down
    oculus_main = create_light(
        name="OL_Oculus_Main",
        light_type="AREA",
        location=(0, 0, VAULT_CREST + 2),
        rotation=(0, 0, 0),  # Pointing down
        color=WARM_GOLDEN,
        energy=2000,
        shape="DISK",
        size=6.0,
        shadow=True,
    )
    col.objects.link(oculus_main)
    lights.append(oculus_main)

    # Secondary oculus fill (softer, cooler)
    oculus_fill = create_light(
        name="OL_Oculus_Fill",
        light_type="AREA",
        location=(0, 0, VAULT_CREST + 4),
        rotation=(0, 0, 0),
        color=COOL_BLUE,
        energy=500,
        shape="DISK",
        size=8.0,
        shadow=False,
    )
    col.objects.link(oculus_fill)
    lights.append(oculus_fill)

    print(f"   ✅ Oculus skylight: 2 lights")
    return lights


# =============================================================================
# CLERESTORY WINDOWS
# =============================================================================


def create_clerestory_lights(col) -> List[bpy.types.Object]:
    """
    Create light shafts from clerestory windows.

    High side windows in Gothic cathedrals create dramatic
    diagonal light shafts across the interior.
    """
    lights = []

    # Light positions along each wing
    # Clerestory windows are at CLERESTORY_BASE height, along wing sides

    wing_positions = [
        # North wing (positive Y)
        {
            "dir": "N",
            "positions": [
                (x * BAY, WING_EXTENT * 0.7, CLERESTORY_BASE + 2)
                for x in [-2, -1, 1, 2]
            ],
        },
        # South wing (negative Y)
        {
            "dir": "S",
            "positions": [
                (x * BAY, -WING_EXTENT * 0.7, CLERESTORY_BASE + 2)
                for x in [-2, -1, 1, 2]
            ],
        },
        # East wing (positive X)
        {
            "dir": "E",
            "positions": [
                (WING_EXTENT * 0.7, y * BAY, CLERESTORY_BASE + 2)
                for y in [-2, -1, 1, 2]
            ],
        },
        # West wing (negative X)
        {
            "dir": "W",
            "positions": [
                (-WING_EXTENT * 0.7, y * BAY, CLERESTORY_BASE + 2)
                for y in [-2, -1, 1, 2]
            ],
        },
    ]

    # Direction rotations (light pointing inward and down)
    dir_rotations = {
        "N": (radians(45), 0, radians(180)),  # From north, angled down
        "S": (radians(45), 0, 0),  # From south
        "E": (radians(45), 0, radians(-90)),  # From east
        "W": (radians(45), 0, radians(90)),  # From west
    }

    for i, wing in enumerate(wing_positions):
        direction = wing["dir"]
        for j, pos in enumerate(wing["positions"]):
            # Alternate colors for variety
            if j % 2 == 0:
                color = WARM_GOLDEN
            else:
                color = STAINED_GOLD

            light = create_light(
                name=f"OL_Clerestory_{direction}_{j}",
                light_type="SPOT",
                location=pos,
                rotation=dir_rotations[direction],
                color=color,
                energy=800,
                spot_size=radians(35),
                spot_blend=0.3,
                shadow=True,
                shadow_soft_size=1.0,
            )
            col.objects.link(light)
            lights.append(light)

    print(f"   ✅ Clerestory windows: {len(lights)} lights")
    return lights


# =============================================================================
# ROSE WINDOW LIGHTS
# =============================================================================


def create_rose_window_lights(col) -> List[bpy.types.Object]:
    """
    Create colored light from rose windows at wing terminations.

    Rose windows cast distinctive colored light pools,
    especially the Outora cosmic purple.
    """
    lights = []

    # Rose windows at each wing end
    rose_positions = [
        (WING_EXTENT - BAY, 0, VAULT_CREST - 2, STAINED_PURPLE, radians(90)),  # East
        (-WING_EXTENT + BAY, 0, VAULT_CREST - 2, STAINED_BLUE, radians(-90)),  # West
        (0, WING_EXTENT - BAY, VAULT_CREST - 2, STAINED_GOLD, radians(180)),  # North
        (0, -WING_EXTENT + BAY, VAULT_CREST - 2, COOL_BLUE, 0),  # South
    ]

    for i, (x, y, z, color, rot_z) in enumerate(rose_positions):
        # Main rose light
        rose_main = create_light(
            name=f"OL_Rose_{i}_Main",
            light_type="SPOT",
            location=(x, y, z),
            rotation=(radians(60), 0, rot_z),  # Angled down into nave
            color=color,
            energy=1200,
            spot_size=radians(50),
            spot_blend=0.5,
            shadow=True,
        )
        col.objects.link(rose_main)
        lights.append(rose_main)

        # Softer color fill
        rose_fill = create_light(
            name=f"OL_Rose_{i}_Fill",
            light_type="AREA",
            location=(x * 0.7, y * 0.7, z - 2),
            rotation=(radians(45), 0, rot_z),
            color=color,
            energy=300,
            shape="DISK",
            size=4.0,
            shadow=False,
        )
        col.objects.link(rose_fill)
        lights.append(rose_fill)

    print(f"   ✅ Rose windows: {len(lights)} lights")
    return lights


# =============================================================================
# DESK LAMPS (Practical Lights)
# =============================================================================


def create_desk_lamps(col) -> List[bpy.types.Object]:
    """
    Create warm practical desk lamps in study pod areas.

    These create intimate pools of warm light for reading,
    contrasting with the cool ambient.
    """
    lights = []

    # Study pod positions (from layout - in aisles)
    # Simplified: place lamps at regular intervals in the aisles

    aisle_lamp_positions = []

    # Along wing aisles (outside the nave, in the study zones)
    for wing_sign in [-1, 1]:
        for aisle_sign in [-1, 1]:
            # X-wing aisles
            for i in range(3):
                x = wing_sign * (12 + i * BAY)  # Beyond crossing
                y = aisle_sign * 2 * BAY  # In aisle
                aisle_lamp_positions.append((x, y, MEZZANINE_HEIGHT - 0.5))

            # Y-wing aisles
            for i in range(3):
                x = aisle_sign * 2 * BAY
                y = wing_sign * (12 + i * BAY)
                aisle_lamp_positions.append((x, y, MEZZANINE_HEIGHT - 0.5))

    # Create desk lamps
    for i, pos in enumerate(aisle_lamp_positions):
        # Small point light for desk lamp
        lamp = create_light(
            name=f"OL_DeskLamp_{i}",
            light_type="POINT",
            location=pos,
            color=CANDLE_WARM,
            energy=150,
            shadow=True,
            shadow_soft_size=0.15,
        )
        col.objects.link(lamp)
        lights.append(lamp)

    # Ground floor lamps (in the nave for dramatic effect)
    nave_lamp_positions = [
        (0, 0, 3.0),  # Central under oculus
        (0, BAY * 3, 3.0),  # Along nave
        (0, -BAY * 3, 3.0),
        (BAY * 3, 0, 3.0),  # Along transept
        (-BAY * 3, 0, 3.0),
    ]

    for i, pos in enumerate(nave_lamp_positions):
        lamp = create_light(
            name=f"OL_NaveLamp_{i}",
            light_type="POINT",
            location=pos,
            color=CANDLE_WARM,
            energy=250,
            shadow=True,
            shadow_soft_size=0.2,
        )
        col.objects.link(lamp)
        lights.append(lamp)

    print(f"   ✅ Desk lamps: {len(lights)} lights")
    return lights


# =============================================================================
# AMBIENT FILL
# =============================================================================


def create_ambient_fill(col) -> List[bpy.types.Object]:
    """
    Create soft ambient fill lights to prevent pure black shadows.

    Gothic interiors have complex light bounces; we simulate
    this with large, soft fill lights.
    """
    lights = []

    # Large area fills at cardinal points
    fill_positions = [
        ((0, 0, VAULT_CREST * 0.6), (radians(90), 0, 0), "Center"),
        ((WING_EXTENT * 0.5, 0, 6), (0, radians(-90), 0), "East"),
        ((-WING_EXTENT * 0.5, 0, 6), (0, radians(90), 0), "West"),
        ((0, WING_EXTENT * 0.5, 6), (radians(90), 0, 0), "North"),
        ((0, -WING_EXTENT * 0.5, 6), (radians(-90), 0, 0), "South"),
    ]

    for pos, rot, name in fill_positions:
        fill = create_light(
            name=f"OL_Fill_{name}",
            light_type="AREA",
            location=pos,
            rotation=rot,
            color=COOL_BLUE,
            energy=80,
            shape="RECTANGLE",
            size=15.0,
            size_y=10.0,
            shadow=False,
        )
        col.objects.link(fill)
        lights.append(fill)

    print(f"   ✅ Ambient fill: {len(lights)} lights")
    return lights


# =============================================================================
# CHANDELIER LIGHTS
# =============================================================================


def create_chandelier_lights(col) -> List[bpy.types.Object]:
    """
    Create dramatic overhead chandeliers.

    Large chandeliers hanging in the crossing and along the nave
    provide warm, ornate lighting.
    """
    lights = []

    # Central chandelier (under oculus, but lower)
    central = create_light(
        name="OL_Chandelier_Central",
        light_type="POINT",
        location=(0, 0, VAULT_CREST - 4),
        color=CANDLE_WARM,
        energy=800,
        shadow=True,
        shadow_soft_size=0.5,
    )
    col.objects.link(central)
    lights.append(central)

    # Nave chandeliers
    for sign in [-1, 1]:
        for offset in [2, 4]:
            pos = (0, sign * offset * BAY, 8)
            chandelier = create_light(
                name=f"OL_Chandelier_Nave_{sign}_{offset}",
                light_type="POINT",
                location=pos,
                color=CANDLE_WARM,
                energy=400,
                shadow=True,
                shadow_soft_size=0.3,
            )
            col.objects.link(chandelier)
            lights.append(chandelier)

    # Transept chandeliers
    for sign in [-1, 1]:
        for offset in [2, 4]:
            pos = (sign * offset * BAY, 0, 8)
            chandelier = create_light(
                name=f"OL_Chandelier_Trans_{sign}_{offset}",
                light_type="POINT",
                location=pos,
                color=CANDLE_WARM,
                energy=400,
                shadow=True,
                shadow_soft_size=0.3,
            )
            col.objects.link(chandelier)
            lights.append(chandelier)

    print(f"   ✅ Chandeliers: {len(lights)} lights")
    return lights


# =============================================================================
# MAIN SETUP FUNCTION
# =============================================================================


def create_lighting_setup(clear_existing: bool = True) -> Dict[str, List]:
    """
    Create the complete Gothic lighting setup.

    Returns dict of light categories for easy manipulation.
    """
    print("\n" + "=" * 60)
    print("GOTHIC LIGHTING SYSTEM")
    print("=" * 60)

    # Create lighting collection
    light_col = get_or_create_collection("OL_Lighting")

    if clear_existing:
        clear_collection_lights(light_col)

    # Set up world
    print("\n🌍 Setting up world...")
    setup_world()

    # Create all light types
    print("\n💡 Creating lights...")

    lights = {
        "oculus": create_oculus_light(light_col),
        "clerestory": create_clerestory_lights(light_col),
        "rose_windows": create_rose_window_lights(light_col),
        "desk_lamps": create_desk_lamps(light_col),
        "ambient_fill": create_ambient_fill(light_col),
        "chandeliers": create_chandelier_lights(light_col),
    }

    # Count totals
    total = sum(len(v) for v in lights.values())

    # Summary
    print("\n" + "=" * 60)
    print("LIGHTING SETUP COMPLETE")
    print("=" * 60)
    print(f"   Total lights: {total}")
    print("\n   Categories:")
    for cat, light_list in lights.items():
        print(f"      • {cat}: {len(light_list)}")
    print("\n   Light hierarchy:")
    print("      1. Oculus (dramatic central shaft)")
    print("      2. Clerestory (high window shafts)")
    print("      3. Rose windows (colored accents)")
    print("      4. Chandeliers (overhead warmth)")
    print("      5. Desk lamps (practical pools)")
    print("      6. Ambient fill (shadow softening)")
    print("=" * 60 + "\n")

    return lights


# =============================================================================
# PRESETS
# =============================================================================


def preset_dramatic():
    """High contrast, dramatic lighting preset."""
    print("\n🎭 Applying DRAMATIC preset...")
    lights = create_lighting_setup()

    # Increase key lights, reduce fill
    for light in lights["oculus"]:
        light.data.energy *= 1.5
    for light in lights["clerestory"]:
        light.data.energy *= 1.3
    for light in lights["ambient_fill"]:
        light.data.energy *= 0.5

    print("   ✅ Dramatic preset applied")


def preset_warm_reading():
    """Warm, cozy reading room preset."""
    print("\n📚 Applying WARM READING preset...")
    lights = create_lighting_setup()

    # Increase practical lights, warm everything
    for light in lights["desk_lamps"]:
        light.data.energy *= 1.8
        light.data.color = CANDLE_WARM
    for light in lights["chandeliers"]:
        light.data.energy *= 1.5
    for light in lights["oculus"]:
        light.data.energy *= 0.7

    print("   ✅ Warm reading preset applied")


def preset_cosmic():
    """Outora cosmic/mystical preset with purple accents."""
    print("\n🌌 Applying COSMIC preset...")
    lights = create_lighting_setup()

    # Emphasize rose windows, add purple tint
    for light in lights["rose_windows"]:
        light.data.energy *= 2.0
    for light in lights["ambient_fill"]:
        light.data.color = (0.7, 0.6, 0.9)

    print("   ✅ Cosmic preset applied")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    create_lighting_setup()
