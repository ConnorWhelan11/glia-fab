#!/usr/bin/env python3
"""
Export a Blender scene/collection as a Godot-ready GLB using the Fab game contract.

Usage (headless):
  macOS:
    /Applications/Blender.app/Contents/MacOS/Blender path/to/file.blend --background \
      --python export_fab_game_glb.py -- \
      --output /tmp/level.glb --collection Export_Game

  Other:
    blender path/to/file.blend --background --python export_fab_game_glb.py -- \
      --output /tmp/level.glb --collection Export_Game

Markers (required):
  - SPAWN_PLAYER (or ol_spawn_player)
  - COLLIDER_* meshes (or ol_collider_*)

See also:
  - fab/godot/CONTRACT.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def _ensure_outora_library_on_path() -> None:
    repo_outora_root = Path(__file__).resolve().parents[1]
    src_dir = repo_outora_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_ensure_outora_library_on_path()

from outora_library.game_contract import validate_fab_game_contract  # noqa: E402


def _script_args(argv: list[str]) -> list[str]:
    if "--" not in argv:
        return []
    return argv[argv.index("--") + 1 :]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/fab_level.glb"),
        help="Output GLB path.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Optional collection name to export (recursive).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate markers and exit without exporting.",
    )
    parser.add_argument(
        "--no-require-colliders",
        action="store_true",
        help="Allow export without any COLLIDER_* meshes.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path to write a JSON validation report.",
    )
    return parser.parse_args(argv)


def _select_collection_objects(collection_name: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")

    col = bpy.data.collections.get(collection_name)
    if not col:
        raise ValueError(f"Collection not found: {collection_name!r}")

    def select_recursive(c: bpy.types.Collection) -> None:
        for obj in c.objects:
            if obj.type in {"MESH", "EMPTY"}:
                obj.select_set(True)
        for child in c.children:
            select_recursive(child)

    select_recursive(col)


def _select_scene_objects() -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "EMPTY"}:
            obj.select_set(True)


def _export_glb(filepath: Path) -> None:
    export_args: dict[str, object] = {
        "filepath": str(filepath),
        "use_selection": True,
        "export_format": "GLB",
        "export_texcoords": True,
        "export_normals": True,
        "export_materials": "EXPORT",
        "export_cameras": False,
        "export_lights": False,
        "export_apply": True,
    }

    # Keep compatibility across Blender versions by gracefully dropping optional args.
    try:
        bpy.ops.export_scene.gltf(**export_args, export_extras=True, export_colors=True)
        return
    except TypeError:
        pass

    try:
        bpy.ops.export_scene.gltf(**export_args, export_extras=True)
        return
    except TypeError:
        pass

    try:
        bpy.ops.export_scene.gltf(**export_args, export_colors=True)
        return
    except TypeError:
        pass

    bpy.ops.export_scene.gltf(**export_args)


def main() -> None:
    args = _parse_args(_script_args(sys.argv))
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.collection:
        _select_collection_objects(args.collection)
    else:
        _select_scene_objects()

    exported_objects = list(bpy.context.selected_objects)
    exported_names = [obj.name for obj in exported_objects]

    report = validate_fab_game_contract(
        exported_names,
        require_colliders=not args.no_require_colliders,
    )

    print("\n" + "=" * 70)
    print("FAB GAME EXPORT - VALIDATION")
    print("=" * 70)
    print(f"Selected objects: {len(exported_objects)}")
    print(f"Spawns: {len(report.spawns)}  Colliders: {len(report.colliders)}")
    print(f"Triggers: {len(report.triggers)}")
    print(f"Interactables: {len(report.interactables)}")

    if report.warnings:
        print("\nWarnings:")
        for w in report.warnings:
            print(f"  - {w}")

    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e}")

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
        print(f"\nWrote report: {args.report_json}")

    if report.errors:
        raise SystemExit(2)

    if args.validate_only:
        print("\nValidation passed (validate-only).")
        return

    print("\n" + "=" * 70)
    print("EXPORTING GLB")
    print("=" * 70)
    print(f"Output: {output_path}")
    _export_glb(output_path)
    print("Done.")


if __name__ == "__main__":
    main()
