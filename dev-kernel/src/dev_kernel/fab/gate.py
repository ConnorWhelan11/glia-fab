"""
Fab Realism Gate - Main Entry Point

This module provides the CLI and core logic for running the Fab Realism Gate,
which evaluates Blender assets through canonical renders and multi-signal critics.

Usage:
    python -m dev_kernel.fab.gate --help
    python -m dev_kernel.fab.gate --dry-run --out /tmp/fab-test
    python -m dev_kernel.fab.gate --asset asset.glb --config car_realism_v001

Gate Decision Logic:
    1. Run all enabled critics (category, alignment, realism, geometry)
    2. Aggregate scores using weighted sum: S = Σ(weight_i × score_i)
    3. Check subscore floors (each critic must meet minimum threshold)
    4. Check for hard fail codes (immediate rejection)
    5. Final verdict: pass if S >= threshold and no hard fails and floors met
"""

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import GateConfig, load_gate_config, find_gate_config

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result from gate evaluation."""

    run_id: str
    asset_id: str
    gate_config_id: str
    verdict: str  # "pass", "fail", "escalate"
    scores: Dict[str, float] = field(default_factory=dict)
    failures: Dict[str, List[str]] = field(
        default_factory=lambda: {"hard": [], "soft": []}
    )
    next_actions: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    timing: Dict[str, Any] = field(default_factory=dict)


def generate_run_id() -> str:
    """Generate a unique run identifier."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Short hash for uniqueness
    hash_input = f"{timestamp}-{id(object())}"
    short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
    return f"run_{timestamp}_{short_hash}"


def generate_asset_id(asset_path: Optional[Path]) -> str:
    """Generate asset identifier from path or random."""
    if asset_path and asset_path.exists():
        # Hash first 1KB of file for stability
        with open(asset_path, "rb") as f:
            content = f.read(1024)
        return hashlib.sha256(content).hexdigest()[:12]
    return hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:12]


def create_skeleton_verdict(
    run_id: str,
    asset_id: str,
    gate_config: GateConfig,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Create a skeleton gate verdict JSON.

    In dry-run mode, this produces a template structure without actual evaluation.
    """
    now = datetime.now(timezone.utc)

    verdict = {
        "schema_version": "1.0",
        "run_id": run_id,
        "asset_id": asset_id,
        "gate_config_id": gate_config.gate_config_id,
        "iteration_index": 0,
        "verdict": "pending" if dry_run else "fail",
        "verdict_reason": "Dry run - no evaluation performed" if dry_run else "",
        "scores": {
            "overall": 0.0,
            "by_critic": {
                "category": 0.0,
                "alignment": 0.0,
                "realism": 0.0,
                "geometry": 0.0,
            },
            "threshold": gate_config.decision.overall_pass_min,
            "margin": -gate_config.decision.overall_pass_min,
        },
        "failures": {"hard": [], "soft": []},
        "floor_violations": [],
        "next_actions": [],
        "artifacts": {
            "critic_report_path": "",
            "render_dir": "",
            "asset_proof_path": "",
            "manifest_path": "",
        },
        "timing": {
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "duration_ms": 0,
        },
    }

    if dry_run:
        verdict["_dry_run"] = True
        verdict["_config_loaded"] = gate_config.gate_config_id
        verdict["_critics_configured"] = list(gate_config.critics.keys())

    return verdict


def create_skeleton_critic_report(
    run_id: str,
    asset_id: str,
    gate_config: GateConfig,
) -> Dict[str, Any]:
    """Create a skeleton critic report JSON."""
    now = datetime.now(timezone.utc)

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "asset_id": asset_id,
        "gate_config_id": gate_config.gate_config_id,
        "determinism": {
            "cpu_only": gate_config.render.device == "CPU",
            "seeds": {"global_seed": gate_config.render.seed},
            "framework_versions": {"dev_kernel": "0.1.0"},
        },
        "models": [],
        "views": [],
        "geometry_analysis": {},
        "scores": {
            "category": 0.0,
            "alignment": 0.0,
            "realism": 0.0,
            "geometry": 0.0,
            "overall": 0.0,
        },
        "failures": {"hard": [], "soft": []},
        "timing": {
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "duration_ms": 0,
        },
    }


def create_skeleton_manifest(
    run_id: str,
    gate_config: GateConfig,
    output_dir: Path,
) -> Dict[str, Any]:
    """Create a skeleton run manifest JSON."""
    now = datetime.now(timezone.utc)

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at": now.isoformat(),
        "gate_config_id": gate_config.gate_config_id,
        "files": {},
        "tool_versions": {
            "blender": "4.1.0",  # Placeholder
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "dev_kernel": "0.1.0",
        },
        "iteration": {
            "parent_run_id": None,
            "iteration_index": 0,
            "max_iterations": gate_config.iteration.max_iterations,
        },
    }


@dataclass
class CriticResults:
    """Aggregated critic results."""

    category: Optional[Dict[str, Any]] = None
    alignment: Optional[Dict[str, Any]] = None
    realism: Optional[Dict[str, Any]] = None
    geometry: Optional[Dict[str, Any]] = None


def run_critics(
    asset_path: Path,
    render_dir: Path,
    config: GateConfig,
    prompt: str = "",
) -> Tuple[CriticResults, Dict[str, float], List[str], List[str]]:
    """
    Run all enabled critics on the asset.

    Returns:
        Tuple of (results, scores, hard_fails, soft_fails)
    """
    from .critics.category import CategoryCritic
    from .critics.alignment import AlignmentCritic
    from .critics.realism import RealismCritic
    from .critics.geometry import GeometryCritic

    results = CriticResults()
    scores: Dict[str, float] = {}
    hard_fails: List[str] = []
    soft_fails: List[str] = []

    beauty_dir = render_dir / "beauty"
    clay_dir = render_dir / "clay"

    # Category Critic
    if config.critics.get("category", None) and config.critics["category"].enabled:
        try:
            critic_params = config.critics["category"].params
            critic = CategoryCritic(
                category=config.category,
                clip_model=critic_params.get("clip_model", "ViT-L/14"),
                min_views_passing=critic_params.get("min_views_passing", 10),
                per_view_conf_min=critic_params.get(
                    "per_view_conf_min", critic_params.get("per_view_car_conf_min", 0.60)
                ),
                margin_min=critic_params.get(
                    "margin_min", critic_params.get("clip_margin_min", 0.08)
                ),
                require_clay_agreement=critic_params.get(
                    "require_clay_agreement", True
                ),
            )

            beauty_renders = (
                sorted(beauty_dir.glob("*.png")) if beauty_dir.exists() else []
            )
            clay_renders = sorted(clay_dir.glob("*.png")) if clay_dir.exists() else []

            cat_result = critic.evaluate(
                beauty_renders, clay_renders, seed=config.render.seed
            )
            results.category = cat_result.to_dict()
            scores["category"] = cat_result.score

            # Classify failures
            for code in cat_result.fail_codes:
                if code in config.hard_fail_codes:
                    hard_fails.append(code)
                else:
                    soft_fails.append(code)

            logger.info(
                f"Category critic: score={cat_result.score:.3f}, passed={cat_result.passed}"
            )
        except Exception as e:
            logger.error(f"Category critic failed: {e}")
            scores["category"] = 0.0
            soft_fails.append("CRITIC_CATEGORY_ERROR")

    # Alignment Critic
    if config.critics.get("alignment", None) and config.critics["alignment"].enabled:
        try:
            critic_params = config.critics["alignment"].params
            critic = AlignmentCritic(
                clip_model=critic_params.get("clip_model", "ViT-L/14"),
                similarity_min=critic_params.get("similarity_min", 0.25),
                margin_min=critic_params.get("margin_min", 0.08),
                min_views_passing=critic_params.get("min_views_passing", 4),
                use_attribute_probes=critic_params.get("use_attribute_probes", True),
            )

            beauty_renders = (
                sorted(beauty_dir.glob("*.png")) if beauty_dir.exists() else []
            )

            align_result = critic.evaluate(
                prompt=prompt or f"a {config.category.replace('_', ' ')}",
                render_paths=beauty_renders,
                seed=config.render.seed,
            )
            results.alignment = align_result.to_dict()
            scores["alignment"] = align_result.score

            for code in align_result.fail_codes:
                if code in config.hard_fail_codes:
                    hard_fails.append(code)
                else:
                    soft_fails.append(code)

            logger.info(
                f"Alignment critic: score={align_result.score:.3f}, passed={align_result.passed}"
            )
        except Exception as e:
            logger.error(f"Alignment critic failed: {e}")
            scores["alignment"] = 0.0
            soft_fails.append("CRITIC_ALIGNMENT_ERROR")

    # Realism Critic
    if config.critics.get("realism", None) and config.critics["realism"].enabled:
        try:
            critic_params = config.critics["realism"].params
            artifact_checks = critic_params.get("artifact_checks", {})
            if not isinstance(artifact_checks, dict):
                artifact_checks = {}

            critic = RealismCritic(
                aesthetic_min=critic_params.get("aesthetic_min", 0.55),
                quality_min=critic_params.get("quality_min", 0.40),
                niqe_max=critic_params.get("niqe_max", 6.0),
                min_views_passing=critic_params.get("min_views_passing", 8),
                noise_max=critic_params.get(
                    "noise_max",
                    critic_params.get(
                        "noise_threshold", artifact_checks.get("noise_threshold", 0.20)
                    ),
                ),
                missing_texture_max=critic_params.get(
                    "missing_texture_max",
                    critic_params.get(
                        "missing_texture_threshold",
                        critic_params.get(
                            "magenta_threshold",
                            artifact_checks.get("missing_texture_threshold", 0.05),
                        ),
                    ),
                ),
            )

            beauty_renders = (
                sorted(beauty_dir.glob("*.png")) if beauty_dir.exists() else []
            )

            real_result = critic.evaluate(beauty_renders, seed=config.render.seed)
            results.realism = real_result.to_dict()
            scores["realism"] = real_result.score

            for code in real_result.fail_codes:
                if code in config.hard_fail_codes:
                    hard_fails.append(code)
                else:
                    soft_fails.append(code)

            logger.info(
                f"Realism critic: score={real_result.score:.3f}, passed={real_result.passed}"
            )
        except Exception as e:
            logger.error(f"Realism critic failed: {e}")
            scores["realism"] = 0.0
            soft_fails.append("CRITIC_REALISM_ERROR")

    # Geometry Critic
    if config.critics.get("geometry", None) and config.critics["geometry"].enabled:
        try:
            critic_params = config.critics["geometry"].params
            bounds_m = critic_params.get("bounds_m", {})

            critic = GeometryCritic(
                category=config.category,
                bounds_length=tuple(bounds_m.get("length", [3.0, 6.0])),
                bounds_width=tuple(bounds_m.get("width", [1.4, 2.5])),
                bounds_height=tuple(bounds_m.get("height", [1.0, 2.5])),
                triangle_count_range=tuple(
                    critic_params.get("triangle_count", [5000, 500000])
                ),
                symmetry_min=critic_params.get("symmetry_min", 0.70),
                wheel_clusters_min=critic_params.get("wheel_clusters_min", 3),
                non_manifold_max_ratio=critic_params.get(
                    "non_manifold_max_ratio",
                    critic_params.get("manifold_tolerance", 0.05),
                ),
                normals_consistency_min=critic_params.get(
                    "normals_consistency_min", 0.95
                ),
            )

            geo_result = critic.evaluate(asset_path)
            results.geometry = geo_result.to_dict()
            scores["geometry"] = geo_result.score

            for code in geo_result.fail_codes:
                if code in config.hard_fail_codes:
                    hard_fails.append(code)
                else:
                    soft_fails.append(code)

            logger.info(
                f"Geometry critic: score={geo_result.score:.3f}, passed={geo_result.passed}"
            )
        except Exception as e:
            logger.error(f"Geometry critic failed: {e}")
            scores["geometry"] = 0.0
            soft_fails.append("CRITIC_GEOMETRY_ERROR")

    return results, scores, hard_fails, soft_fails


def compute_aggregate_score(
    scores: Dict[str, float],
    weights: Dict[str, float],
) -> float:
    """Compute weighted aggregate score."""
    total_weight = 0.0
    weighted_sum = 0.0

    for critic_name, weight in weights.items():
        if critic_name in scores:
            weighted_sum += weight * scores[critic_name]
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def check_subscore_floors(
    scores: Dict[str, float],
    floors: Dict[str, float],
) -> List[str]:
    """Check if all subscores meet their floors."""
    violations = []

    for critic_name, floor in floors.items():
        if critic_name in scores:
            if scores[critic_name] < floor:
                violations.append(f"FLOOR_{critic_name.upper()}_BELOW_MIN")

    return violations


def determine_verdict(
    overall_score: float,
    threshold: float,
    hard_fails: List[str],
    floor_violations: List[str],
    iteration_index: int = 0,
    max_iterations: int = 5,
) -> str:
    """
    Determine final gate verdict.

    Returns: "pass", "fail", or "escalate"
    """
    # Hard fail = immediate fail
    if hard_fails:
        return "fail"

    # Floor violations = fail
    if floor_violations:
        return "fail"

    # Score below threshold = fail
    if overall_score < threshold:
        return "fail"

    return "pass"


def generate_next_actions(
    verdict: str,
    hard_fails: List[str],
    soft_fails: List[str],
    floor_violations: List[str],
    repair_playbook: Dict[str, Dict[str, Any]],
    iteration_index: int = 0,
    max_iterations: int = 5,
) -> List[Dict[str, Any]]:
    """Generate recommended next actions based on failures."""
    actions = []

    if verdict == "pass":
        return actions

    # Collect all failure codes
    all_fails = hard_fails + soft_fails + floor_violations

    # Generate repair actions from playbook
    for code in all_fails:
        if code in repair_playbook:
            playbook_entry = repair_playbook[code]
            actions.append(
                {
                    "action": "repair",
                    "priority": playbook_entry.get("priority", 3),
                    "fail_code": code,
                    "instructions": playbook_entry.get("instructions", f"Fix {code}"),
                }
            )

    # Sort by priority
    actions.sort(key=lambda x: x["priority"])

    # Check for escalation conditions
    if iteration_index >= max_iterations - 1:
        actions.insert(
            0,
            {
                "action": "human_review",
                "priority": 0,
                "reason": f"Max iterations ({max_iterations}) reached",
            },
        )

    # Suggest template fallback after repeated failures
    if iteration_index >= 2 and hard_fails:
        actions.append(
            {
                "action": "fallback_to_template",
                "priority": 1,
                "reason": "Repeated hard failures suggest starting from template",
                "suggested_template_ref": "car_sedan_template_v001",
            }
        )

    return actions


def run_gate(
    asset_path: Optional[Path],
    config: GateConfig,
    output_dir: Path,
    dry_run: bool = False,
    prompt: str = "",
    render_dir: Optional[Path] = None,
    iteration_index: int = 0,
) -> GateResult:
    """
    Run the fab realism gate on an asset.

    Args:
        asset_path: Path to asset file (.glb)
        config: Gate configuration
        output_dir: Directory for output artifacts
        dry_run: If True, only produce skeleton outputs
        prompt: Asset prompt/description for alignment critic
        render_dir: Pre-existing render directory (skip rendering if provided)
        iteration_index: Current iteration number

    Returns:
        GateResult with verdict and artifacts
    """
    start_time = datetime.now(timezone.utc)
    run_id = generate_run_id()
    asset_id = generate_asset_id(asset_path)

    logger.info(f"Starting gate run: {run_id}")
    logger.info(f"Gate config: {config.gate_config_id}")
    logger.info(f"Asset: {asset_path or 'none (dry-run)'}")
    logger.info(f"Output: {output_dir}")

    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    verdict_dir = output_dir / "verdict"
    verdict_dir.mkdir(exist_ok=True)
    critics_dir = output_dir / "critics"
    critics_dir.mkdir(exist_ok=True)

    # In dry-run mode, create skeleton outputs
    if dry_run:
        verdict_data = create_skeleton_verdict(run_id, asset_id, config, dry_run)
        critic_report = create_skeleton_critic_report(run_id, asset_id, config)
        manifest = create_skeleton_manifest(run_id, config, output_dir)

        # Write outputs
        verdict_path = verdict_dir / "gate_verdict.json"
        with open(verdict_path, "w") as f:
            json.dump(verdict_data, f, indent=2)

        report_path = critics_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(critic_report, f, indent=2)

        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return GateResult(
            run_id=run_id,
            asset_id=asset_id,
            gate_config_id=config.gate_config_id,
            verdict="pending",
            scores=verdict_data["scores"]["by_critic"],
            failures=verdict_data["failures"],
            next_actions=verdict_data["next_actions"],
            artifacts={
                "verdict_path": str(verdict_path),
                "critic_report_path": str(report_path),
                "manifest_path": str(manifest_path),
            },
            timing={
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_ms": duration_ms,
            },
        )

    # Full evaluation mode
    # Determine render directory
    actual_render_dir = render_dir or (output_dir / "render")

    # If no pre-existing renders were provided, generate canonical renders first.
    # This ensures verifier-driven fab gates actually evaluate images, not an empty directory.
    render_errors: list[str] = []
    if render_dir is None and asset_path and asset_path.exists():
        from .render import run_render_harness

        render_result = run_render_harness(
            asset_path=asset_path,
            config=config,
            output_dir=actual_render_dir,
        )

        # Persist render result for debugging/provenance.
        render_result_path = actual_render_dir / "render_result.json"
        try:
            actual_render_dir.mkdir(parents=True, exist_ok=True)
            with open(render_result_path, "w") as f:
                json.dump(
                    {
                        "success": render_result.success,
                        "output_dir": str(render_result.output_dir),
                        "beauty_renders": render_result.beauty_renders,
                        "clay_renders": render_result.clay_renders,
                        "passes": render_result.passes,
                        "errors": render_result.errors,
                        "blender_version": render_result.blender_version,
                        "duration_ms": render_result.duration_ms,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"Failed to write render result: {e}")

        if not render_result.success:
            render_errors = render_result.errors or ["RENDER_FAILED"]

    # Run critics
    if asset_path and asset_path.exists():
        critic_results, scores, hard_fails, soft_fails = run_critics(
            asset_path=asset_path,
            render_dir=actual_render_dir,
            config=config,
            prompt=prompt,
        )
    else:
        critic_results = CriticResults()
        scores = {}
        hard_fails = ["ASSET_NOT_FOUND"]
        soft_fails = []

    # Surface render failures as gate failures so the verdict is meaningful.
    for code in render_errors:
        if code in config.hard_fail_codes:
            hard_fails.append(code)
        else:
            soft_fails.append(code)

    # Compute aggregate score
    overall_score = compute_aggregate_score(scores, config.decision.weights)
    scores["overall"] = overall_score

    # Check subscore floors
    floor_violations = check_subscore_floors(scores, config.decision.subscore_floors)

    # Determine verdict
    verdict = determine_verdict(
        overall_score=overall_score,
        threshold=config.decision.overall_pass_min,
        hard_fails=hard_fails,
        floor_violations=floor_violations,
        iteration_index=iteration_index,
        max_iterations=config.iteration.max_iterations,
    )

    # Generate next actions
    next_actions = generate_next_actions(
        verdict=verdict,
        hard_fails=hard_fails,
        soft_fails=soft_fails,
        floor_violations=floor_violations,
        repair_playbook=config.repair_playbook,
        iteration_index=iteration_index,
        max_iterations=config.iteration.max_iterations,
    )

    # Build verdict data
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    verdict_data = {
        "schema_version": "1.0",
        "run_id": run_id,
        "asset_id": asset_id,
        "gate_config_id": config.gate_config_id,
        "iteration_index": iteration_index,
        "verdict": verdict,
        "verdict_reason": _verdict_reason(
            verdict,
            hard_fails,
            floor_violations,
            overall_score,
            config.decision.overall_pass_min,
        ),
        "scores": {
            "overall": overall_score,
            "by_critic": {k: v for k, v in scores.items() if k != "overall"},
            "threshold": config.decision.overall_pass_min,
            "margin": overall_score - config.decision.overall_pass_min,
        },
        "failures": {
            "hard": list(set(hard_fails)),
            "soft": list(set(soft_fails)),
        },
        "floor_violations": floor_violations,
        "next_actions": next_actions,
        "timing": {
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_ms": duration_ms,
        },
    }

    # Build critic report
    critic_report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "asset_id": asset_id,
        "gate_config_id": config.gate_config_id,
        "critics": {
            "category": critic_results.category,
            "alignment": critic_results.alignment,
            "realism": critic_results.realism,
            "geometry": critic_results.geometry,
        },
        "scores": scores,
        "failures": {"hard": hard_fails, "soft": soft_fails},
        "timing": {
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_ms": duration_ms,
        },
    }

    # Build manifest
    manifest = create_skeleton_manifest(run_id, config, output_dir)
    manifest["iteration"]["iteration_index"] = iteration_index
    manifest["asset_path"] = str(asset_path) if asset_path else None
    manifest["prompt"] = prompt

    # Write outputs
    verdict_path = verdict_dir / "gate_verdict.json"
    with open(verdict_path, "w") as f:
        json.dump(verdict_data, f, indent=2)
    logger.info(f"Wrote verdict: {verdict_path}")

    report_path = critics_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(critic_report, f, indent=2)
    logger.info(f"Wrote critic report: {report_path}")

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Wrote manifest: {manifest_path}")

    return GateResult(
        run_id=run_id,
        asset_id=asset_id,
        gate_config_id=config.gate_config_id,
        verdict=verdict,
        scores={k: v for k, v in scores.items() if k != "overall"},
        failures={"hard": hard_fails, "soft": soft_fails},
        next_actions=next_actions,
        artifacts={
            "verdict_path": str(verdict_path),
            "critic_report_path": str(report_path),
            "manifest_path": str(manifest_path),
            "render_dir": str(actual_render_dir),
        },
        timing={
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_ms": duration_ms,
        },
    )


def _verdict_reason(
    verdict: str,
    hard_fails: List[str],
    floor_violations: List[str],
    overall_score: float,
    threshold: float,
) -> str:
    """Generate human-readable verdict reason."""
    if verdict == "pass":
        return (
            f"All checks passed. Score {overall_score:.3f} >= threshold {threshold:.3f}"
        )

    reasons = []
    if hard_fails:
        reasons.append(f"Hard failures: {', '.join(hard_fails[:3])}")
    if floor_violations:
        reasons.append(f"Floor violations: {', '.join(floor_violations[:3])}")
    if overall_score < threshold:
        reasons.append(f"Score {overall_score:.3f} < threshold {threshold:.3f}")

    return "; ".join(reasons) if reasons else "Unknown failure"


def main(args: List[str] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fab-gate",
        description="Fab Realism Gate - Evaluate Blender assets through canonical renders and critics",
    )

    parser.add_argument(
        "--asset",
        type=Path,
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
        help="Output directory for artifacts",
    )

    parser.add_argument(
        "--render-dir",
        type=Path,
        help="Pre-existing render directory (skip rendering)",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default="",
        help="Asset prompt/description for alignment critic",
    )

    parser.add_argument(
        "--iteration",
        type=int,
        default=0,
        help="Current iteration index",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Produce skeleton outputs without evaluation",
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
        help="Output result as JSON to stdout",
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
            # Try to find by ID
            config_path = find_gate_config(parsed.config)
            gate_config = load_gate_config(config_path)
    except FileNotFoundError as e:
        logger.error(f"Config not found: {e}")
        return 1

    # Run gate
    try:
        result = run_gate(
            asset_path=parsed.asset,
            config=gate_config,
            output_dir=parsed.out,
            dry_run=parsed.dry_run,
            prompt=parsed.prompt,
            render_dir=parsed.render_dir,
            iteration_index=parsed.iteration,
        )
    except Exception as e:
        logger.error(f"Gate execution failed: {e}")
        if parsed.verbose:
            import traceback

            traceback.print_exc()
        return 1

    # Output result
    if parsed.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Fab Gate Result")
        print(f"{'='*60}")
        print(f"Run ID:     {result.run_id}")
        print(f"Asset ID:   {result.asset_id}")
        print(f"Config:     {result.gate_config_id}")
        print(f"Verdict:    {result.verdict.upper()}")
        print(f"Duration:   {result.timing.get('duration_ms', 0)}ms")
        print(f"\nArtifacts:")
        for name, path in result.artifacts.items():
            print(f"  {name}: {path}")
        print(f"{'='*60}\n")

    if parsed.dry_run:
        return 0

    if result.verdict == "pass":
        return 0

    # Non-pass verdicts should fail the process so callers (Verifier/CI) can block.
    return 3 if result.verdict == "escalate" else 2


if __name__ == "__main__":
    sys.exit(main())
