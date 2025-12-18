#!/usr/bin/env python3
"""
Export Library Sections as GLB - For web/game engine use.

Exports modular sections of the Outora Library:
- Individual study pods
- Structural elements (columns, arches)
- Full wings (nave, transepts)
- Kit pieces

Run with:
    blender outora_library_v0.3.0.blend --background --python export_sections_glb.py
"""

import bpy
import os
from pathlib import Path


OUTPUT_DIR = Path("/tmp/outora-library-exports")


def ensure_output_dir():
    """Create output directory structure."""
    dirs = [
        OUTPUT_DIR,
        OUTPUT_DIR / "pods",
        OUTPUT_DIR / "structure",
        OUTPUT_DIR / "wings",
        OUTPUT_DIR / "kit",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def select_collection_objects(collection_name):
    """Select all objects in a collection (recursively)."""
    bpy.ops.object.select_all(action="DESELECT")
    
    col = bpy.data.collections.get(collection_name)
    if not col:
        print(f"    Warning: Collection '{collection_name}' not found")
        return False
    
    def select_recursive(c):
        for obj in c.objects:
            if obj.type in {"MESH", "CURVE", "SURFACE"}:
                obj.select_set(True)
        for child in c.children:
            select_recursive(child)
    
    select_recursive(col)
    return True


def export_glb(filepath, export_selected=True):
    """Export to GLB with optimized settings (Blender 5.x compatible)."""
    # Blender 5.x changed some export parameters
    export_args = {
        "filepath": str(filepath),
        "use_selection": export_selected,
        "export_format": "GLB",
        "export_texcoords": True,
        "export_normals": True,
        "export_materials": "EXPORT",
        "export_cameras": False,
        "export_lights": False,
        "export_apply": True,
    }
    
    # Try with export_colors (older Blender), fall back without
    try:
        bpy.ops.export_scene.gltf(**export_args, export_colors=True)
    except TypeError:
        bpy.ops.export_scene.gltf(**export_args)


def export_study_pods():
    """Export each study pod as individual GLB."""
    print("\n  Exporting study pods...")
    
    pods_exported = 0
    for col in bpy.data.collections:
        if col.name.startswith("StudyPod_"):
            student = col.name.replace("StudyPod_", "")
            
            if select_collection_objects(col.name):
                selected = len([o for o in bpy.context.selected_objects])
                if selected > 0:
                    filepath = OUTPUT_DIR / "pods" / f"{student}.glb"
                    export_glb(filepath)
                    print(f"    {student}: {selected} objects -> {filepath.name}")
                    pods_exported += 1
    
    return pods_exported


def export_kit_pieces():
    """Export kit pieces (assets collection)."""
    print("\n  Exporting kit pieces...")
    
    # Look for asset collections
    kit_collections = [
        "OL_Assets",
        "OL_Kit",
        "Kit",
        "Assets",
    ]
    
    exported = 0
    for col_name in kit_collections:
        col = bpy.data.collections.get(col_name)
        if col:
            # Export each child collection as separate piece
            for child in col.children:
                if select_collection_objects(child.name):
                    selected = len([o for o in bpy.context.selected_objects])
                    if selected > 0:
                        safe_name = child.name.replace(" ", "_").lower()
                        filepath = OUTPUT_DIR / "kit" / f"{safe_name}.glb"
                        export_glb(filepath)
                        print(f"    {child.name}: {selected} objects -> {filepath.name}")
                        exported += 1
            
            # Also export the full kit
            if select_collection_objects(col_name):
                selected = len([o for o in bpy.context.selected_objects])
                if selected > 0:
                    filepath = OUTPUT_DIR / "kit" / f"full_kit.glb"
                    export_glb(filepath)
                    print(f"    Full kit: {selected} objects -> full_kit.glb")
                    exported += 1
    
    return exported


def export_structural_elements():
    """Export structural elements (columns, arches, etc.)."""
    print("\n  Exporting structural elements...")
    
    # Look for structure-related collections
    structure_collections = [
        "Structure",
        "Columns",
        "Arches",
        "OL_Structure",
        "Gothic",
        "Floor",
        "Walls",
    ]
    
    exported = 0
    for col_name in structure_collections:
        if select_collection_objects(col_name):
            selected = len([o for o in bpy.context.selected_objects])
            if selected > 0:
                safe_name = col_name.replace(" ", "_").lower()
                filepath = OUTPUT_DIR / "structure" / f"{safe_name}.glb"
                export_glb(filepath)
                print(f"    {col_name}: {selected} objects -> {filepath.name}")
                exported += 1
    
    return exported


def export_wings():
    """Export major wings/sections."""
    print("\n  Exporting wings...")
    
    # Define wing bounding boxes (approximate)
    wings = {
        "nave_south": {"min": (-15, -50, 0), "max": (15, 0, 20)},
        "nave_north": {"min": (-15, 0, 0), "max": (15, 50, 20)},
        "transept_east": {"min": (-50, -15, 0), "max": (0, 15, 20)},
        "transept_west": {"min": (0, -15, 0), "max": (50, 15, 20)},
        "crossing": {"min": (-15, -15, 0), "max": (15, 15, 25)},
    }
    
    exported = 0
    for wing_name, bounds in wings.items():
        bpy.ops.object.select_all(action="DESELECT")
        
        min_b = bounds["min"]
        max_b = bounds["max"]
        
        # Select objects within bounds
        for obj in bpy.data.objects:
            if obj.type not in {"MESH", "CURVE", "SURFACE"}:
                continue
            
            loc = obj.location
            if (min_b[0] <= loc.x <= max_b[0] and
                min_b[1] <= loc.y <= max_b[1] and
                min_b[2] <= loc.z <= max_b[2]):
                obj.select_set(True)
        
        selected = len([o for o in bpy.context.selected_objects])
        if selected > 0:
            filepath = OUTPUT_DIR / "wings" / f"{wing_name}.glb"
            export_glb(filepath)
            print(f"    {wing_name}: {selected} objects -> {filepath.name}")
            exported += 1
    
    return exported


def export_full_scene():
    """Export the entire scene as one GLB."""
    print("\n  Exporting full scene...")
    
    bpy.ops.object.select_all(action="DESELECT")
    
    # Select all mesh objects
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE"}:
            obj.select_set(True)
    
    selected = len([o for o in bpy.context.selected_objects])
    filepath = OUTPUT_DIR / "full_library.glb"
    export_glb(filepath)
    print(f"    Full scene: {selected} objects -> full_library.glb")
    
    return 1


def generate_manifest():
    """Generate a manifest of all exported files."""
    manifest = {
        "name": "Outora Library Exports",
        "version": "0.3.0",
        "files": [],
    }
    
    for glb_file in OUTPUT_DIR.rglob("*.glb"):
        rel_path = glb_file.relative_to(OUTPUT_DIR)
        size_kb = glb_file.stat().st_size / 1024
        manifest["files"].append({
            "path": str(rel_path),
            "size_kb": round(size_kb, 1),
        })
    
    # Write manifest
    import json
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n  Manifest: {manifest_path}")
    return manifest


def main():
    print("\n" + "=" * 60)
    print("OUTORA LIBRARY - GLB EXPORT")
    print("=" * 60)
    
    ensure_output_dir()
    
    stats = {
        "pods": export_study_pods(),
        "kit": export_kit_pieces(),
        "structure": export_structural_elements(),
        "wings": export_wings(),
        "full": export_full_scene(),
    }
    
    manifest = generate_manifest()
    
    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    print(f"\n  Output: {OUTPUT_DIR}")
    print(f"  Total files: {len(manifest['files'])}")
    print("\n  By category:")
    for cat, count in stats.items():
        print(f"    {cat}: {count} files")


if __name__ == "__main__":
    main()

