#!/usr/bin/env python3
"""
Optimize GLB Files - Draco compression and texture reduction.

This script:
1. Re-exports GLB files with Draco compression
2. Reduces texture sizes for web delivery
3. Decimates high-poly meshes

Run with:
    blender --background --python optimize_glb.py -- --input /tmp/outora-library-exports --output /tmp/outora-library-optimized
"""

import bpy
import os
import sys
from pathlib import Path


# Default settings
DEFAULT_INPUT = Path("/tmp/outora-library-exports")
DEFAULT_OUTPUT = Path("/tmp/outora-library-optimized")

OPTIMIZATION_SETTINGS = {
    "draco_compression": True,
    "draco_compression_level": 6,  # 0-10, higher = smaller but slower
    "max_texture_size": 1024,  # Max texture dimension
    "decimate_ratio": 0.5,  # Keep 50% of triangles for high-poly
    "decimate_threshold": 100000,  # Only decimate if > this many tris
}


def parse_args():
    """Parse command line arguments."""
    argv = sys.argv
    input_dir = DEFAULT_INPUT
    output_dir = DEFAULT_OUTPUT

    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
        for i, arg in enumerate(args):
            if arg == "--input" and i + 1 < len(args):
                input_dir = Path(args[i + 1])
            elif arg == "--output" and i + 1 < len(args):
                output_dir = Path(args[i + 1])

    return input_dir, output_dir


def clear_scene():
    """Clear all objects from scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Clear orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)
    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)


def import_glb(filepath):
    """Import a GLB file."""
    bpy.ops.import_scene.gltf(filepath=str(filepath))
    return bpy.context.selected_objects


def resize_textures(max_size):
    """Resize all textures to max_size."""
    resized = 0
    for image in bpy.data.images:
        if image.size[0] > max_size or image.size[1] > max_size:
            # Calculate new size
            ratio = min(max_size / image.size[0], max_size / image.size[1])
            new_width = int(image.size[0] * ratio)
            new_height = int(image.size[1] * ratio)

            image.scale(new_width, new_height)
            resized += 1
            print(f"      Resized: {image.name} -> {new_width}x{new_height}")

    return resized


def decimate_mesh(obj, ratio):
    """Apply decimation to a mesh object."""
    if obj.type != "MESH":
        return False

    # Count triangles
    tri_count = len(obj.data.polygons)
    if tri_count < OPTIMIZATION_SETTINGS["decimate_threshold"]:
        return False

    # Add decimate modifier
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
    modifier.ratio = ratio

    # Apply modifier
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    new_count = len(obj.data.polygons)
    print(f"      Decimated: {obj.name} {tri_count:,} -> {new_count:,} tris")
    return True


def export_glb_optimized(filepath, use_draco=True):
    """Export to GLB with Draco compression."""
    export_args = {
        "filepath": str(filepath),
        "use_selection": False,
        "export_format": "GLB",
        "export_texcoords": True,
        "export_normals": True,
        "export_materials": "EXPORT",
        "export_cameras": False,
        "export_lights": False,
    }

    if use_draco:
        export_args["export_draco_mesh_compression_enable"] = True
        export_args["export_draco_mesh_compression_level"] = OPTIMIZATION_SETTINGS[
            "draco_compression_level"
        ]

    try:
        bpy.ops.export_scene.gltf(**export_args)
        return True
    except Exception as e:
        print(f"      Export error: {e}")
        # Try without Draco
        export_args.pop("export_draco_mesh_compression_enable", None)
        export_args.pop("export_draco_mesh_compression_level", None)
        bpy.ops.export_scene.gltf(**export_args)
        return True


def get_file_size(filepath):
    """Get file size in MB."""
    return filepath.stat().st_size / (1024 * 1024)


def optimize_glb(input_path, output_path):
    """Optimize a single GLB file."""
    print(f"\n  Processing: {input_path.name}")

    original_size = get_file_size(input_path)
    print(f"    Original size: {original_size:.1f} MB")

    # Clear scene
    clear_scene()

    # Import
    try:
        import_glb(input_path)
    except Exception as e:
        print(f"    Import error: {e}")
        return None

    # Resize textures
    resized = resize_textures(OPTIMIZATION_SETTINGS["max_texture_size"])
    if resized > 0:
        print(f"    Resized {resized} textures")

    # Decimate high-poly meshes
    decimated = 0
    for obj in bpy.data.objects:
        if decimate_mesh(obj, OPTIMIZATION_SETTINGS["decimate_ratio"]):
            decimated += 1
    if decimated > 0:
        print(f"    Decimated {decimated} meshes")

    # Export with Draco
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_glb_optimized(output_path, OPTIMIZATION_SETTINGS["draco_compression"])

    if output_path.exists():
        new_size = get_file_size(output_path)
        reduction = (1 - new_size / original_size) * 100
        print(f"    Optimized size: {new_size:.1f} MB ({reduction:.0f}% reduction)")
        return {"original": original_size, "optimized": new_size}

    return None


def main():
    input_dir, output_dir = parse_args()

    print("\n" + "=" * 60)
    print("GLB OPTIMIZATION")
    print("=" * 60)
    print(f"\nInput: {input_dir}")
    print(f"Output: {output_dir}")
    print(f"\nSettings:")
    for key, value in OPTIMIZATION_SETTINGS.items():
        print(f"  {key}: {value}")

    # Find all GLB files
    glb_files = list(input_dir.rglob("*.glb"))
    print(f"\nFound {len(glb_files)} GLB files")

    if not glb_files:
        print("No files to process!")
        return

    # Process each file
    results = []
    for glb_path in glb_files:
        # Preserve directory structure
        rel_path = glb_path.relative_to(input_dir)
        output_path = output_dir / rel_path

        result = optimize_glb(glb_path, output_path)
        if result:
            results.append({"file": glb_path.name, **result})

    # Summary
    print("\n" + "=" * 60)
    print("OPTIMIZATION COMPLETE")
    print("=" * 60)

    if results:
        total_original = sum(r["original"] for r in results)
        total_optimized = sum(r["optimized"] for r in results)
        total_reduction = (1 - total_optimized / total_original) * 100

        print(f"\n  Files processed: {len(results)}")
        print(f"  Total original: {total_original:.1f} MB")
        print(f"  Total optimized: {total_optimized:.1f} MB")
        print(f"  Overall reduction: {total_reduction:.0f}%")

    print(f"\n  Output: {output_dir}")


if __name__ == "__main__":
    main()
