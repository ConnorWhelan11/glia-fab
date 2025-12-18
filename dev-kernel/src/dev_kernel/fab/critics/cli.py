"""
Fab Critics CLI - Command-line interface for running critics.

Usage:
    python -m dev_kernel.fab.critics.cli category --beauty-dir /path/to/beauty --clay-dir /path/to/clay
    python -m dev_kernel.fab.critics.cli geometry --mesh /path/to/asset.glb
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_category(args: argparse.Namespace) -> int:
    """Run category critic."""
    from .category import CategoryCritic

    # Load config if provided
    config: Dict[str, Any] = {}
    if args.config:
        import yaml

        with open(args.config) as f:
            full_config = yaml.safe_load(f)
            config = full_config.get("critics", {}).get("category", {})

    # Create critic
    critic = CategoryCritic(
        category=args.category,
        clip_model=config.get("clip_model", "ViT-L/14"),
        min_views_passing=config.get("min_views_passing", 10),
        per_view_conf_min=config.get("per_view_car_conf_min", 0.60),
        margin_min=config.get("clip_margin_min", 0.08),
        require_clay_agreement=config.get("require_clay_agreement", True),
    )

    # Get renders
    beauty_dir = Path(args.beauty_dir)
    clay_dir = Path(args.clay_dir) if args.clay_dir else beauty_dir.parent / "clay"

    beauty_renders = sorted(beauty_dir.glob("*.png"))
    clay_renders = sorted(clay_dir.glob("*.png")) if clay_dir.exists() else []

    logger.info(f"Evaluating {len(beauty_renders)} beauty + {len(clay_renders)} clay renders")

    # Run evaluation
    result = critic.evaluate(beauty_renders, clay_renders)

    # Output
    output = result.to_dict()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Wrote result to {out_path}")

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print("Category Critic Result")
        print(f"{'='*60}")
        print(f"Score:           {result.score:.3f}")
        print(f"Passed:          {result.passed}")
        print(f"Views evaluated: {result.views_evaluated}")
        print(f"Views passing:   {result.views_passing}")
        if result.fail_codes:
            print(f"Fail codes:      {', '.join(result.fail_codes)}")
        print(f"{'='*60}\n")

    return 0 if result.passed else 1


def run_geometry(args: argparse.Namespace) -> int:
    """Run geometry critic."""
    from .geometry import GeometryCritic

    # Load config if provided
    config: Dict[str, Any] = {}
    if args.config:
        import yaml

        with open(args.config) as f:
            full_config = yaml.safe_load(f)
            config = full_config.get("critics", {}).get("geometry", {})

    bounds_m = config.get("bounds_m", {})
    triangle_count = config.get("triangle_count", [5000, 500000])

    # Create critic
    critic = GeometryCritic(
        category=args.category,
        bounds_length=tuple(bounds_m.get("length", [3.0, 6.0])),
        bounds_width=tuple(bounds_m.get("width", [1.4, 2.5])),
        bounds_height=tuple(bounds_m.get("height", [1.0, 2.5])),
        triangle_count_range=tuple(triangle_count),
        symmetry_min=config.get("symmetry_min", 0.70),
        wheel_clusters_min=config.get("wheel_clusters_min", 3),
        non_manifold_max_ratio=config.get("non_manifold_max_ratio", 0.05),
        normals_consistency_min=config.get("normals_consistency_min", 0.95),
    )

    mesh_path = Path(args.mesh)
    logger.info(f"Evaluating mesh: {mesh_path}")

    # Run evaluation
    result = critic.evaluate(mesh_path)

    # Output
    output = result.to_dict()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Wrote result to {out_path}")

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print("Geometry Critic Result")
        print(f"{'='*60}")
        print(f"Score:           {result.score:.3f}")
        print(f"Passed:          {result.passed}")
        if result.bounds:
            print(f"Bounds:          {result.bounds.length:.2f}L x {result.bounds.width:.2f}W x {result.bounds.height:.2f}H m")
        if result.mesh_metrics:
            print(f"Triangles:       {result.mesh_metrics.triangle_count}")
            print(f"Components:      {result.mesh_metrics.component_count}")
        print(f"Symmetry:        {result.symmetry_score:.3f}")
        print(f"Wheels found:    {len([w for w in result.wheel_candidates if w.is_valid])}")
        if result.fail_codes:
            print(f"Fail codes:      {', '.join(result.fail_codes)}")
        print(f"{'='*60}\n")

    return 0 if result.passed else 1


def main(args: list = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fab-critics",
        description="Fab Critics - Multi-signal asset evaluation",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Category critic
    cat_parser = subparsers.add_parser("category", help="Run category critic on renders")
    cat_parser.add_argument("--beauty-dir", type=str, required=True, help="Directory with beauty renders")
    cat_parser.add_argument("--clay-dir", type=str, help="Directory with clay renders")
    cat_parser.add_argument("--category", type=str, default="car", help="Expected category")
    cat_parser.add_argument("--config", type=str, help="Path to gate config YAML")
    cat_parser.add_argument("--out", type=str, help="Output JSON path")
    cat_parser.add_argument("--json", action="store_true", help="Output as JSON to stdout")

    # Geometry critic
    geo_parser = subparsers.add_parser("geometry", help="Run geometry critic on mesh")
    geo_parser.add_argument("--mesh", type=str, required=True, help="Path to mesh file (.glb)")
    geo_parser.add_argument("--category", type=str, default="car", help="Asset category")
    geo_parser.add_argument("--config", type=str, help="Path to gate config YAML")
    geo_parser.add_argument("--out", type=str, help="Output JSON path")
    geo_parser.add_argument("--json", action="store_true", help="Output as JSON to stdout")

    parsed = parser.parse_args(args)

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if parsed.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if parsed.command == "category":
        return run_category(parsed)
    elif parsed.command == "geometry":
        return run_geometry(parsed)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

