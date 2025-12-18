import json
import struct
from pathlib import Path

import pytest


def _write_minimal_glb(path: Path, gltf: dict) -> None:
    json_bytes = json.dumps(gltf).encode("utf-8")
    # GLB JSON chunk must be 4-byte aligned (pad with spaces).
    json_bytes += b" " * ((4 - (len(json_bytes) % 4)) % 4)

    total_length = 12 + 8 + len(json_bytes)
    header = b"glTF" + struct.pack("<II", 2, total_length)
    chunk_header = struct.pack("<I4s", len(json_bytes), b"JSON")
    path.write_bytes(header + chunk_header + json_bytes)


def test_read_glb_json_and_stats(tmp_path: Path) -> None:
    from dev_kernel.fab.godot import compute_gltf_stats, read_glb_json

    glb_path = tmp_path / "level.glb"
    _write_minimal_glb(
        glb_path,
        {
            "asset": {"version": "2.0"},
            "nodes": [
                {"name": "SPAWN_PLAYER"},
                {"name": "COLLIDER_GROUND", "mesh": 0},
                {"name": "MeshThing", "mesh": 0},
            ],
            "meshes": [{"primitives": [{}, {}]}],
            "materials": [{}, {}, {}],
        },
    )

    gltf = read_glb_json(glb_path)
    stats = compute_gltf_stats(gltf)

    assert stats.node_count == 3
    assert stats.mesh_count == 1
    assert stats.material_count == 3
    assert stats.primitive_count == 2
    # mesh referenced by 2 nodes, 2 primitives -> 4 draw calls estimate
    assert stats.draw_calls_estimate == 4


def test_gate_contract_failures_without_markers(tmp_path: Path) -> None:
    from dev_kernel.fab.godot import GodotGateConfig, run_godot_harness

    glb_path = tmp_path / "level.glb"
    _write_minimal_glb(
        glb_path,
        {
            "asset": {"version": "2.0"},
            "nodes": [{"name": "JustAThing", "mesh": 0}],
            "meshes": [{"primitives": [{}]}],
            "materials": [{}],
        },
    )

    out_dir = tmp_path / "out"
    result = run_godot_harness(
        asset_path=glb_path,
        config=GodotGateConfig(gate_config_id="godot_integration_v001"),
        template_dir=tmp_path / "template",
        output_dir=out_dir,
        skip_godot=True,
    )

    assert result.verdict == "fail"
    details = result.failures.get("details", {})
    assert "CONTRACT_NO_SPAWN" in details
    assert "CONTRACT_NO_COLLIDERS" in details
    assert result.next_actions, "Expected repair actions for contract failures"


def test_gate_budget_failures(tmp_path: Path) -> None:
    from dev_kernel.fab.godot import GodotBudgets, GodotGateConfig, run_godot_harness

    glb_path = tmp_path / "level.glb"
    _write_minimal_glb(
        glb_path,
        {
            "asset": {"version": "2.0"},
            "nodes": [{"name": "SPAWN_PLAYER"}, {"name": "COLLIDER_GROUND", "mesh": 0}],
            "meshes": [{"primitives": [{} for _ in range(10)]}],
            "materials": [{} for _ in range(50)],
        },
    )

    out_dir = tmp_path / "out"
    result = run_godot_harness(
        asset_path=glb_path,
        config=GodotGateConfig(
            gate_config_id="godot_integration_v001",
            budgets=GodotBudgets(max_materials=10, max_draw_calls_est=5, max_nodes=10),
        ),
        template_dir=tmp_path / "template",
        output_dir=out_dir,
        skip_godot=True,
    )

    assert result.verdict == "fail"
    details = result.failures.get("details", {})
    assert "BUDGET_TOO_MANY_MATERIALS" in details
    assert "BUDGET_TOO_MANY_DRAW_CALLS" in details
