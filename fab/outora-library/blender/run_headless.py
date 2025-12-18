"""
Headless Pipeline Runner - Execute in Blender background mode.

Usage:
    /Applications/Blender.app/Contents/MacOS/Blender --background --python run_headless.py
"""

import bpy
import sys
from pathlib import Path

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

print("\n" + "=" * 70)
print("GOTHIC MEGA LIBRARY - HEADLESS PIPELINE")
print("=" * 70)

# Clear existing scene
print("\n🗑️ Clearing scene...")
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for col in list(bpy.data.collections):
    if col.name != "Collection":
        bpy.data.collections.remove(col)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for light in list(bpy.data.lights):
    bpy.data.lights.remove(light)
print("   ✅ Scene cleared")

# Stage 1: Kit Pieces
print("\n" + "=" * 60)
print("STAGE 1: GENERATING KIT PIECES")
print("=" * 60)
try:
    import gothic_kit_generator as kit
    kit.generate_all_pieces()
    kit_count = len([o for o in bpy.data.objects if o.name.startswith("GK_")])
    print(f"   ✅ Kit pieces generated: {kit_count}")
except Exception as e:
    print(f"   ❌ Kit pieces failed: {e}")
    import traceback
    traceback.print_exc()

# Stage 2: Bake Layout
print("\n" + "=" * 60)
print("STAGE 2: BAKING LAYOUT")
print("=" * 60)
try:
    import bake_gothic_v2 as bake
    bake.bake_all()
    mesh_count = sum(1 for obj in bpy.context.scene.objects if obj.type == 'MESH')
    print(f"   ✅ Layout baked: {mesh_count} mesh objects")
except Exception as e:
    print(f"   ❌ Layout baking failed: {e}")
    import traceback
    traceback.print_exc()

# Stage 3: Materials
print("\n" + "=" * 60)
print("STAGE 3: APPLYING MATERIALS")
print("=" * 60)
try:
    import gothic_materials as mats
    mats.create_all_materials()
    mats.apply_materials_to_scene()
    mat_count = len(bpy.data.materials)
    print(f"   ✅ Materials applied: {mat_count} materials")
except Exception as e:
    print(f"   ❌ Materials failed: {e}")
    import traceback
    traceback.print_exc()

# Stage 4: Lighting
print("\n" + "=" * 60)
print("STAGE 4: SETTING UP LIGHTING")
print("=" * 60)
try:
    import gothic_lighting as lights
    lights.preset_dramatic()
    light_count = sum(1 for obj in bpy.context.scene.objects if obj.type == 'LIGHT')
    print(f"   ✅ Lighting setup: {light_count} lights")
except Exception as e:
    print(f"   ❌ Lighting failed: {e}")
    import traceback
    traceback.print_exc()

# Stage 4.5: Furniture
print("\n" + "=" * 60)
print("STAGE 4.5: ADDING FURNITURE")
print("=" * 60)
try:
    import add_furniture as furniture
    furniture.add_all_furniture()
    desk_count = sum(1 for obj in bpy.context.scene.objects if 'desk' in obj.name.lower())
    chair_count = sum(1 for obj in bpy.context.scene.objects if 'chair' in obj.name.lower())
    print(f"   ✅ Furniture added: {desk_count} desks, {chair_count} chairs")
except Exception as e:
    print(f"   ❌ Furniture failed: {e}")
    import traceback
    traceback.print_exc()

# Stage 5: Validation
print("\n" + "=" * 60)
print("STAGE 5: RUNNING GATE VALIDATION")
print("=" * 60)
try:
    import gate_validation as gate
    report = gate.run_full_validation()
    gate.print_report(report)
    
    # Save report
    output_dir = Path("/tmp/outora-gothic-v2")
    output_dir.mkdir(parents=True, exist_ok=True)
    gate.save_report(report, str(output_dir / "gate_report.json"))
    
    if not report.overall_passed:
        gate.print_repair_instructions(report)
except Exception as e:
    print(f"   ❌ Validation failed: {e}")
    import traceback
    traceback.print_exc()

# Save blend file
print("\n" + "=" * 60)
print("SAVING BLEND FILE")
print("=" * 60)
output_path = "/tmp/outora-gothic-v2/outora_gothic_v2.blend"
Path(output_path).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"   📁 Saved: {output_path}")

# Export to GLB for Three.js viewer
print("\n" + "=" * 60)
print("EXPORTING GLB FOR VIEWER")
print("=" * 60)
try:
    import export_gothic_glb as exporter
    exports = exporter.export_scene_glb("/tmp/outora-gothic-v2")
    print(f"   ✅ GLB files exported")
except Exception as e:
    print(f"   ❌ Export failed: {e}")
    import traceback
    traceback.print_exc()

# Final stats
print("\n" + "=" * 70)
print("PIPELINE COMPLETE")
print("=" * 70)
print(f"   Mesh objects: {sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')}")
print(f"   Lights: {sum(1 for o in bpy.context.scene.objects if o.type == 'LIGHT')}")
print(f"   Materials: {len(bpy.data.materials)}")
print(f"   Collections: {len(bpy.data.collections)}")
print("=" * 70 + "\n")

