"""
Fab Godot Harness - Build a minimal playable Web export from a Blender-authored GLB.

This is an *engine integration* gate (separate from realism). It validates:
- Minimal gameplay metadata via naming conventions (spawn + colliders)
- Complexity budgets (materials / draw-call estimate)
- (When Godot is available) imports and exports a deterministic Web build

Usage:
  python -m dev_kernel.fab.godot --help
  python -m dev_kernel.fab.godot --asset scene.glb --config godot_integration_v001 --out /tmp/game
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import find_gate_config

logger = logging.getLogger(__name__)

DEFAULT_REPAIR_PLAYBOOK: dict[str, dict[str, Any]] = {}


def find_godot() -> Path | None:
    """Find a Godot executable on the system."""
    candidates = [
        # macOS app bundle
        "/Applications/Godot.app/Contents/MacOS/Godot",
        "/Applications/Godot_4.app/Contents/MacOS/Godot",
        "/Applications/Godot4.app/Contents/MacOS/Godot",
        str(Path.home() / "Applications/Godot.app/Contents/MacOS/Godot"),
        # Linux
        "/usr/bin/godot",
        "/usr/local/bin/godot",
    ]

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path

    for name in ("godot", "godot4", "Godot"):
        which = shutil.which(name)
        if which:
            return Path(which).resolve()

    return None


def get_godot_version(godot_path: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(godot_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    # Godot 4 prints like: "4.3.stable.official [hash]"
    version = result.stdout.strip().splitlines()[0].strip()
    return version or None


def read_glb_json(glb_path: Path) -> dict[str, Any]:
    """Read the JSON chunk from a .glb file (glTF 2.0 binary)."""
    data = glb_path.read_bytes()
    if len(data) < 12:
        raise ValueError("Invalid GLB: file too small")

    magic = data[0:4]
    if magic != b"glTF":
        raise ValueError("Invalid GLB: bad magic header")

    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"Unsupported GLB version: {version}")
    if length != len(data):
        raise ValueError("Invalid GLB: length header mismatch")

    offset = 12
    json_chunk: bytes | None = None
    while offset + 8 <= len(data):
        chunk_length = struct.unpack_from("<I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        if chunk_end > len(data):
            raise ValueError("Invalid GLB: chunk overruns file")

        if chunk_type == b"JSON":
            json_chunk = data[chunk_start:chunk_end]
            break

        offset = chunk_end

    if json_chunk is None:
        raise ValueError("Invalid GLB: missing JSON chunk")

    # JSON chunk is padded with spaces to 4-byte alignment
    return json.loads(json_chunk.decode("utf-8").rstrip(" \t\r\n\0"))


def _name_is_spawn(name: str, spawn_names: list[str]) -> bool:
    upper = name.strip().upper()
    for token in spawn_names:
        t = token.strip().upper()
        if upper == t or upper.startswith(t + "_"):
            return True
    return False


def _name_has_prefix(name: str, prefixes: list[str]) -> bool:
    upper = name.strip().upper()
    for prefix in prefixes:
        p = prefix.strip().upper()
        if upper.startswith(p):
            return True
    return False


@dataclass
class GltfStats:
    node_count: int
    mesh_count: int
    material_count: int
    primitive_count: int
    draw_calls_estimate: int
    node_names: list[str]


def compute_gltf_stats(gltf: dict[str, Any]) -> GltfStats:
    nodes = gltf.get("nodes", []) if isinstance(gltf.get("nodes", []), list) else []
    meshes = gltf.get("meshes", []) if isinstance(gltf.get("meshes", []), list) else []
    materials = (
        gltf.get("materials", []) if isinstance(gltf.get("materials", []), list) else []
    )

    node_names: list[str] = []
    mesh_ref_counts: dict[int, int] = {}
    for node in nodes:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str):
                node_names.append(name)
            mesh_index = node.get("mesh")
            if isinstance(mesh_index, int):
                mesh_ref_counts[mesh_index] = mesh_ref_counts.get(mesh_index, 0) + 1

    primitive_counts: dict[int, int] = {}
    total_primitives = 0
    for i, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            continue
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list):
            continue
        primitive_count = sum(1 for p in primitives if isinstance(p, dict))
        primitive_counts[i] = primitive_count
        total_primitives += primitive_count

    draw_calls = 0
    for mesh_index, ref_count in mesh_ref_counts.items():
        draw_calls += primitive_counts.get(mesh_index, 0) * ref_count

    return GltfStats(
        node_count=len(nodes),
        mesh_count=len(meshes),
        material_count=len(materials),
        primitive_count=total_primitives,
        draw_calls_estimate=draw_calls,
        node_names=node_names,
    )


@dataclass
class GodotRequirements:
    require_spawn: bool = True
    spawn_names: list[str] = field(default_factory=lambda: ["SPAWN_PLAYER", "OL_SPAWN_PLAYER"])
    require_colliders: bool = True
    collider_prefixes: list[str] = field(default_factory=lambda: ["COLLIDER_", "OL_COLLIDER_"])
    trigger_prefixes: list[str] = field(default_factory=lambda: ["TRIGGER_", "OL_TRIGGER_"])
    interact_prefixes: list[str] = field(default_factory=lambda: ["INTERACT_", "OL_INTERACT_"])


@dataclass
class GodotBudgets:
    max_materials: int = 256
    max_draw_calls_est: int = 8000
    max_nodes: int = 100000


@dataclass
class GodotConfig:
    export_preset: str = "Web"
    level_asset_relpath: str = "assets/level.glb"


@dataclass
class GodotGateConfig:
    gate_config_id: str
    category: str = "engine_integration"
    schema_version: str = "1.0"
    requirements: GodotRequirements = field(default_factory=GodotRequirements)
    budgets: GodotBudgets = field(default_factory=GodotBudgets)
    godot: GodotConfig = field(default_factory=GodotConfig)
    hard_fail_codes: list[str] = field(default_factory=list)
    repair_playbook: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_godot_gate_config(config_path: Path) -> GodotGateConfig:
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid config format in {config_path}")

    requirements_raw = raw.get("requirements", {}) if isinstance(raw.get("requirements"), dict) else {}
    budgets_raw = raw.get("budgets", {}) if isinstance(raw.get("budgets"), dict) else {}
    godot_raw = raw.get("godot", {}) if isinstance(raw.get("godot"), dict) else {}

    requirements = GodotRequirements(
        require_spawn=bool(requirements_raw.get("require_spawn", True)),
        spawn_names=list(requirements_raw.get("spawn_names", GodotRequirements().spawn_names)),
        require_colliders=bool(requirements_raw.get("require_colliders", True)),
        collider_prefixes=list(
            requirements_raw.get("collider_prefixes", GodotRequirements().collider_prefixes)
        ),
        trigger_prefixes=list(
            requirements_raw.get("trigger_prefixes", GodotRequirements().trigger_prefixes)
        ),
        interact_prefixes=list(
            requirements_raw.get("interact_prefixes", GodotRequirements().interact_prefixes)
        ),
    )

    budgets = GodotBudgets(
        max_materials=int(budgets_raw.get("max_materials", 256)),
        max_draw_calls_est=int(budgets_raw.get("max_draw_calls_est", 8000)),
        max_nodes=int(budgets_raw.get("max_nodes", 100000)),
    )

    godot = GodotConfig(
        export_preset=str(godot_raw.get("export_preset", "Web")),
        level_asset_relpath=str(godot_raw.get("level_asset_relpath", "assets/level.glb")),
    )

    return GodotGateConfig(
        gate_config_id=str(raw.get("gate_config_id", config_path.stem)),
        category=str(raw.get("category", "engine_integration")),
        schema_version=str(raw.get("schema_version", "1.0")),
        requirements=requirements,
        budgets=budgets,
        godot=godot,
        hard_fail_codes=list(raw.get("hard_fail_codes", [])),
        repair_playbook=raw.get("repair_playbook", {}) or {},
    )


@dataclass
class GodotGateResult:
    gate_config_id: str
    asset_id: str
    verdict: str
    stats: dict[str, Any]
    failures: dict[str, Any]
    artifacts: dict[str, str]
    timing: dict[str, Any]
    tool_versions: dict[str, str | None] = field(default_factory=dict)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    scores: dict[str, Any] = field(default_factory=dict)


def generate_next_actions(
    verdict: str,
    hard_fails: list[str],
    soft_fails: list[str],
    repair_playbook: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if verdict == "pass":
        return []

    actions: list[dict[str, Any]] = []
    for code in hard_fails + soft_fails:
        entry = repair_playbook.get(code)
        if entry:
            actions.append(
                {
                    "action": "repair",
                    "priority": int(entry.get("priority", 3)),
                    "fail_code": code,
                    "instructions": str(entry.get("instructions", f"Fix {code}")).strip(),
                }
            )
        else:
            actions.append(
                {
                    "action": "repair",
                    "priority": 3,
                    "fail_code": code,
                    "instructions": f"Fix {code}",
                }
            )

    actions.sort(key=lambda x: x.get("priority", 3))
    return actions


def run_godot_harness(
    *,
    asset_path: Path,
    config: GodotGateConfig,
    template_dir: Path,
    output_dir: Path,
    godot_path: Path | None = None,
    skip_godot: bool = False,
) -> GodotGateResult:
    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_id = asset_path.stem
    failure_details: dict[str, Any] = {}
    artifacts: dict[str, str] = {}
    scores: dict[str, Any] = {}

    # Parse GLB and validate contract + budgets.
    try:
        gltf = read_glb_json(asset_path)
        stats = compute_gltf_stats(gltf)
    except Exception as e:
        failure_details["ASSET_PARSE_FAILED"] = {"error": str(e)}
        hard_fails = ["ASSET_PARSE_FAILED"]
        soft_fails: list[str] = []
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            "fail",
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict="fail",
            stats={},
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    spawn_nodes = [n for n in stats.node_names if _name_is_spawn(n, config.requirements.spawn_names)]
    collider_nodes = [
        n for n in stats.node_names if _name_has_prefix(n, config.requirements.collider_prefixes)
    ]
    trigger_nodes = [
        n for n in stats.node_names if _name_has_prefix(n, config.requirements.trigger_prefixes)
    ]
    interact_nodes = [
        n for n in stats.node_names if _name_has_prefix(n, config.requirements.interact_prefixes)
    ]

    if config.requirements.require_spawn:
        if len(spawn_nodes) == 0:
            failure_details["CONTRACT_NO_SPAWN"] = {"expected": config.requirements.spawn_names}
        elif len(spawn_nodes) > 1:
            failure_details["CONTRACT_TOO_MANY_SPAWNS"] = {"found": spawn_nodes}

    if config.requirements.require_colliders and len(collider_nodes) == 0:
        failure_details["CONTRACT_NO_COLLIDERS"] = {
            "expected_prefixes": config.requirements.collider_prefixes
        }

    if stats.material_count > config.budgets.max_materials:
        failure_details["BUDGET_TOO_MANY_MATERIALS"] = {
            "found": stats.material_count,
            "max": config.budgets.max_materials,
        }

    if stats.draw_calls_estimate > config.budgets.max_draw_calls_est:
        failure_details["BUDGET_TOO_MANY_DRAW_CALLS"] = {
            "found": stats.draw_calls_estimate,
            "max": config.budgets.max_draw_calls_est,
        }

    if stats.node_count > config.budgets.max_nodes:
        failure_details["BUDGET_TOO_MANY_NODES"] = {
            "found": stats.node_count,
            "max": config.budgets.max_nodes,
        }

    stats_dict = {
        "node_count": stats.node_count,
        "mesh_count": stats.mesh_count,
        "material_count": stats.material_count,
        "primitive_count": stats.primitive_count,
        "draw_calls_estimate": stats.draw_calls_estimate,
        "contract": {
            "spawns": spawn_nodes,
            "colliders": collider_nodes,
            "triggers": trigger_nodes,
            "interactables": interact_nodes,
        },
    }

    failure_codes = sorted(failure_details.keys())
    hard_fails = [c for c in failure_codes if c in set(config.hard_fail_codes)]
    soft_fails = [c for c in failure_codes if c not in set(config.hard_fail_codes)]

    scores["budgets_ok"] = not any(k.startswith("BUDGET_") for k in failure_details)
    scores["contract_ok"] = not any(k.startswith("CONTRACT_") for k in failure_details)

    # If contract/budget already fails, skip Godot build.
    if failure_details and not skip_godot:
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            "fail",
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict="fail",
            stats=stats_dict,
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            scores=scores,
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    if skip_godot:
        verdict = "pass" if not failure_details else "fail"
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            verdict,
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict=verdict,
            stats=stats_dict,
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            scores=scores,
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    # Godot build.
    godot_bin = godot_path or find_godot()
    if godot_bin is None:
        failure_details["GODOT_MISSING"] = {
            "hint": "Install Godot 4 and ensure `godot` is on PATH."
        }
        hard_fails = sorted({*hard_fails, "GODOT_MISSING"})
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            "fail",
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict="fail",
            stats=stats_dict,
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            tool_versions={"godot": None},
            scores=scores,
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    project_dir = output_dir / "project"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    shutil.copytree(template_dir, project_dir)

    level_dest = project_dir / config.godot.level_asset_relpath
    level_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset_path, level_dest)

    artifacts["project_dir"] = str(project_dir)

    import_log = output_dir / "godot_import.log"
    export_log = output_dir / "godot_export.log"

    try:
        _run_godot_import(godot_bin, project_dir, import_log)
    except Exception as e:
        failure_details["GODOT_IMPORT_FAILED"] = {"error": str(e), "log": str(import_log)}
        hard_fails = sorted({*hard_fails, "GODOT_IMPORT_FAILED"})
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            "fail",
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict="fail",
            stats=stats_dict,
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            tool_versions={"godot": get_godot_version(godot_bin)},
            scores=scores,
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    export_index = output_dir / "index.html"
    try:
        _run_godot_export(godot_bin, project_dir, config.godot.export_preset, export_index, export_log)
    except Exception as e:
        failure_details["GODOT_EXPORT_FAILED"] = {"error": str(e), "log": str(export_log)}
        hard_fails = sorted({*hard_fails, "GODOT_EXPORT_FAILED"})
        duration_ms = int((time.time() - start_time) * 1000)
        next_actions = generate_next_actions(
            "fail",
            hard_fails=hard_fails,
            soft_fails=soft_fails,
            repair_playbook=config.repair_playbook,
        )
        report = GodotGateResult(
            gate_config_id=config.gate_config_id,
            asset_id=asset_id,
            verdict="fail",
            stats=stats_dict,
            failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
            artifacts=artifacts,
            timing={"duration_ms": duration_ms},
            tool_versions={"godot": get_godot_version(godot_bin)},
            scores=scores,
            next_actions=next_actions,
        )
        _write_report(output_dir, report)
        return report

    artifacts["web_index"] = str(export_index)
    artifacts["import_log"] = str(import_log)
    artifacts["export_log"] = str(export_log)

    duration_ms = int((time.time() - start_time) * 1000)
    report = GodotGateResult(
        gate_config_id=config.gate_config_id,
        asset_id=asset_id,
        verdict="pass",
        stats=stats_dict,
        failures={"hard": hard_fails, "soft": soft_fails, "details": failure_details},
        artifacts=artifacts,
        timing={"duration_ms": duration_ms},
        tool_versions={"godot": get_godot_version(godot_bin)},
        scores=scores,
        next_actions=[],
    )
    _write_report(output_dir, report)
    return report


def _run_godot_import(godot_bin: Path, project_dir: Path, log_path: Path) -> None:
    cmd = [
        str(godot_bin),
        "--headless",
        "--path",
        str(project_dir),
        "--import",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0:
        raise RuntimeError(f"Godot import failed (exit {result.returncode})")


def _run_godot_export(
    godot_bin: Path,
    project_dir: Path,
    export_preset: str,
    export_index: Path,
    log_path: Path,
) -> None:
    cmd = [
        str(godot_bin),
        "--headless",
        "--path",
        str(project_dir),
        "--export-release",
        export_preset,
        str(export_index),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0:
        raise RuntimeError(f"Godot export failed (exit {result.returncode})")
    if not export_index.exists():
        raise RuntimeError("Godot export did not produce index.html")


def _write_report(output_dir: Path, report: GodotGateResult) -> None:
    report_path = output_dir / "godot_report.json"
    report_path.write_text(json.dumps(asdict(report), indent=2, default=str) + "\n")


def _parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fab Godot integration gate")
    parser.add_argument("--asset", type=Path, required=True, help="Path to exported .glb asset")
    parser.add_argument(
        "--config",
        type=str,
        default="godot_integration_v001",
        help="Gate config ID (in fab/gates/) or path to YAML",
    )
    parser.add_argument("--template-dir", type=Path, default=Path("fab/godot/template"))
    parser.add_argument("--out", type=Path, required=True, help="Output directory for build + report")
    parser.add_argument("--godot", type=Path, default=None, help="Optional path to Godot binary")
    parser.add_argument(
        "--skip-godot",
        action="store_true",
        help="Only validate GLB + budgets; do not run Godot import/export",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    parsed = _parse_args(args or sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if parsed.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config_path = Path(parsed.config)
    if not (config_path.exists() and config_path.suffix in (".yaml", ".yml")):
        config_path = find_gate_config(parsed.config)
    gate_config = load_godot_gate_config(config_path)

    result = run_godot_harness(
        asset_path=parsed.asset,
        config=gate_config,
        template_dir=parsed.template_dir,
        output_dir=parsed.out,
        godot_path=parsed.godot,
        skip_godot=parsed.skip_godot,
    )

    if parsed.json:
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        print("\n" + "=" * 60)
        print("Fab Godot Gate Result")
        print("=" * 60)
        print(f"Asset:   {result.asset_id}")
        print(f"Config:  {result.gate_config_id}")
        print(f"Verdict: {result.verdict.upper()}")
        print(f"Output:  {parsed.out}")
        print("=" * 60 + "\n")

    if result.verdict == "pass":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
