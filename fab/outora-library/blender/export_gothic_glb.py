"""
Export Gothic Library to GLB - For Three.js viewer.

Exports the complete Gothic library scene to GLB format with:
- Draco compression
- Materials included
- Optimized for web viewing

Usage in Blender:
    exec(open("export_gothic_glb.py").read())
"""

import bpy
from pathlib import Path


def export_scene_glb(output_dir: str = "/tmp/outora-gothic-v2"):
    """Export the full scene as GLB."""
    print("\n" + "=" * 60)
    print("EXPORTING TO GLB")
    print("=" * 60)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Select all mesh and light objects
    bpy.ops.object.select_all(action='DESELECT')
    
    mesh_count = 0
    for obj in bpy.context.scene.objects:
        if obj.type in {'MESH', 'LIGHT', 'CAMERA'}:
            obj.select_set(True)
            mesh_count += 1
    
    print(f"\n   Selected {mesh_count} objects for export")
    
    # Export full scene (WITHOUT lights - let Three.js handle lighting)
    full_path = str(output_path / "gothic_library_full.glb")
    print(f"   Exporting full scene to: {full_path}")
    
    bpy.ops.export_scene.gltf(
        filepath=full_path,
        export_format='GLB',
        use_selection=False,  # Export all
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_cameras=False,  # No cameras
        export_lights=False,   # No lights - they're too bright in Three.js
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
    )
    
    # Also export just the crossing area (for faster loading)
    bpy.ops.object.select_all(action='DESELECT')
    
    crossing_count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        
        # Select objects near the center (crossing)
        dist = (obj.location.x ** 2 + obj.location.y ** 2) ** 0.5
        if dist < 20:  # Within 20m of center
            obj.select_set(True)
            crossing_count += 1
    
    crossing_path = str(output_path / "gothic_crossing.glb")
    print(f"   Exporting crossing ({crossing_count} objects) to: {crossing_path}")
    
    bpy.ops.export_scene.gltf(
        filepath=crossing_path,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_cameras=False,
        export_lights=False,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
    )
    
    # Get file sizes
    full_size = Path(full_path).stat().st_size / (1024 * 1024)
    crossing_size = Path(crossing_path).stat().st_size / (1024 * 1024)
    
    print(f"\n✅ Export complete:")
    print(f"   Full scene: {full_size:.2f} MB")
    print(f"   Crossing: {crossing_size:.2f} MB")
    print("=" * 60 + "\n")
    
    return {
        "full": full_path,
        "crossing": crossing_path,
    }


if __name__ == "__main__":
    export_scene_glb()

