"""
Clone imported reference materials into Outora-prefixed variants.

This is non-destructive to the source materials appended from
gothic_library_2_cycles.blend. Run from Blender Scripting:

    import importlib, materials_outora_variants
    importlib.reload(materials_outora_variants)
    materials_outora_variants.create_outora_material_variants()
"""

import bpy

MATERIAL_MAP = {
    "Wood floor": "ol_mat_ref_wood_floor",
    "Glossy wood": "ol_mat_ref_wood_gloss",
    "Stone": "ol_mat_ref_stone",
    "Sandstone bricks": "ol_mat_ref_sandstone",
    "Procedural stained glass": "ol_mat_ref_stained_glass",
    "Metal": "ol_mat_ref_metal",
    "SHC Old Book Material": "ol_mat_ref_book_cover",
    "Leather": "ol_mat_ref_leather",
}


def copy_material(src_name: str, dst_name: str) -> bool:
    src = bpy.data.materials.get(src_name)
    if not src:
        print(f"[skip] missing source material: {src_name}")
        return False

    if bpy.data.materials.get(dst_name):
        print(f"[keep] already exists: {dst_name}")
        return True

    dst = src.copy()
    dst.name = dst_name

    # Ensure nodes stay on; no tweaks yet (palette adjustments happen later)
    dst.use_nodes = src.use_nodes

    print(f"[new] {dst_name} cloned from {src_name}")
    return True


def create_outora_material_variants():
    created = []
    skipped = []
    for src, dst in MATERIAL_MAP.items():
        ok = copy_material(src, dst)
        (created if ok else skipped).append(dst if ok else src)
    return {"created_or_existing": created, "missing_sources": skipped}


if __name__ == "__main__":
    create_outora_material_variants()
