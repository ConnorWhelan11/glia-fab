import bpy
import math
import bmesh
from mathutils import Euler
from pathlib import Path

KIT_BLEND_NAME = "Gothic_Kit_for_sketchfab.blend"
KIT_SRC_COLLECTION = "Collection"
KIT_APPENDED_COLLECTION = "OL_GOTHIC_KIT_SRC"
GOTHIC_LAYOUT_COLLECTION = "OL_GOTHIC_LAYOUT"
OLD_SHELL_COLLECTION = "OL_SHELL"
OLD_PROXIES_COLLECTION = "OL_PROXIES"
OLD_FINAL_COLLECTION = "OL_SCENE_FINAL"
STONE_MATERIAL_NAME = "ol_mat_gothic_stone"
BAY_SIZE = 6.0
FLOOR_SIZE_X = 36.0  # 6m rhythm, 6 bays along X
FLOOR_SIZE_Y = 36.0  # 6m rhythm, 6 bays along Y
MEZZ_Z = 5.0
OCULUS_CLEAR_HALF = 6.0  # central void half-size in mezz (hole spans 12m)


def get_or_create_collection(name):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def remove_object(name: str):
    obj = bpy.data.objects.get(name)
    if not obj:
        return
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    bpy.data.objects.remove(obj, do_unlink=True)


def clear_collection(col: bpy.types.Collection):
    for obj in list(col.objects):
        remove_object(obj.name)


def remove_objects_by_prefix(prefixes):
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in prefixes):
            remove_object(obj.name)


def ensure_gothic_material():
    mat = bpy.data.materials.get(STONE_MATERIAL_NAME)
    if mat:
        return mat
    mat = bpy.data.materials.new(STONE_MATERIAL_NAME)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled:
        base = principled.inputs.get("Base Color")
        rough = principled.inputs.get("Roughness")
        sheen_tint = principled.inputs.get("Sheen Tint")
        if base:
            base.default_value = (0.75, 0.7, 0.63, 1.0)
        if rough:
            rough.default_value = 0.75
        if sheen_tint:
            sheen_tint.default_value = 0.4
    return mat


def apply_material_to_collection(col: bpy.types.Collection, mat: bpy.types.Material):
    for obj in col.objects:
        if obj.type != "MESH" or not obj.data:
            continue
        mesh = obj.data
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = True
        mesh.materials.clear()
        mesh.materials.append(mat)


def append_gothic_kit():
    # Append the gothic kit from the local blend
    blend_dir = Path(bpy.path.abspath("//"))
    kit_path = blend_dir / KIT_BLEND_NAME
    if not kit_path.exists():
        raise FileNotFoundError(f"Gothic kit not found at {kit_path}")

    # If already appended, reuse
    existing = bpy.data.collections.get(KIT_APPENDED_COLLECTION)
    if existing:
        return existing

    with bpy.data.libraries.load(str(kit_path), link=False) as (data_from, _):
        if KIT_SRC_COLLECTION not in data_from.collections:
            raise RuntimeError(f"{KIT_SRC_COLLECTION} not found in {kit_path}")

    bpy.ops.wm.append(
        filepath=str(kit_path / "Collection" / KIT_SRC_COLLECTION),
        directory=str(kit_path / "Collection"),
        filename=KIT_SRC_COLLECTION,
        link=False,
        autoselect=False,
    )
    appended = bpy.data.collections.get(KIT_SRC_COLLECTION)
    if appended:
        appended.name = KIT_APPENDED_COLLECTION
        return appended
    raise RuntimeError("Failed to append gothic kit collection")


def create_plane(name, size_x, size_y, loc, material=None, parent_col=None):
    remove_object(name)
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    hx, hy = size_x / 2, size_y / 2
    verts = [(-hx, -hy, 0.0), (hx, -hy, 0.0), (hx, hy, 0.0), (-hx, hy, 0.0)]
    faces = [(0, 1, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    if material:
        mesh.materials.append(material)
    if parent_col:
        parent_col.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def create_gothic_megalibrary():
    """Build a multi-floor gothic library layout using the kitbash components."""
    layout_col = get_or_create_collection(GOTHIC_LAYOUT_COLLECTION)
    clear_collection(layout_col)
    remove_objects_by_prefix(
        [
            "ol_wing_",
            "ol_arch_",
            "ol_column_",
            "ol_statue_",
            "ol_stair_",
            "ol_mezz_",
            "ol_floor_",
            "ol_floor",
            "ol_ceiling",
        ]
    )

    kit_col = append_gothic_kit()
    stone_mat = ensure_gothic_material()
    apply_material_to_collection(kit_col, stone_mat)

    # Hide legacy blockout so the new shell reads cleanly
    for old in ("ol_walls", "ol_ceiling"):
        obj = bpy.data.objects.get(old)
        if obj:
            obj.hide_set(True)
            obj.hide_render = True
    for col_name in (OLD_SHELL_COLLECTION, OLD_PROXIES_COLLECTION):
        col = bpy.data.collections.get(col_name)
        if col:
            col.hide_render = True
            col.hide_viewport = True
    # Hide legacy final dressing if present
    col_final = bpy.data.collections.get(OLD_FINAL_COLLECTION)
    if col_final:
        col_final.hide_render = True
        col_final.hide_viewport = True

    laminate = bpy.data.materials.get("laminate_floor_02")

    # Primary floor plate (aligned to 6m bays)
    create_plane(
        "ol_floor_grand",
        size_x=FLOOR_SIZE_X,
        size_y=FLOOR_SIZE_Y,
        loc=(0.0, 0.0, 0.0),
        material=laminate,
        parent_col=layout_col,
    )

    # Mezzanine bands leaving a central oculus (hole spans 12m)
    create_plane(
        "ol_mezz_north",
        size_x=FLOOR_SIZE_X,
        size_y=6.0,
        loc=(0.0, (OCULUS_CLEAR_HALF + 3.0), MEZZ_Z),
        material=laminate,
        parent_col=layout_col,
    )
    create_plane(
        "ol_mezz_south",
        size_x=FLOOR_SIZE_X,
        size_y=6.0,
        loc=(0.0, -(OCULUS_CLEAR_HALF + 3.0), MEZZ_Z),
        material=laminate,
        parent_col=layout_col,
    )
    create_plane(
        "ol_mezz_east",
        size_x=6.0,
        size_y=FLOOR_SIZE_Y - 12.0,
        loc=((OCULUS_CLEAR_HALF + 3.0), 0.0, MEZZ_Z),
        material=laminate,
        parent_col=layout_col,
    )
    create_plane(
        "ol_mezz_west",
        size_x=6.0,
        size_y=FLOOR_SIZE_Y - 12.0,
        loc=(-(OCULUS_CLEAR_HALF + 3.0), 0.0, MEZZ_Z),
        material=laminate,
        parent_col=layout_col,
    )

    def find_src(src_name: str):
        obj = kit_col.objects.get(src_name) if kit_col else None
        if not obj:
            obj = bpy.data.objects.get(src_name)
        return obj

    def place_copy(src_name, name, loc, rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
        src = find_src(src_name)
        if not src:
            print(f"[missing] {src_name}")
            return None
        remove_object(name)
        obj = src.copy()
        obj.data = src.data.copy()
        obj.name = name
        obj.location = loc
        obj.rotation_euler = rot
        obj.scale = scale
        layout_col.objects.link(obj)
        return obj

    # Four crossing arches anchored to bay grid (crest ~8-9m after scale)
    arch_scale = (0.6, 0.6, 0.6)  # crest ~10m
    arch_offset = 9.0
    place_copy("GIK_Arch1", "ol_arch_n", (0.0, arch_offset, 0.0), (0.0, 0.0, 0.0), arch_scale)
    place_copy("GIK_Arch1", "ol_arch_s", (0.0, -arch_offset, 0.0), (0.0, 0.0, math.radians(180)), arch_scale)
    place_copy("GIK_Arch1", "ol_arch_e", (arch_offset, 0.0, 0.0), (0.0, 0.0, math.radians(90)), arch_scale)
    place_copy("GIK_Arch1", "ol_arch_w", (-arch_offset, 0.0, 0.0), (0.0, 0.0, math.radians(-90)), arch_scale)

    # Piers/columns at mezz corners of the oculus
    col_scale = (2.0, 2.0, 2.0)
    for name, loc in [
        ("ol_column_ne", (OCULUS_CLEAR_HALF + 6.0, OCULUS_CLEAR_HALF + 6.0, 0.0)),
        ("ol_column_nw", (-(OCULUS_CLEAR_HALF + 6.0), OCULUS_CLEAR_HALF + 6.0, 0.0)),
        ("ol_column_se", (OCULUS_CLEAR_HALF + 6.0, -(OCULUS_CLEAR_HALF + 6.0), 0.0)),
        ("ol_column_sw", (-(OCULUS_CLEAR_HALF + 6.0), -(OCULUS_CLEAR_HALF + 6.0), 0.0)),
    ]:
        place_copy("Column2.001", name, loc, scale=col_scale)

    # Perimeter wall rhythm: buttress/wall repeats every 6m on all sides
    wall_src = "Wall2"
    wall_scale = (2.5, 2.5, 2.5)
    edge_positions = [-18.0, -12.0, -6.0, 0.0, 6.0, 12.0, 18.0]
    idx = 0
    for x in edge_positions:
        place_copy(wall_src, f"ol_wall_n_{idx}", (x, 18.0, 0.0), (0.0, 0.0, 0.0), wall_scale)
        idx += 1
    idx = 0
    for x in edge_positions:
        place_copy(wall_src, f"ol_wall_s_{idx}", (x, -18.0, 0.0), (0.0, 0.0, math.radians(180)), wall_scale)
        idx += 1
    idx = 0
    for y in edge_positions:
        place_copy(wall_src, f"ol_wall_e_{idx}", (18.0, y, 0.0), (0.0, 0.0, math.radians(-90)), wall_scale)
        idx += 1
    idx = 0
    for y in edge_positions:
        place_copy(wall_src, f"ol_wall_w_{idx}", (-18.0, y, 0.0), (0.0, 0.0, math.radians(90)), wall_scale)
        idx += 1

    # Clerestory/aperture windows at mezz height band
    window_z = 4.0
    window_scale = (2.2, 2.2, 2.2)
    win_positions = [-12.0, -6.0, 0.0, 6.0, 12.0]
    for x in win_positions:
        place_copy("GIK_Window", f"ol_window_n_{x}", (x, 18.1, window_z), (0.0, 0.0, 0.0), window_scale)
        place_copy("GIK_Window", f"ol_window_s_{x}", (x, -18.1, window_z), (0.0, 0.0, math.radians(180)), window_scale)
    for y in win_positions:
        place_copy("GIK_Window", f"ol_window_e_{y}", (18.1, y, window_z), (0.0, 0.0, math.radians(-90)), window_scale)
        place_copy("GIK_Window", f"ol_window_w_{y}", (-18.1, y, window_z), (0.0, 0.0, math.radians(90)), window_scale)

    # Statues framing central stacks (at bay centers)
    statue_a = find_src("Statue1")
    statue_b = find_src("Statue2")
    statue_spots = [
        ("ol_statue_n", (0.0, 7.0, 0.0), statue_a),
        ("ol_statue_s", (0.0, -7.0, 0.0), statue_b),
        ("ol_statue_e", (7.0, 0.0, 0.0), statue_b),
        ("ol_statue_w", (-7.0, 0.0, 0.0), statue_a),
    ]
    for name, loc, src in statue_spots:
        if not src:
            continue
        place_copy(src.name, name, loc, scale=(1.6, 1.6, 1.6))

    # Grand stairs placed at midpoints toward mezzanine
    stair_src = find_src("GIK_LongStair1")
    if stair_src:
        stairs = [
            ("ol_stair_n", (0.0, 9.0, 0.0), 0.0),
            ("ol_stair_s", (0.0, -9.0, 0.0), math.radians(180)),
            ("ol_stair_e", (9.0, 0.0, 0.0), math.radians(-90)),
            ("ol_stair_w", (-9.0, 0.0, 0.0), math.radians(90)),
        ]
        for name, loc, rz in stairs:
            place_copy(
                stair_src.name,
                name,
                loc,
                rot=Euler((0.0, 0.0, rz), "XYZ"),
                scale=(2.2, 2.2, 2.2),
            )

    # Hide legacy stray OL_* objects outside the layout to reduce clutter
    keep_visible = {"ol_cam_hero", "ol_focus_target", "ol_skybox_0", "ol_skybox_1", "ol_skybox_2", "ol_skybox_3"}
    for obj in bpy.data.objects:
        if obj.name.startswith("ol_") and obj.name not in layout_col.objects.keys():
            if obj.name in keep_visible:
                continue
            obj.hide_set(True)
            obj.hide_render = True

    print("Gothic mega-library grid layout generated in OL_GOTHIC_LAYOUT")


def create_blockout():
    # Parameters
    MAJOR_RADIUS = 9.0
    MINOR_RADIUS = 7.2
    WALL_HEIGHT = 4.2
    WALL_THICKNESS = 0.2
    SEGMENTS = 12

    # Collections
    coll_shell = bpy.data.collections.get("OL_SHELL")
    if not coll_shell:
        coll_shell = bpy.data.collections.new("OL_SHELL")
        bpy.context.scene.collection.children.link(coll_shell)

    coll_proxies = bpy.data.collections.get("OL_PROXIES")
    if not coll_proxies:
        coll_proxies = bpy.data.collections.new("OL_PROXIES")
        bpy.context.scene.collection.children.link(coll_proxies)

    # Cleanup existing OL objects to ensure clean state
    # (Be careful not to delete Assets if they were renamed, but here we delete by prefix/collection if needed)
    # Actually, safer to delete specific named objects we are about to create

    objects_to_remove = []
    objects_to_remove.append(bpy.data.objects.get("ol_floor"))
    objects_to_remove.append(bpy.data.objects.get("ol_walls"))
    objects_to_remove.append(bpy.data.objects.get("ol_window_cutter"))
    objects_to_remove.append(bpy.data.objects.get("ol_proxy_desk"))
    objects_to_remove.append(bpy.data.objects.get("ol_ceiling"))

    # Find old pillars
    for o in bpy.data.objects:
        if o.name.startswith("ol_pillar_"):
            objects_to_remove.append(o)
    for o in bpy.data.objects:
        if o.name.startswith("ol_proxy_shelf_"):
            objects_to_remove.append(o)

    for o in objects_to_remove:
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    # 1. Floor (Oval)
    bm = bmesh.new()
    bmesh.ops.create_circle(
        bm, cap_ends=True, radius=1.0, segments=SEGMENTS * 2  # Smoother floor
    )
    # Scale to oval
    bmesh.ops.scale(bm, vec=(MAJOR_RADIUS, MINOR_RADIUS, 1.0), verts=bm.verts)

    mesh = bpy.data.meshes.new("ol_floor_mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj_floor = bpy.data.objects.new("ol_floor", mesh)
    coll_shell.objects.link(obj_floor)

    # 2. Walls (Segmented)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=1.0, segments=SEGMENTS)
    bmesh.ops.scale(bm, vec=(MAJOR_RADIUS, MINOR_RADIUS, 1.0), verts=bm.verts)

    # Extrude up
    res = bmesh.ops.extrude_edge_only(bm, edges=bm.edges)
    verts_ext = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, WALL_HEIGHT), verts=verts_ext)

    # Solidify (manual or modifier - let's use modifier on object)
    mesh_wall = bpy.data.meshes.new("ol_walls_mesh")
    bm.to_mesh(mesh_wall)
    bm.free()

    obj_wall = bpy.data.objects.new("ol_walls", mesh_wall)
    coll_shell.objects.link(obj_wall)

    mod_solid = obj_wall.modifiers.new("Solidify", "SOLIDIFY")
    mod_solid.thickness = WALL_THICKNESS

    # Window Boolean (Placeholder)
    # 4.0m wide x 2.2m tall, centered +Y
    # Use standard cube mesh or create one
    if "Cube" in bpy.data.meshes:
        cube_mesh = bpy.data.meshes["Cube"]
    else:
        # Create a basic cube mesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        cube_mesh = bpy.data.meshes.new("ol_proxy_cube_mesh")
        bm.to_mesh(cube_mesh)
        bm.free()

    obj_window = bpy.data.objects.new("ol_window_cutter", cube_mesh)
    obj_window.location = (0, MINOR_RADIUS, 1.0 + 2.2 / 2)
    obj_window.scale = (4.0, 1.0, 2.2)
    obj_window.display_type = "WIRE"

    coll_shell.objects.link(obj_window)
    obj_window.hide_render = True

    mod_bool = obj_wall.modifiers.new("WindowCut", "BOOLEAN")
    mod_bool.object = obj_window
    mod_bool.operation = "DIFFERENCE"

    # 3. Shelves Proxies (Ring)
    shelf_w, shelf_h, shelf_d = 1.2, 2.2, 0.35

    for i in range(SEGMENTS):
        angle = (i / SEGMENTS) * 2 * math.pi
        # Ellipse perimeter point approx
        x = math.cos(angle) * (MAJOR_RADIUS - 0.5)
        y = math.sin(angle) * (MINOR_RADIUS - 0.5)

        # Skip window area (approx 90 degrees / pi/2)
        if abs(angle - math.pi / 2) < 0.5:
            continue

        shelf = bpy.data.objects.new(f"ol_proxy_shelf_{i}", cube_mesh)
        shelf.scale = (shelf_w, shelf_d, shelf_h)
        shelf.location = (x, y, shelf_h / 2)
        shelf.rotation_euler = (0, 0, angle + math.pi / 2)  # Face inward

        coll_proxies.objects.link(shelf)

    # 4. Desk Proxy (Hero)
    desk = bpy.data.objects.new("ol_proxy_desk", cube_mesh)
    desk.scale = (1.6, 0.8, 0.75)
    desk.location = (0, 1.2, 0.75 / 2)  # Offset +Y

    coll_proxies.objects.link(desk)

    # 5. Pillars (Architecture)
    # Place pillars at the vertices of the 12-gon wall
    pillar_size = 0.6
    for i in range(SEGMENTS):
        angle = (i / SEGMENTS) * 2 * math.pi
        x = math.cos(angle) * MAJOR_RADIUS
        y = math.sin(angle) * MINOR_RADIUS

        # Skip if near window? Maybe keep window pillars

        pillar = bpy.data.objects.new(f"ol_pillar_{i}", cube_mesh)
        pillar.scale = (pillar_size, pillar_size, WALL_HEIGHT)
        pillar.location = (x, y, WALL_HEIGHT / 2)
        pillar.rotation_euler = (0, 0, angle)

        coll_shell.objects.link(pillar)

    # 6. Ceiling (Simple Disc)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=SEGMENTS * 2)
    bmesh.ops.scale(
        bm, vec=(MAJOR_RADIUS + 1.0, MINOR_RADIUS + 1.0, 1.0), verts=bm.verts
    )
    mesh_ceil = bpy.data.meshes.new("ol_ceiling_mesh")
    bm.to_mesh(mesh_ceil)
    bm.free()

    obj_ceil = bpy.data.objects.new("ol_ceiling", mesh_ceil)
    obj_ceil.location.z = WALL_HEIGHT
    # Flip normals to point down? Or just make it double sided.
    # For now, standard plane faces +Z. Rotate 180 to face down.
    obj_ceil.rotation_euler.x = math.pi

    coll_shell.objects.link(obj_ceil)


if __name__ == "__main__":
    # Default to the gothic mega-library build. The original blockout is still
    # available via create_blockout() if needed for quick shell scenes.
    create_gothic_megalibrary()
