import bpy
import math


def create_camera(name, location, rotation_euler, focal_length=50, type="PERSP"):
    # Remove existing if present
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = focal_length
    cam_data.type = type

    cam_obj = bpy.data.objects.new(name, cam_data)
    cam_obj.location = location
    cam_obj.rotation_euler = rotation_euler
    return cam_obj


def setup_cameras():
    # Collection for cameras
    col_name = "OL_CAMERAS"
    col = bpy.data.collections.get(col_name)
    if not col:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # 1. Nave Hero (Entrance looking North)
    # Positioned at South end (-20m) looking North (+Y)
    c1 = create_camera(
        "CAM_Nave_Hero",
        location=(0, -24, 1.8),
        rotation_euler=(math.radians(90), 0, 0),
        focal_length=35,
    )

    # 2. Crossing High (Looking down at chandelier)
    c2 = create_camera(
        "CAM_Crossing_High",
        location=(12, -12, 14),
        rotation_euler=(math.radians(60), 0, math.radians(45)),
        focal_length=24,
    )

    # 3. Reading Nook (Inside a wing aisle)
    # Aisle is at X ~ 9m. Y ~ 15m.
    c3 = create_camera(
        "CAM_Reading_Nook",
        location=(9, 15, 1.4),  # Seated height
        rotation_euler=(
            math.radians(90),
            0,
            math.radians(150),
        ),  # Looking slightly back/inward
        focal_length=50,
    )

    # 4. Mezzanine Balcony
    c4 = create_camera(
        "CAM_Mezzanine_View",
        location=(-6, -6, 6.7),  # On mezzanine (+5m floor + 1.7m eye)
        rotation_euler=(math.radians(80), 0, math.radians(-45)),
        focal_length=35,
    )

    # 5. Top Down
    c5 = create_camera(
        "CAM_Top_Down",
        location=(0, 0, 80),
        rotation_euler=(0, 0, 0),
        focal_length=50,
        type="ORTHO",
    )
    c5.data.ortho_scale = 60

    # Link all to collection
    cameras = [c1, c2, c3, c4, c5]
    for cam in cameras:
        if cam.name not in col.objects:
            col.objects.link(cam)

    # Make Nave Hero active
    bpy.context.scene.camera = c1

    print(f"Created {len(cameras)} cameras in {col_name}")


if __name__ == "__main__":
    setup_cameras()
