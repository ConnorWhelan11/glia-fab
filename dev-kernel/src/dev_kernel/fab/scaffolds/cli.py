"""
Scaffold CLI - Command-line interface for procedural scaffold generation.

Usage:
    fab-scaffold list                           # List available scaffolds
    fab-scaffold info <scaffold_id>             # Show scaffold parameters
    fab-scaffold generate <scaffold_id> --out . # Generate scaffold script
    fab-scaffold check-sverchok                 # Check Sverchok installation
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .registry import get_registry, list_scaffolds
from .sverchok import (
    generate_sverchok_check_script,
    SverchokConfig,
    CarSverchokScaffold,
)

logger = logging.getLogger(__name__)


def cmd_list(args: argparse.Namespace) -> int:
    """List available scaffolds."""
    scaffolds = list_scaffolds(args.category)

    if args.json:
        print(json.dumps(scaffolds, indent=2))
    else:
        print("\nAvailable Scaffolds:")
        print("=" * 60)

        if not scaffolds:
            print("  (none)")
        else:
            for s in scaffolds:
                print(f"  [{s['category']}] {s['scaffold_id']} v{s['version']}")

        print()

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show scaffold details and parameters."""
    registry = get_registry()

    # Find scaffold
    scaffold = None
    for cat in registry._scaffolds.values():
        for key, scaffold_class in cat.items():
            if scaffold_class.SCAFFOLD_ID == args.scaffold_id:
                scaffold = scaffold_class()
                break
        if scaffold:
            break

    if not scaffold:
        print(f"Error: Scaffold '{args.scaffold_id}' not found", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(scaffold.to_manifest(), indent=2))
    else:
        print(f"\nScaffold: {scaffold.SCAFFOLD_ID}")
        print(f"Version:  {scaffold.SCAFFOLD_VERSION}")
        print(f"Category: {scaffold.CATEGORY}")
        print()
        print("Parameters:")
        print("-" * 60)

        params = scaffold.get_parameters()
        for name, param in params.items():
            range_str = ""
            if param.min_value is not None or param.max_value is not None:
                range_str = f" [{param.min_value} - {param.max_value}]"

            unit_str = f" {param.unit}" if param.unit else ""
            print(f"  {name}: {param.param_type.value}{range_str}{unit_str}")
            print(f"    Default: {param.default}")
            if param.description:
                print(f"    {param.description}")
            print()

    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate scaffold script and files."""
    registry = get_registry()

    # Find scaffold
    scaffold = None
    for cat in registry._scaffolds.values():
        for key, scaffold_class in cat.items():
            if scaffold_class.SCAFFOLD_ID == args.scaffold_id:
                scaffold = scaffold_class()
                break
        if scaffold:
            break

    if not scaffold:
        print(f"Error: Scaffold '{args.scaffold_id}' not found", file=sys.stderr)
        return 1

    # Parse custom parameters
    params: Dict[str, Any] = {}
    if args.params:
        for param_str in args.params:
            if "=" in param_str:
                key, value = param_str.split("=", 1)
                # Try to parse as JSON, fall back to string
                try:
                    params[key] = json.loads(value)
                except json.JSONDecodeError:
                    params[key] = value

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate scaffold
    result = scaffold.instantiate(params=params, output_dir=output_dir)

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\nScaffold generated successfully!")
        print(f"  Script: {result.script_path}")
        print(f"  Output: {result.output_path}")
        print()
        print("To run in Blender:")
        print(f"  blender --background --python {result.script_path}")
        print()

    return 0


def cmd_check_sverchok(args: argparse.Namespace) -> int:
    """Check Sverchok installation status."""
    script = generate_sverchok_check_script()

    if args.json:
        print(json.dumps({"check_script": script}, indent=2))
    else:
        print("\nSverchok Check Script")
        print("=" * 60)
        print("Run this script in Blender to check Sverchok status:")
        print()
        print("  blender --background --python-expr '")
        print(script[:200] + "...'")
        print()
        print("Or save to file and run:")
        print("  blender --background --python check_sverchok.py")
        print()

        # Write check script to file if output specified
        if args.output:
            script_path = Path(args.output) / "check_sverchok.py"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script)
            print(f"Check script saved to: {script_path}")

    return 0


def cmd_demo_sverchok(args: argparse.Namespace) -> int:
    """Generate demo Sverchok car scaffold."""
    config = SverchokConfig(
        enabled=True,
        fallback_to_geometry_nodes=True,
    )

    scaffold = CarSverchokScaffold(config=config)

    # Use default params or custom
    params = scaffold.get_defaults()
    if args.params:
        for param_str in args.params:
            if "=" in param_str:
                key, value = param_str.split("=", 1)
                try:
                    params[key] = json.loads(value)
                except json.JSONDecodeError:
                    params[key] = value

    output_dir = Path(args.output)
    result = scaffold.instantiate(params=params, output_dir=output_dir)

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\nSverchok demo scaffold generated!")
        print(f"  Script: {result.script_path}")
        print()
        print("Parameters used:")
        for k, v in params.items():
            print(f"  {k}: {v}")
        print()

    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fab Scaffold CLI - Procedural asset generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    list_parser = subparsers.add_parser("list", help="List available scaffolds")
    list_parser.add_argument("--category", type=str, help="Filter by category")

    # info command
    info_parser = subparsers.add_parser("info", help="Show scaffold info")
    info_parser.add_argument("scaffold_id", help="Scaffold ID")

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate scaffold")
    gen_parser.add_argument("scaffold_id", help="Scaffold ID")
    gen_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=".",
        help="Output directory",
    )
    gen_parser.add_argument(
        "--params",
        "-p",
        nargs="*",
        help="Parameters as key=value pairs",
    )

    # check-sverchok command
    check_parser = subparsers.add_parser(
        "check-sverchok",
        help="Check Sverchok installation",
    )
    check_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Save check script to directory",
    )

    # demo-sverchok command
    demo_parser = subparsers.add_parser(
        "demo-sverchok",
        help="Generate demo Sverchok car scaffold",
    )
    demo_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=".",
        help="Output directory",
    )
    demo_parser.add_argument(
        "--params",
        "-p",
        nargs="*",
        help="Parameters as key=value pairs",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Route to command handler
    if args.command == "list":
        return cmd_list(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "check-sverchok":
        return cmd_check_sverchok(args)
    elif args.command == "demo-sverchok":
        return cmd_demo_sverchok(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
