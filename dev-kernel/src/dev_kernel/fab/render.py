"""
Fab Render Harness - Headless Blender Rendering

This module provides deterministic canonical rendering of assets through Blender.
It produces beauty renders, clay renders, and render passes for critic evaluation.

Usage:
    python -m dev_kernel.fab.render --help
    python -m dev_kernel.fab.render --asset asset.glb --config car_realism_v001 --out /tmp/renders
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import GateConfig, RenderConfig, load_gate_config, find_gate_config

logger = logging.getLogger(__name__)

# Path to the Blender render script (bundled with this module)
BLENDER_SCRIPT_PATH = Path(__file__).parent / "blender_scripts" / "render_harness.py"


@dataclass
class RenderResult:
    """Result from render harness execution."""

    success: bool
    output_dir: Path
    beauty_renders: List[str] = field(default_factory=list)
    clay_renders: List[str] = field(default_factory=list)
    passes: Dict[str, List[str]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    blender_version: Optional[str] = None
    duration_ms: int = 0


def find_blender() -> Optional[Path]:
    """Find Blender executable on the system."""
    # Common locations - prefer app bundle paths on macOS
    candidates = [
        # macOS app bundle (preferred - has all resources)
        "/Applications/Blender.app/Contents/MacOS/Blender",
        # Linux
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/snap/bin/blender",
        # Windows
        "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 4.1/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 4.0/blender.exe",
    ]

    # Check common locations first (app bundle is more reliable on macOS)
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path

    # Fall back to PATH
    blender_path = shutil.which("blender")
    if blender_path:
        # On macOS, symlinks to the binary may not work properly
        # Check if it's a symlink to an app bundle
        real_path = Path(blender_path).resolve()
        if "Blender.app" in str(real_path):
            # Use the app bundle path instead
            app_path = Path("/Applications/Blender.app/Contents/MacOS/Blender")
            if app_path.exists():
                return app_path
        return real_path

    return None


def get_blender_version(blender_path: Path) -> Optional[str]:
    """Get Blender version string."""
    try:
        result = subprocess.run(
            [str(blender_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse "Blender 4.1.0" from output
            for line in result.stdout.split("\n"):
                if line.startswith("Blender"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
        return None
    except Exception as e:
        logger.warning(f"Failed to get Blender version: {e}")
        return None


def prepare_render_config(
    gate_config: GateConfig,
    asset_path: Path,
    output_dir: Path,
    lookdev_scene: Optional[Path] = None,
    camera_rig: Optional[Path] = None,
) -> Dict[str, Any]:
    """Prepare configuration for Blender script."""
    render = gate_config.render

    return {
        "asset_path": str(asset_path.absolute()),
        "output_dir": str(output_dir.absolute()),
        "lookdev_scene": str(lookdev_scene.absolute()) if lookdev_scene else None,
        "camera_rig": str(camera_rig.absolute()) if camera_rig else None,
        "render": {
            "engine": render.engine,
            "device": render.device,
            "resolution": list(render.resolution),
            "samples": render.samples,
            "seed": render.seed,
            "denoise": render.denoise,
            "threads": render.threads,
            "output_format": render.output_format,
            "color_depth": render.color_depth,
        },
        "views": (
            gate_config.critics.get("category", {}).params
            if gate_config.critics
            else {}
        ),
        "gate_config_id": gate_config.gate_config_id,
    }


def run_blender_render(
    blender_path: Path,
    asset_path: Path,
    output_dir: Path,
    render_config: Dict[str, Any],
    timeout_seconds: int = 900,  # 15 minutes default
) -> RenderResult:
    """
    Run Blender headless to render the asset.

    Args:
        blender_path: Path to Blender executable
        asset_path: Path to asset file (.glb)
        output_dir: Directory for render output
        render_config: Configuration dict for Blender script
        timeout_seconds: Render timeout

    Returns:
        RenderResult with paths to rendered images
    """
    start_time = datetime.now(timezone.utc)

    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "beauty").mkdir(exist_ok=True)
    (output_dir / "clay").mkdir(exist_ok=True)
    (output_dir / "passes").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    # Write config to temp file for Blender script
    config_file = output_dir / "render_config.json"
    with open(config_file, "w") as f:
        json.dump(render_config, f, indent=2)

    # Check if render script exists
    if not BLENDER_SCRIPT_PATH.exists():
        logger.warning(
            f"Blender script not found at {BLENDER_SCRIPT_PATH}, using inline script"
        )
        # Use inline minimal script for now
        script_content = generate_inline_render_script()
        script_file = output_dir / "render_script.py"
        with open(script_file, "w") as f:
            f.write(script_content)
        script_path = script_file
    else:
        script_path = BLENDER_SCRIPT_PATH

    # Build Blender command
    cmd = [
        str(blender_path),
        "--background",
        "--factory-startup",
        "--python",
        str(script_path),
        "--",
        "--config",
        str(config_file),
    ]

    # Set environment for determinism
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    # For macOS app bundle, we need to run from within the bundle directory
    # to ensure Blender can find its resources
    cwd = str(output_dir)
    if "Blender.app" in str(blender_path):
        cwd = str(blender_path.parent)
        logger.info(f"Running from app bundle directory: {cwd}")

    logger.info(f"Running Blender: {' '.join(cmd)}")

    # Run Blender
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            cwd=cwd,
        )

        # Save logs
        stdout_log = output_dir / "logs" / "blender_stdout.log"
        stderr_log = output_dir / "logs" / "blender_stderr.log"
        stdout_log.write_text(result.stdout)
        stderr_log.write_text(result.stderr)

        success = result.returncode == 0

        if not success:
            logger.error(f"Blender failed with exit code {result.returncode}")
            logger.error(f"stderr: {result.stderr[:500]}")

    except subprocess.TimeoutExpired:
        logger.error(f"Blender render timed out after {timeout_seconds}s")
        return RenderResult(
            success=False,
            output_dir=output_dir,
            errors=["RENDER_TIMEOUT"],
        )
    except Exception as e:
        logger.error(f"Blender execution failed: {e}")
        return RenderResult(
            success=False,
            output_dir=output_dir,
            errors=[f"BLENDER_ERROR: {str(e)}"],
        )

    # Collect rendered files
    beauty_renders = sorted([str(p) for p in (output_dir / "beauty").glob("*.png")])
    clay_renders = sorted([str(p) for p in (output_dir / "clay").glob("*.png")])

    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    return RenderResult(
        success=success and len(beauty_renders) > 0,
        output_dir=output_dir,
        beauty_renders=beauty_renders,
        clay_renders=clay_renders,
        passes={},
        errors=[] if success else [f"Exit code: {result.returncode}"],
        blender_version=get_blender_version(blender_path),
        duration_ms=duration_ms,
    )


def generate_inline_render_script() -> str:
    """Generate an inline Blender Python script for rendering."""
    return '''"""
Fab Render Harness - Blender Script
This script is executed inside Blender to perform headless rendering.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy


def setup_render_settings(config: dict):
    """Configure render settings from config."""
    scene = bpy.context.scene
    render = config.get("render", {})
    
    # Engine
    scene.render.engine = "CYCLES" if render.get("engine") == "CYCLES" else "BLENDER_EEVEE"
    
    # Device
    if scene.render.engine == "CYCLES":
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "NONE"
        scene.cycles.device = "CPU"
    
    # Resolution
    res = render.get("resolution", [768, 512])
    scene.render.resolution_x = res[0]
    scene.render.resolution_y = res[1]
    scene.render.resolution_percentage = 100
    
    # Samples
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = render.get("samples", 128)
        scene.cycles.seed = render.get("seed", 1337)
        scene.cycles.use_denoising = render.get("denoise", False)
    
    # Output format
    scene.render.image_settings.file_format = render.get("output_format", "PNG")
    scene.render.image_settings.color_depth = str(render.get("color_depth", 16))
    scene.render.image_settings.color_mode = "RGBA"
    
    # Film
    scene.render.film_transparent = False


def import_asset(asset_path: str) -> list:
    """Import GLB/GLTF asset and return imported objects."""
    # Clear existing mesh objects
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.select_set(True)
    bpy.ops.object.delete()
    
    # Import GLB
    bpy.ops.import_scene.gltf(filepath=asset_path)
    
    # Get imported objects
    imported = [obj for obj in bpy.context.selected_objects]
    
    return imported


def normalize_asset(objects: list):
    """Normalize asset origin and position."""
    if not objects:
        return
    
    # Join objects to compute bounds
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        if obj.type == "MESH":
            obj.select_set(True)
    
    if not bpy.context.selected_objects:
        return
    
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    
    # Compute bounding box
    min_z = float("inf")
    for obj in objects:
        if obj.type == "MESH":
            for v in obj.data.vertices:
                world_co = obj.matrix_world @ v.co
                min_z = min(min_z, world_co.z)
    
    # Move to ground
    if min_z != float("inf"):
        for obj in objects:
            obj.location.z -= min_z


def setup_camera(index: int, total: int, distance: float = 5.0):
    """Setup camera for turntable rendering."""
    angle = (index / total) * 2 * math.pi
    
    cam = bpy.data.objects.get("Camera")
    if not cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
    
    cam.location.x = math.sin(angle) * distance
    cam.location.y = -math.cos(angle) * distance
    cam.location.z = distance * 0.4
    
    # Point at origin
    direction = -cam.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()
    
    bpy.context.scene.camera = cam


def setup_lighting():
    """Setup basic three-point lighting."""
    # Clear existing lights
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj)
    
    # Key light
    bpy.ops.object.light_add(type="AREA", location=(3, -3, 5))
    key = bpy.context.object
    key.data.energy = 500
    key.data.size = 2
    
    # Fill light
    bpy.ops.object.light_add(type="AREA", location=(-3, -2, 3))
    fill = bpy.context.object
    fill.data.energy = 200
    fill.data.size = 3
    
    # Rim light
    bpy.ops.object.light_add(type="AREA", location=(0, 4, 4))
    rim = bpy.context.object
    rim.data.energy = 300
    rim.data.size = 2


def setup_ground():
    """Setup ground plane with shadow catcher."""
    # Add ground plane
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    
    # Create material
    mat = bpy.data.materials.new(name="Ground_Material")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    if mat.node_tree:
        nodes = mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
            principled.inputs["Roughness"].default_value = 0.8
    
    ground.data.materials.append(mat)
    
    # Shadow catcher (Cycles) - compatible with Blender 4.x and 5.x
    if bpy.context.scene.render.engine == "CYCLES":
        if hasattr(ground, "is_shadow_catcher"):
            ground.is_shadow_catcher = True


def create_clay_material():
    """Create neutral clay material for geometry evaluation."""
    mat = bpy.data.materials.new(name="Clay_Material")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    
    if mat.node_tree:
        nodes = mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        if principled:
            # Neutral gray
            principled.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1)
            principled.inputs["Roughness"].default_value = 0.7
            principled.inputs["Metallic"].default_value = 0.0
    
    return mat


def apply_clay_material(objects: list, clay_mat):
    """Apply clay material to all mesh objects."""
    for obj in objects:
        if obj.type == "MESH":
            obj.data.materials.clear()
            obj.data.materials.append(clay_mat)


def render_views(output_dir: str, mode: str, num_views: int = 6):
    """Render multiple views."""
    output_path = Path(output_dir) / mode
    output_path.mkdir(exist_ok=True)
    
    # Fixed camera positions (azimuth, elevation in degrees)
    fixed_views = [
        ("front_3q", 45, 15),
        ("rear_3q", 225, 15),
        ("side_left", 90, 5),
        ("front", 0, 10),
        ("top", 0, 75),
    ]
    
    for name, azimuth, elevation in fixed_views:
        angle_rad = math.radians(azimuth)
        elev_rad = math.radians(elevation)
        distance = 5.0
        
        cam = bpy.data.objects.get("Camera") or bpy.context.scene.camera
        if cam:
            cam.location.x = math.sin(angle_rad) * math.cos(elev_rad) * distance
            cam.location.y = -math.cos(angle_rad) * math.cos(elev_rad) * distance
            cam.location.z = math.sin(elev_rad) * distance
            
            # Point at origin
            from mathutils import Vector
            direction = Vector((0, 0, 0.5)) - cam.location
            rot_quat = direction.to_track_quat("-Z", "Y")
            cam.rotation_euler = rot_quat.to_euler()
        
        # Render
        filepath = str(output_path / f"{mode}_{name}.png")
        bpy.context.scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {filepath}")
    
    # Turntable frames
    for i in range(12):
        setup_camera(i, 12, distance=5.0)
        filepath = str(output_path / f"{mode}_turntable_f{i:02d}.png")
        bpy.context.scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)
        print(f"Rendered: {filepath}")


def main():
    # Parse arguments after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to render config JSON")
    args = parser.parse_args(argv)
    
    # Load config
    with open(args.config, "r") as f:
        config = json.load(f)
    
    asset_path = config["asset_path"]
    output_dir = config["output_dir"]
    
    print(f"Fab Render Harness")
    print(f"Asset: {asset_path}")
    print(f"Output: {output_dir}")
    
    # Setup scene
    setup_render_settings(config)
    setup_lighting()
    setup_ground()
    
    # Import and normalize asset
    objects = import_asset(asset_path)
    normalize_asset(objects)
    
    # Store original materials
    original_materials = {}
    for obj in objects:
        if obj.type == "MESH":
            original_materials[obj.name] = list(obj.data.materials)
    
    # Render beauty views
    print("\\nRendering beauty views...")
    render_views(output_dir, "beauty")
    
    # Apply clay material and render
    print("\\nRendering clay views...")
    clay_mat = create_clay_material()
    apply_clay_material(objects, clay_mat)
    render_views(output_dir, "clay")
    
    print("\\nRender complete!")


if __name__ == "__main__":
    main()
'''


def run_render_harness(
    asset_path: Path,
    config: GateConfig,
    output_dir: Path,
    lookdev_scene: Optional[Path] = None,
    camera_rig: Optional[Path] = None,
    blender_path: Optional[Path] = None,
) -> RenderResult:
    """
    Run the full render harness pipeline.

    Args:
        asset_path: Path to asset file (.glb)
        config: Gate configuration
        output_dir: Output directory for renders
        lookdev_scene: Optional lookdev scene file
        camera_rig: Optional camera rig JSON
        blender_path: Optional Blender executable path

    Returns:
        RenderResult with render outputs
    """
    # Find Blender
    if blender_path is None:
        blender_path = find_blender()

    if blender_path is None:
        logger.error(
            "Blender not found. Please install Blender or specify --blender path"
        )
        return RenderResult(
            success=False,
            output_dir=output_dir,
            errors=["BLENDER_NOT_FOUND"],
        )

    logger.info(f"Using Blender: {blender_path}")

    # Validate asset
    if not asset_path.exists():
        logger.error(f"Asset not found: {asset_path}")
        return RenderResult(
            success=False,
            output_dir=output_dir,
            errors=["IMPORT_FILE_NOT_FOUND"],
        )

    # Prepare config
    render_config = prepare_render_config(
        config, asset_path, output_dir, lookdev_scene, camera_rig
    )

    # Run Blender
    return run_blender_render(
        blender_path=blender_path,
        asset_path=asset_path,
        output_dir=output_dir,
        render_config=render_config,
    )


def main(args: List[str] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fab-render",
        description="Fab Render Harness - Headless Blender rendering for asset evaluation",
    )

    parser.add_argument(
        "--asset",
        type=Path,
        required=True,
        help="Path to asset file (.glb)",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="car_realism_v001",
        help="Gate config ID or path to YAML file",
    )

    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for renders",
    )

    parser.add_argument(
        "--lookdev",
        type=Path,
        help="Path to lookdev scene (.blend)",
    )

    parser.add_argument(
        "--camera-rig",
        type=Path,
        help="Path to camera rig JSON",
    )

    parser.add_argument(
        "--blender",
        type=Path,
        help="Path to Blender executable",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    parsed = parser.parse_args(args)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if parsed.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load gate config
    try:
        config_path = Path(parsed.config)
        if config_path.exists() and config_path.suffix in (".yaml", ".yml"):
            gate_config = load_gate_config(config_path)
        else:
            config_path = find_gate_config(parsed.config)
            gate_config = load_gate_config(config_path)
    except FileNotFoundError as e:
        logger.error(f"Config not found: {e}")
        return 1

    # Run render harness
    result = run_render_harness(
        asset_path=parsed.asset,
        config=gate_config,
        output_dir=parsed.out,
        lookdev_scene=parsed.lookdev,
        camera_rig=parsed.camera_rig,
        blender_path=parsed.blender,
    )

    # Output result
    if parsed.json:
        output = {
            "success": result.success,
            "output_dir": str(result.output_dir),
            "beauty_renders": result.beauty_renders,
            "clay_renders": result.clay_renders,
            "errors": result.errors,
            "blender_version": result.blender_version,
            "duration_ms": result.duration_ms,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Fab Render Harness Result")
        print(f"{'='*60}")
        print(f"Success:    {result.success}")
        print(f"Output:     {result.output_dir}")
        print(f"Blender:    {result.blender_version or 'unknown'}")
        print(f"Duration:   {result.duration_ms}ms")
        print(f"\nBeauty renders: {len(result.beauty_renders)}")
        for r in result.beauty_renders[:5]:
            print(f"  - {Path(r).name}")
        if len(result.beauty_renders) > 5:
            print(f"  ... and {len(result.beauty_renders) - 5} more")
        print(f"\nClay renders: {len(result.clay_renders)}")
        for r in result.clay_renders[:5]:
            print(f"  - {Path(r).name}")
        if result.errors:
            print(f"\nErrors:")
            for e in result.errors:
                print(f"  - {e}")
        print(f"{'='*60}\n")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
