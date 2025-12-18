import bpy
import math
import random


def integrate_assets():
    # 1. Organize Imported Assets
    # Create a collection for source assets if it doesn't exist
    coll_assets = bpy.data.collections.get("OL_ASSETS_SOURCE")
    if not coll_assets:
        coll_assets = bpy.data.collections.new("OL_ASSETS_SOURCE")
        bpy.context.scene.collection.children.link(coll_assets)
        coll_assets.hide_render = True  # Hide source assets from render
        coll_assets.hide_viewport = True  # Hide from viewport

    # Identify source objects
    # Based on previous `list_objects` output
    asset_map = {
        "desk": "WoodenTable_02",
        "chair": "WoodenChair_01",
        "shelf": "Shelf_01",
        "lamp": "desk_lamp_arm_01",
    }

    # Move main assets to source collection
    for key, name in asset_map.items():
        obj = bpy.data.objects.get(name)
        if obj:
            # Link to assets collection, unlink from others
            if obj.name not in coll_assets.objects:
                coll_assets.objects.link(obj)

            cols_to_unlink = [col for col in obj.users_collection if col != coll_assets]
            for col in cols_to_unlink:
                col.objects.unlink(obj)

            # Reset transform just in case
            obj.location = (0, 0, 0)

    # Handle Books (Multiple objects)
    books = [obj for obj in bpy.data.objects if "book_encyclopedia" in obj.name]
    for book in books:
        if book.name not in coll_assets.objects:
            coll_assets.objects.link(book)

        cols_to_unlink = [col for col in book.users_collection if col != coll_assets]
        for col in cols_to_unlink:
            col.objects.unlink(book)

    # Create a "Book Cluster" Collection instance for easier scattering?
    # Actually, let's just pick random books to place on shelves.

    # 2. Replace Proxies
    coll_proxies = bpy.data.collections.get("OL_PROXIES")
    coll_final = bpy.data.collections.get("OL_SCENE_FINAL")
    if not coll_final:
        coll_final = bpy.data.collections.new("OL_SCENE_FINAL")
        bpy.context.scene.collection.children.link(coll_final)

    # Cleanup existing final objects to avoid duplicates
    objects_to_remove = []
    for obj in coll_final.objects:
        objects_to_remove.append(obj)

    for obj in objects_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)

    if not coll_proxies:
        print("No proxies found!")
        return

    # A. Shelves
    shelf_asset = bpy.data.objects.get(asset_map["shelf"])
    if shelf_asset:
        proxies = [o for o in coll_proxies.objects if "ol_proxy_shelf" in o.name]
        for proxy in proxies:
            # Create instance
            inst = shelf_asset.copy()
            inst.data = shelf_asset.data  # Linked mesh
            inst.name = proxy.name.replace("proxy", "final")

            # Match proxy transform
            inst.location = proxy.location
            inst.rotation_euler = proxy.rotation_euler

            # Adjustments for the specific asset (Wooden Shelf 01)
            # The asset seems to face outward (or backward) by default relative to our proxy rotation.
            # We rotate it 180 degrees (pi) to face inward.
            inst.rotation_euler.z += math.pi

            # Add to final collection
            coll_final.objects.link(inst)

            # B. Populate Books on this Shelf
            # Shelf dimensions: ~1.0m wide, ~2.08m tall.
            # Levels approx: 0.15, 0.6, 1.05, 1.5, 1.95 (Checking bounds 0 to 2.08)
            populate_shelf_with_books(inst, books, coll_final)

    # B. Desk and Extra Seating
    # 1. Hero Desk
    desk_asset = bpy.data.objects.get(asset_map["desk"])
    proxy_desk = bpy.data.objects.get("ol_proxy_desk")

    if desk_asset and proxy_desk:
        inst = desk_asset.copy()
        inst.data = desk_asset.data
        inst.name = "ol_hero_desk"
        inst.location = proxy_desk.location
        inst.rotation_euler = proxy_desk.rotation_euler
        inst.location.z = 0  # Floor
        coll_final.objects.link(inst)

        # Place Lamp on Desk
        lamp_asset = bpy.data.objects.get(asset_map["lamp"])
        if lamp_asset:
            l_inst = lamp_asset.copy()
            l_inst.data = lamp_asset.data
            l_inst.name = "ol_hero_lamp"
            # Offset relative to desk
            l_inst.location = inst.location
            l_inst.location.x -= 0.6
            l_inst.location.y += 0.3
            l_inst.location.z += 0.75  # Table height
            coll_final.objects.link(l_inst)

    # 2. Hero Chair
    chair_asset = bpy.data.objects.get(asset_map["chair"])
    if chair_asset:
        inst = chair_asset.copy()
        inst.data = chair_asset.data
        inst.name = "ol_hero_chair"
        inst.location = (0, 0.4, 0)
        inst.rotation_euler = (0, 0, 0)
        coll_final.objects.link(inst)

    # 3. Extra Tables/Chairs (Density)
    # Place 2 more tables on the sides
    # Locations: (+4, +2), (-4, +2) ?
    # Or rotated around the ring.
    extra_positions = [
        ((3.5, 2.5, 0), -0.5),  # Right
        ((-3.5, 2.5, 0), 0.5),  # Left
    ]

    if desk_asset and chair_asset:
        for i, (loc, rot_z) in enumerate(extra_positions):
            # Table
            t_inst = desk_asset.copy()
            t_inst.data = desk_asset.data
            t_inst.name = f"ol_extra_table_{i}"
            t_inst.location = loc
            t_inst.rotation_euler = (0, 0, rot_z)
            coll_final.objects.link(t_inst)

            # Chair (behind table)
            c_inst = chair_asset.copy()
            c_inst.data = chair_asset.data
            c_inst.name = f"ol_extra_chair_{i}"
            # Simple offset logic: move 0.8m along local -Y of table
            # Table local Y is forward/back? Assume chair is behind.
            import mathutils

            offset = mathutils.Vector((0, -0.8, 0))
            # Rotation matrix
            mat_rot = mathutils.Euler((0, 0, rot_z)).to_matrix().to_4x4()
            world_offset = mat_rot @ offset

            c_inst.location = mathutils.Vector(loc) + world_offset
            c_inst.rotation_euler = (0, 0, rot_z)
            coll_final.objects.link(c_inst)

    # Hide Proxies
    coll_proxies.hide_viewport = True
    coll_proxies.hide_render = True


def populate_shelf_with_books(shelf_inst, book_assets, collection):
    if not book_assets:
        return

    # Revised Shelf Levels (based on 2.08m height)
    # Assumed 5 shelves evenly spaced
    row_heights = [0.2, 0.6, 1.0, 1.4, 1.8]  # Local Z

    import mathutils

    shelf_matrix = shelf_inst.matrix_world

    for z_level in row_heights:
        # Fill row with 90% probability (denser)
        if random.random() > 0.9:
            continue

        # Place books
        current_x = -0.40  # Start left (shelf width ~1m, so -0.5 to 0.5)

        while current_x < 0.40:
            # Gap probability
            if random.random() > 0.9:
                current_x += random.uniform(0.05, 0.1)
                continue

            book_proto = random.choice(book_assets)
            b_inst = book_proto.copy()
            b_inst.data = book_proto.data

            # Randomize thickness/scale
            scale_z = random.uniform(0.9, 1.05)
            scale_thick = random.uniform(0.8, 1.2)
            b_inst.scale = (1.0, scale_thick, scale_z)  # Assuming Y is thickness?
            # Actually book assets usually X is thickness, Y/Z cover.
            # Let's assume standard scale for now or check.

            width = 0.035 * scale_thick  # Approx width per book

            # Local pos
            # Shelf Y depth is -0.26 to 0. Center books at -0.13?
            local_pos = mathutils.Vector((current_x, -0.13, z_level))

            # Apply world matrix
            b_inst.location = shelf_matrix @ local_pos

            # Rotation
            # Shelf is rotated. Books need to align with shelf Y axis.
            # Shelf local Y points BACK (0) to FRONT (-0.26)? No, usually Front is -Y.
            # If Shelf rotated 180, then Local -Y is facing Inward.
            # Books should face Local -Y.

            shelf_rot = shelf_inst.rotation_euler.z
            jitter = random.uniform(-0.05, 0.05)

            # Book rotation logic:
            # If books default is Spine +Y? Or Spine -Y?
            # Usually books are Z-up. Spine often -Y.
            # Let's align them to shelf rotation.
            b_inst.rotation_euler = (0, 0, shelf_rot + jitter)
            # If they appear sideways, we add pi/2.
            # Previous code added pi/2. Let's keep it aligned for now, correct if wrong.

            collection.objects.link(b_inst)

            current_x += width


if __name__ == "__main__":
    integrate_assets()
