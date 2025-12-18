"""
Bake Sverchok matrices into instanced geometry under OL_GOTHIC_LAYOUT.

This reads the outputs from the SV_LIB_LAYOUT tree and instantiates chosen
source objects (walls/windows/arches) onto the provided matrices. Intended to
keep runtime users free from Sverchok dependency.

Usage (after running sverchok_layout.ensure_layout_tree()):
    import importlib, sverchok_bake
    importlib.reload(sverchok_bake)
    sverchok_bake.bake_bays()
"""

import bpy
import math
import mathutils
import random
from mathutils import Matrix
from mathutils import Vector


SV_TREE_NAME = "SV_LIB_LAYOUT"
TARGET_COLLECTION = "OL_GOTHIC_LAYOUT"

# Map output names to source objects and target sub-collections.
# Adjust these to your kit asset names/collections.
# Can be a single dict or a list of dicts (for composite objects).
INSTANCE_MAP = {
    "floor_ground": [
        {
            "object": "ol_floor_gothic",
            "collection": "OL_Floors",
            "z_offset": 0.0,
            "scale": (6.0, 6.0, 1.0),
        }
    ],
    "floor_mezz": [
        {
            "object": "ol_floor_gothic",
            "collection": "OL_Floors_Mezz",
            "z_offset": 0.0,
            "scale": (6.0, 6.0, 1.0),
        },
        {
            # Underside Slab/Beam
            "object": "Cube.006",
            "collection": "OL_Floors_Slabs",
            "z_offset": -0.2,
            "scale": (2.83, 11.76, 0.075),  # Matches ~6x6x0.4m based on source dims
        },
    ],
    # "walls": {"object": "Wall2", "collection": "OL_Walls", "z_offset": 0.0},
    # "walls_solid": {
    #    "object": "ol_wall_solid",
    #    "collection": "OL_Walls_Solid",
    #    "z_offset": 0.0,
    # },
    "windows": {"object": "GIK_Window", "collection": "OL_Windows", "z_offset": 0.0},
    "arches_main": {
        "object": "GIK_Arch1",
        "collection": "OL_Arches_Main",
        "z_offset": 0.0,
        "scale": (2.5, 2.5, 2.5),
    },
    "arches_aisle": {
        "object": "GIK_Arch1",
        "collection": "OL_Arches_Aisle",
        "z_offset": 0.0,
    },
    "columns": {"object": "Column2.001", "collection": "OL_Columns", "z_offset": 1.0},
    "railings": {
        "object": "GIK_UpperWall.001",
        "collection": "OL_Railings",
        "z_offset": 0.0,
    },
    "stairs": {
        "object": "GIK_CornerStair1.004",
        "collection": "OL_Stairs",
        "z_offset": 0.0,
    },
    "shelves": {
        "object": "Shelf_01",
        "collection": "OL_Shelves",
        "z_offset": 0.0,
        # "scale": (1.0, 1.0, 1.0),
    },
    "desks": [
        {
            "object": "ol_desk_concrete",
            "collection": "OL_Desks",
            "z_offset": 0.0,
            # "rot_euler": (0.0, 0.0, 0.0),
            "scale": (1.35, 1.35, 1.35),
        },
        {
            "object": "WoodenChair_01",
            "collection": "OL_Furniture",
            "z_offset": 0.0,
            "rot_euler": (0.0, 0.0, 3.14159),
            "pos_offset": (
                0,
                1.2,
                0,
            ),  # Place chair behind table (inverted Y due to 180 rot)
            "scale": (0.85, 0.85, 0.85),
        },
        {
            "object": "desk_lamp_arm_01",
            "collection": "OL_Furniture",
            "z_offset": 0.75,  # On top of table
            "pos_offset": (0.3, 0.3, 0),
        },
    ],
    "heroes": {"object": "ol_chandelier_a", "collection": "OL_Heroes", "z_offset": 0.0},
}

# Prop sources for desk/shelf dressing (rename source meshes to these ids in the .blend)
BOOK_STACK_SOURCES = [
    "ol_book_stack_a",
    "ol_book_stack_b",
    "ol_book_stack_c",
    "ol_book_stack_d",
    "ol_book_stack_e",
    "ol_book_stack_f",
    "ol_book_stack_g",
    "ol_book_stack_h",
]
SINGLE_BOOK_SOURCE = "book_encyclopedia_set_01_book01"
POD_PROPS_COLLECTION = "OL_PodProps"
POD_SOURCES_COLLECTION = "OL_PodSources"
POD_MONITOR_SOURCES = [
    "ol_monitor_base",
    "ol_monitor_arm",
    "ol_monitor_keyboard",
    "ol_monitor_screen",
]


def _flatten(data):
    """Sverchok often nests lists; flatten one level deep when a single-item wrapper exists."""
    while isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
        data = data[0]
    return data or []


def get_sv_outputs():
    tree = bpy.data.node_groups.get(SV_TREE_NAME)
    if not tree:
        raise RuntimeError(f"Missing Sverchok tree {SV_TREE_NAME}")

    # Find the script node and pull each output via sv_get
    script_node = None
    for node in tree.nodes:
        if node.bl_idname == "SvScriptNodeLite":
            script_node = node
            break
    if not script_node or not script_node.outputs:
        try:
            script_node.update_sockets()
        except Exception:
            ...
    if not script_node or not script_node.outputs:
        return []
    if not script_node or not script_node.outputs:
        return {}

    # Force processing to ensure outputs are live
    try:
        script_node.process()
    except Exception:
        pass

    outputs = {}
    for socket in script_node.outputs:
        try:
            outputs[socket.name] = _flatten(socket.sv_get(default=[]))
        except Exception:
            outputs[socket.name] = []
    return outputs


def ensure_collection(name):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def instance_object(
    src_name,
    mat: Matrix,
    target_col,
    z_offset: float = 0.0,
    scale=None,
    pos_offset=None,
    rot_z=None,
    rot_x=None,
    rot_y=None,
    rot_euler=None,
):
    src = bpy.data.objects.get(src_name)
    if not src:
        print(f"[skip] missing source {src_name}")
        return None
    inst = src.copy()
    inst.data = src.data.copy()

    # Apply offsets
    base_mat = mat
    if z_offset:
        base_mat = Matrix.Translation((0, 0, z_offset)) @ base_mat

    # Apply extra rotation (XYZ order)
    rx = rot_x or 0.0
    ry = rot_y or 0.0
    rz = rot_z or 0.0
    if rot_euler:
        rx, ry, rz = rot_euler
    if rx or ry or rz:
        base_mat = base_mat @ mathutils.Euler((rx, ry, rz), "XYZ").to_matrix().to_4x4()
    inst.matrix_world = base_mat

    # Additional local translation (post-matrix)
    if pos_offset:
        # Apply offset in local space of the instance?
        # If 'mat' includes rotation, we probably want this relative to that rotation.
        # So we add translation to the matrix BEFORE applying it?
        # Or we just treat it as a local translation.
        # Let's do it relative to the object's final orientation.
        inst.matrix_world = inst.matrix_world @ Matrix.Translation(pos_offset)

    if scale:
        # Apply scale locally
        s_mat = (
            Matrix.Scale(scale[0], 4, (1, 0, 0))
            @ Matrix.Scale(scale[1], 4, (0, 1, 0))
            @ Matrix.Scale(scale[2], 4, (0, 0, 1))
        )
        inst.matrix_world = inst.matrix_world @ s_mat

    target_col.objects.link(inst)
    return inst


def clear_collection(col):
    """Remove objects inside a collection (non-recursive) to avoid double-bakes."""
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def orient_radial(mat: Matrix) -> Matrix:
    """Rotate around Z so the object's forward (+Y) faces away from origin."""
    trans = mat.to_translation()
    angle = math.atan2(trans.y, trans.x) + math.pi / 2.0
    rot = Matrix.Rotation(angle, 4, "Z")
    return rot @ mat


def ensure_materials():
    mats = {}

    def get_or_make(name, color):
        mat = bpy.data.materials.get(name)
        if not mat:
            mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        mats[name] = mat
        return mat

    # Stone: Pale marble / warm ivory
    marble = get_or_make("ol_mat_gothic_stone", (0.92, 0.90, 0.85))
    marble.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.4

    # Wood: Deep walnut
    wood = get_or_make("ol_mat_wood_dark", (0.1, 0.05, 0.02))
    wood.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.4

    # Gold/Brass
    brass = get_or_make("ol_mat_gold", (0.8, 0.6, 0.2))
    brass.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.95
    brass.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.2

    # Glass
    glass = get_or_make("ol_mat_glass", (0.85, 0.95, 1.0))
    glass.node_tree.nodes["Principled BSDF"].inputs[
        "Transmission Weight"
    ].default_value = 0.95
    glass.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.02

    # Stained glass (Nebula / Outora Tech)
    stained = get_or_make("ol_mat_stained_glass", (0.2, 0.1, 0.8))
    bsdf = stained.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Transmission Weight"].default_value = 0.8
    bsdf.inputs["Emission Color"].default_value = (
        0.2,
        0.1,
        0.9,
        1.0,
    )  # Blue/Purple glow
    bsdf.inputs["Emission Strength"].default_value = 8.0
    bsdf.inputs["Roughness"].default_value = 0.1

    return mats


def apply_base_materials(src_name, mats):
    # Skip material override for assets that come with their own textures (e.g. imported GLBs)
    if "concrete" in src_name.lower():
        return

    src = bpy.data.objects.get(src_name)
    if not src or not hasattr(src.data, "materials"):
        return

    # Determine material based on object type/name
    s_lower = src_name.lower()
    if "window" in s_lower or "stained" in s_lower:
        target_mat = mats["ol_mat_stained_glass"]
    elif (
        "floor" in s_lower
        or "wall" in s_lower
        or "arch" in s_lower
        or "column" in s_lower
        or "cube" in s_lower  # Catch-all for slabs/beams using Cube.*
    ):
        target_mat = mats["ol_mat_gothic_stone"]
    elif (
        "shelf" in s_lower
        or "desk" in s_lower
        or "railing" in s_lower
        or "stair" in s_lower
    ):
        target_mat = mats["ol_mat_wood_dark"]
    elif "chandelier" in s_lower or "hero" in s_lower:
        target_mat = mats["ol_mat_gold"]
    else:
        target_mat = mats["ol_mat_gothic_stone"]

    if not src.data.materials:
        src.data.materials.append(target_mat)
    else:
        # Replace the first material slot
        src.data.materials[0] = target_mat


def bake_bays(purge_existing=True, outputs=None):
    """Bake SV tree outputs into mesh instances."""
    outputs = outputs if outputs is not None else get_sv_outputs()
    root_col = ensure_collection(TARGET_COLLECTION)
    mats_dict = ensure_materials()

    created = {}
    cleared_collections = set()

    for out_name, mats_list in outputs.items():
        mappings = INSTANCE_MAP.get(out_name)
        if not mappings:
            continue

        # Normalize to list
        if isinstance(mappings, dict):
            mappings = [mappings]

        for mapping in mappings:
            src_name = mapping.get("object")
            apply_base_materials(src_name, mats_dict)

            sub_col_name = (
                mapping.get("collection")
                or f"{TARGET_COLLECTION}_{out_name.capitalize()}"
            )
            sub_col = ensure_collection(sub_col_name)
            # Ensure sub-collection is linked under the root
            if sub_col.name not in {c.name for c in root_col.children}:
                try:
                    root_col.children.link(sub_col)
                except Exception:
                    pass

            if purge_existing:
                if sub_col.name not in cleared_collections:
                    clear_collection(sub_col)
                    cleared_collections.add(sub_col.name)

            if out_name not in created:
                created[out_name] = []

            for mat in mats_list:
                orient_mode = mapping.get("orient")
                oriented_mat = mat
                if orient_mode == "radial":
                    oriented_mat = orient_radial(mat)

                obj = instance_object(
                    src_name,
                    oriented_mat,
                    sub_col,
                    z_offset=mapping.get("z_offset", 0.0),
                    rot_z=mapping.get("rot_z"),
                    scale=mapping.get("scale"),
                    pos_offset=mapping.get("pos_offset"),
                )
                if obj:
                    created[out_name].append(obj.name)

    total = sum(len(v) for v in created.values())
    print(f"Baked {total} instances into {TARGET_COLLECTION}")
    return created


# ---------------------------------------------------------------------------
# Study pod dressing helpers (books on shelves/desks)
# ---------------------------------------------------------------------------
def _get_source_candidates(names):
    sources = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            sources.append(obj)
        else:
            print(f"[pod props] missing source: {name}")
    return sources


def _instance_prop(src, name, location, rotation_z, scale, target_col, z_lift=0.0):
    """Create a linked duplicate of a prop source."""
    inst = src.copy()
    if hasattr(src, "data") and src.data:
        inst.data = src.data.copy()
    inst.location = (location[0], location[1], location[2] + z_lift)
    inst.rotation_euler = (0.0, 0.0, rotation_z)
    if isinstance(scale, (tuple, list)):
        inst.scale = scale
    else:
        inst.scale = (scale, scale, scale)
    inst.name = name
    target_col.objects.link(inst)
    return inst


def populate_study_props(random_seed=3):
    """Dress shelves and desks with book stacks for repeatable bake runs."""
    rand = random.Random(random_seed)

    prop_col = ensure_collection(POD_PROPS_COLLECTION)
    clear_collection(prop_col)
    root_col = ensure_collection(TARGET_COLLECTION)
    if prop_col.name not in {c.name for c in root_col.children}:
        try:
            root_col.children.link(prop_col)
        except Exception:
            pass
    source_col = ensure_collection(POD_SOURCES_COLLECTION)
    source_col.hide_viewport = True
    source_col.hide_render = True
    if source_col.name not in {c.name for c in root_col.children}:
        try:
            root_col.children.link(source_col)
        except Exception:
            pass

    stack_sources = _get_source_candidates(BOOK_STACK_SOURCES)
    single_book = bpy.data.objects.get(SINGLE_BOOK_SOURCE)
    monitor_sources = _get_source_candidates(POD_MONITOR_SOURCES)
    if not stack_sources:
        print("[pod props] no book stack sources available; skipping")
        return {}
    # Park sources in a hidden collection so they don't clutter the scene
    for src in stack_sources + monitor_sources + ([single_book] if single_book else []):
        if not src:
            continue
        for col in list(src.users_collection):
            col.objects.unlink(src)
        source_col.objects.link(src)
        src.hide_set(True)

    def world_top(obj):
        return max((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)

    def place_on_top(obj, xy_offset: Vector, z_add: float) -> Vector:
        """Place relative to object orientation/scale. Z is base origin + offset; lifted per-prop."""
        base = obj.matrix_world.translation
        rot_mat = obj.matrix_world.to_3x3()
        xy = rot_mat @ Vector((xy_offset.x, xy_offset.y, 0.0))
        loc = base + xy
        loc.z = base.z + z_add
        return loc

    shelf_col = bpy.data.collections.get("OL_Shelves")
    desk_col = bpy.data.collections.get(
        "OL_Desks"
    )  # Corrected collection name for desks
    furniture_col = bpy.data.collections.get("OL_Furniture")
    shelves = list(shelf_col.objects) if shelf_col else []

    # Look in OL_Desks, not OL_Furniture
    desks = [
        obj
        for obj in (desk_col.objects if desk_col else [])
        if obj.name.startswith("ol_desk_concrete")
    ]

    created = {"shelf_stacks": [], "desk_stacks": [], "desk_single": []}
    monitor_created = []

    # Shelf offsets adjusted for better alignment
    # Moving Y from 0.12 to 0.0 to prevent back-clipping
    shelf_offsets = [
        Vector((-0.22, 0.0, 0.30)),
        Vector((0.08, 0.0, 0.30)),
        Vector((-0.22, 0.0, 0.75)),
        Vector((0.08, 0.0, 0.75)),
        Vector((-0.22, 0.0, 1.20)),
        Vector((0.08, 0.0, 1.20)),
    ]
    for s_idx, shelf in enumerate(shelves):
        for slot_idx, offset in enumerate(shelf_offsets):
            src = rand.choice(stack_sources)
            loc = place_on_top(shelf, offset, offset.z)
            rot_z = shelf.rotation_euler.z + rand.uniform(-0.2, 0.2)
            scale = rand.uniform(0.015, 0.022)
            name = f"ol_prop_shelf_stack_{s_idx:02d}_{slot_idx}"
            # Align base of mesh to surface using vertex min Z
            min_z_local = min((v.co.z for v in src.data.vertices), default=0.0)
            scale_z = scale[2] if isinstance(scale, (tuple, list)) else scale
            z_lift = -min_z_local * scale_z + 0.05
            inst = _instance_prop(src, name, loc, rot_z, scale, prop_col, z_lift=z_lift)
            created["shelf_stacks"].append(inst.name)

    # Populate desks: two stacks + one loose book on each desk
    desk_offsets = [Vector((-0.25, -0.15, 0.78)), Vector((0.18, 0.05, 0.78))]
    for d_idx, desk in enumerate(desks):
        for slot_idx, offset in enumerate(desk_offsets):
            src = rand.choice(stack_sources)
            loc = place_on_top(desk, offset, offset.z)
            rot_z = desk.rotation_euler.z + rand.uniform(-0.4, 0.4)
            scale = rand.uniform(0.015, 0.022)
            name = f"ol_prop_desk_stack_{d_idx:02d}_{slot_idx}"
            min_z_local = min((v.co.z for v in src.data.vertices), default=0.0)
            scale_z = scale[2] if isinstance(scale, (tuple, list)) else scale
            z_lift = -min_z_local * scale_z
            inst = _instance_prop(src, name, loc, rot_z, scale, prop_col, z_lift=z_lift)
            created["desk_stacks"].append(inst.name)

        if single_book:
            loc = place_on_top(desk, Vector((-0.05, 0.15, 0.78)), 0.02)
            rot_z = desk.rotation_euler.z + rand.uniform(-0.6, 0.6)
            inst = _instance_prop(
                single_book,
                f"ol_prop_desk_single_{d_idx:02d}",
                loc,
                rot_z,
                0.18,
                prop_col,
                z_lift=0.0,
            )
            created["desk_single"].append(inst.name)

        # Drop a simple monitor setup per desk (base + screen + keyboard)
        if monitor_sources:
            base = next(
                (m for m in monitor_sources if m.name == "ol_monitor_base"),
                monitor_sources[0],
            )
            screen = next(
                (m for m in monitor_sources if m.name.startswith("ol_monitor_screen")),
                monitor_sources[0],
            )
            keyboard = next(
                (m for m in monitor_sources if m.name == "ol_monitor_keyboard"),
                monitor_sources[0],
            )

            base_loc = place_on_top(desk, Vector((0.0, 0.0, 0.0)), 0.02)
            kb_loc = place_on_top(desk, Vector((0.18, -0.18, 0.0)), 0.025)
            screen_loc = place_on_top(desk, Vector((0.0, 0.0, 0.0)), 0.8)
            rot_z = desk.rotation_euler.z

            base_inst = _instance_prop(
                base,
                f"ol_prop_monitor_base_{d_idx:02d}",
                base_loc,
                rot_z,
                0.02,
                prop_col,
            )
            kb_inst = _instance_prop(
                keyboard,
                f"ol_prop_monitor_kb_{d_idx:02d}",
                kb_loc,
                rot_z,
                0.02,
                prop_col,
            )
            screen_inst = _instance_prop(
                screen,
                f"ol_prop_monitor_screen_{d_idx:02d}",
                screen_loc,
                rot_z,
                0.02,
                prop_col,
            )
            monitor_created.extend([base_inst.name, kb_inst.name, screen_inst.name])

    print(
        f"[pod props] placed {len(created['shelf_stacks'])} shelf stacks, "
        f"{len(created['desk_stacks'])} desk stacks, "
        f"{len(created['desk_single'])} desk singles"
    )
    return created


if __name__ == "__main__":
    bake_bays()
    populate_study_props()
