"""
Import reference materials and a few modular meshes from the purchased
gothic_library_2_cycles.blend without merging the whole scene.

Usage (from Blender Scripting):
    import importlib, import_gothic_reference
    importlib.reload(import_gothic_reference)
    import_gothic_reference.append_reference()
"""

import bpy
from pathlib import Path

LIB_NAME = "gothic_library_2_cycles.blend"
REF_COLLECTION = "OL_IMPORTED_REFERENCE"

# Materials to sample (will only append if they exist in the source)
MATERIAL_NAMES = [
    "Wood floor",
    "Glossy wood",
    "Stone",
    "Sandstone bricks",
    "Procedural stained glass",
    "Metal",
    "SHC Old Book Material",
    "Leather",
]

# Lightweight modular meshes to study proportions/details (not whole scene)
OBJECT_NAMES = [
    "Wooden railing ",
    "Wooden railing end",
    "Wooden railing pillars",
    "Wood floor edges",
    "Wall.025",
    "Wall.024",
]


def ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def append_materials(lib_path: Path):
    with bpy.data.libraries.load(str(lib_path), link=False) as (data_from, data_to):
        wanted = [n for n in MATERIAL_NAMES if n in data_from.materials]
        data_to.materials = wanted
    appended = [m for m in MATERIAL_NAMES if bpy.data.materials.get(m)]
    return appended


def append_objects(lib_path: Path, target_col: bpy.types.Collection):
    with bpy.data.libraries.load(str(lib_path), link=False) as (data_from, data_to):
        wanted = [n for n in OBJECT_NAMES if n in data_from.objects]
        data_to.objects = wanted
    appended = []
    for obj in data_to.objects:
        if not obj:
            continue
        if obj.name not in target_col.objects:
            target_col.objects.link(obj)
        appended.append(obj.name)
    return appended


def append_reference():
    blend_dir = Path(bpy.path.abspath("//"))
    lib_path = blend_dir / LIB_NAME
    if not lib_path.exists():
        raise FileNotFoundError(f"Missing {LIB_NAME} at {lib_path}")

    target_col = ensure_collection(REF_COLLECTION)

    mats = append_materials(lib_path)
    objs = append_objects(lib_path, target_col)

    print(f"Appended materials: {mats}")
    print(f"Appended objects into {REF_COLLECTION}: {objs}")
    return {"materials": mats, "objects": objs}


if __name__ == "__main__":
    append_reference()
