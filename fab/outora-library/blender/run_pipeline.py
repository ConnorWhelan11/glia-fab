"""
Complete Gothic Library Pipeline - Full generation, materials, lighting, and validation.

Runs the complete pipeline:
1. Generate kit pieces (gothic_kit_generator.py)
2. Bake layout with kit pieces (bake_gothic_v2.py)
3. Apply materials (gothic_materials.py)
4. Set up lighting (gothic_lighting.py)
5. Run gate validation (gate_validation.py)

Usage in Blender:
    exec(open("run_pipeline.py").read())

Or run individual stages:
    import run_pipeline as pipeline
    pipeline.run_stage_1_kit_pieces()
    pipeline.run_stage_2_bake_layout()
    pipeline.run_stage_3_materials()
    pipeline.run_stage_4_lighting()
    pipeline.run_stage_5_validation()
"""

import bpy
import sys
from pathlib import Path
from datetime import datetime

# Add script directory to path
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


# =============================================================================
# PIPELINE CONFIGURATION
# =============================================================================

PIPELINE_CONFIG = {
    "name": "Gothic Mega Library",
    "version": "2.0",
    "output_dir": "/tmp/outora-gothic-v2",
    "blend_file": "outora_gothic_v2.blend",
    # Stage toggles
    "stages": {
        "kit_pieces": True,
        "bake_layout": True,
        "materials": True,
        "lighting": True,
        "validation": True,
    },
    # Lighting preset
    "lighting_preset": "dramatic",  # "dramatic", "warm_reading", "cosmic"
    # Bake mode
    "bake_mode": "all",  # "all", "hierarchy", "tier_1", "tier_2", "tier_3"
}


# =============================================================================
# STAGE 1: KIT PIECES
# =============================================================================


def run_stage_1_kit_pieces():
    """Generate all Gothic kit pieces."""
    print("\n" + "=" * 60)
    print("STAGE 1: GENERATING KIT PIECES")
    print("=" * 60)

    try:
        import gothic_kit_generator as kit

        kit.generate_all_pieces()
        print("✅ Kit pieces generated successfully")
        return True
    except Exception as e:
        print(f"❌ Kit piece generation failed: {e}")
        return False


# =============================================================================
# STAGE 2: BAKE LAYOUT
# =============================================================================


def run_stage_2_bake_layout(mode: str = "all"):
    """
    Bake the Gothic layout with kit pieces.

    Modes:
    - "all": Full layout
    - "hierarchy": With tier color visualization
    - "tier_1", "tier_2", "tier_3": Individual tiers
    """
    print("\n" + "=" * 60)
    print(f"STAGE 2: BAKING LAYOUT (mode: {mode})")
    print("=" * 60)

    try:
        import bake_gothic_v2 as bake

        if mode == "all":
            bake.bake_all()
        elif mode == "hierarchy":
            bake.bake_hierarchy_visualization()
        elif mode.startswith("tier_"):
            tier = int(mode.split("_")[1])
            bake.bake_by_tier(tier)
        else:
            print(f"Unknown mode: {mode}, using 'all'")
            bake.bake_all()

        print("✅ Layout baked successfully")
        return True
    except Exception as e:
        print(f"❌ Layout baking failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# =============================================================================
# STAGE 3: MATERIALS
# =============================================================================


def run_stage_3_materials():
    """Create and apply all materials."""
    print("\n" + "=" * 60)
    print("STAGE 3: APPLYING MATERIALS")
    print("=" * 60)

    try:
        import gothic_materials as mats

        # Create all materials
        mats.create_all_materials()

        # Apply to scene
        mats.apply_materials_to_scene()

        print("✅ Materials applied successfully")
        return True
    except Exception as e:
        print(f"❌ Material application failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# =============================================================================
# STAGE 4: LIGHTING
# =============================================================================


def run_stage_4_lighting(preset: str = "dramatic"):
    """
    Set up lighting.

    Presets:
    - "dramatic": High contrast cathedral lighting
    - "warm_reading": Cozy study atmosphere
    - "cosmic": Outora purple mystical
    """
    print("\n" + "=" * 60)
    print(f"STAGE 4: SETTING UP LIGHTING (preset: {preset})")
    print("=" * 60)

    try:
        import gothic_lighting as lights

        if preset == "dramatic":
            lights.preset_dramatic()
        elif preset == "warm_reading":
            lights.preset_warm_reading()
        elif preset == "cosmic":
            lights.preset_cosmic()
        else:
            lights.create_lighting_setup()

        print("✅ Lighting setup complete")
        return True
    except Exception as e:
        print(f"❌ Lighting setup failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# =============================================================================
# STAGE 5: VALIDATION
# =============================================================================


def run_stage_5_validation():
    """Run gate validation and generate report."""
    print("\n" + "=" * 60)
    print("STAGE 5: RUNNING GATE VALIDATION")
    print("=" * 60)

    try:
        import gate_validation as gate

        report = gate.run_full_validation()
        gate.print_report(report)

        # Save report
        output_dir = Path(PIPELINE_CONFIG["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "gate_report.json"
        gate.save_report(report, str(report_path))

        if not report.overall_passed:
            gate.print_repair_instructions(report)

        return report.overall_passed, report
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


# =============================================================================
# FULL PIPELINE
# =============================================================================


def run_full_pipeline():
    """
    Run the complete pipeline.

    Returns:
        Tuple[bool, dict]: (success, results_dict)
    """
    print("\n" + "=" * 70)
    print("GOTHIC MEGA LIBRARY - FULL PIPELINE")
    print(f"Version: {PIPELINE_CONFIG['version']}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    results = {
        "stages": {},
        "overall_success": False,
        "validation_passed": False,
    }

    stages = PIPELINE_CONFIG["stages"]

    # Stage 1: Kit pieces
    if stages.get("kit_pieces", True):
        results["stages"]["kit_pieces"] = run_stage_1_kit_pieces()

    # Stage 2: Bake layout
    if stages.get("bake_layout", True):
        mode = PIPELINE_CONFIG.get("bake_mode", "all")
        results["stages"]["bake_layout"] = run_stage_2_bake_layout(mode)

    # Stage 3: Materials
    if stages.get("materials", True):
        results["stages"]["materials"] = run_stage_3_materials()

    # Stage 4: Lighting
    if stages.get("lighting", True):
        preset = PIPELINE_CONFIG.get("lighting_preset", "dramatic")
        results["stages"]["lighting"] = run_stage_4_lighting(preset)

    # Stage 5: Validation
    if stages.get("validation", True):
        passed, report = run_stage_5_validation()
        results["stages"]["validation"] = passed
        results["validation_passed"] = passed
        results["validation_report"] = report

    # Overall success
    results["overall_success"] = all(results["stages"].values())

    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)

    for stage, success in results["stages"].items():
        status = "✅" if success else "❌"
        print(f"   {status} {stage}")

    print()
    if results["overall_success"] and results.get("validation_passed"):
        print("🎉 PIPELINE COMPLETE - ALL STAGES PASSED!")
    elif results["overall_success"]:
        print("⚠️ Pipeline complete but validation failed - see repair instructions")
    else:
        print("❌ Pipeline had failures - check logs above")

    print("=" * 70 + "\n")

    # Save blend file
    if results["overall_success"]:
        save_blend_file()

    return results["overall_success"], results


def save_blend_file():
    """Save the current scene to a blend file."""
    output_dir = Path(PIPELINE_CONFIG["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / PIPELINE_CONFIG["blend_file"]
    bpy.ops.wm.save_as_mainfile(filepath=str(filepath))
    print(f"\n📁 Saved: {filepath}")


# =============================================================================
# QUICK COMMANDS
# =============================================================================


def quick_rebuild():
    """Quick rebuild - skip kit pieces (already generated)."""
    print("\n🔄 Quick rebuild (skipping kit generation)...")

    PIPELINE_CONFIG["stages"]["kit_pieces"] = False
    run_full_pipeline()


def quick_validate():
    """Just run validation on current scene."""
    return run_stage_5_validation()


def render_preview(filepath: str = None):
    """Render a quick preview."""
    if filepath is None:
        output_dir = Path(PIPELINE_CONFIG["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = str(output_dir / "preview.png")

    # Set up quick render settings
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.filepath = filepath

    # Create camera if needed
    if not scene.camera:
        bpy.ops.object.camera_add(location=(40, -40, 25))
        cam = bpy.context.active_object
        cam.rotation_euler = (1.1, 0, 0.8)
        scene.camera = cam

    # Render
    print(f"\n📷 Rendering preview to: {filepath}")
    bpy.ops.render.render(write_still=True)
    print("✅ Preview rendered")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Run full pipeline
    success, results = run_full_pipeline()

    # Optionally render preview
    # render_preview()
