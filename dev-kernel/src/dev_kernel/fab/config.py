"""
Fab Gate Configuration Loading

Handles loading and validation of gate configurations from YAML files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class RenderConfig:
    """Render settings for determinism."""

    engine: str = "CYCLES"
    device: str = "CPU"
    resolution: Tuple[int, int] = (768, 512)
    samples: int = 128
    seed: int = 1337
    denoise: bool = False
    threads: int = 4
    output_format: str = "PNG"
    color_depth: int = 16


@dataclass
class CriticConfig:
    """Configuration for a single critic."""

    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionConfig:
    """Gate decision parameters."""

    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "category": 0.35,
            "alignment": 0.20,
            "realism": 0.20,
            "geometry": 0.25,
        }
    )
    overall_pass_min: float = 0.75
    subscore_floors: Dict[str, float] = field(
        default_factory=lambda: {
            "category": 0.70,
            "geometry": 0.60,
            "alignment": 0.50,
            "realism": 0.40,
        }
    )


@dataclass
class IterationConfig:
    """Iteration loop settings."""

    max_iterations: int = 5
    vote_pack_on_uncertainty: bool = True
    uncertainty_band: float = 0.03


@dataclass
class GateConfig:
    """Complete gate configuration."""

    gate_config_id: str
    category: str
    version: str = "1.0.0"

    # Scene references
    lookdev_scene_id: Optional[str] = None
    camera_rig_id: Optional[str] = None

    # Sub-configs
    render: RenderConfig = field(default_factory=RenderConfig)
    critics: Dict[str, CriticConfig] = field(default_factory=dict)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    iteration: IterationConfig = field(default_factory=IterationConfig)

    # Failure handling
    hard_fail_codes: List[str] = field(default_factory=list)
    repair_playbook: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def load_gate_config(config_path: Path) -> GateConfig:
    """
    Load gate configuration from YAML file.

    Args:
        config_path: Path to gate config YAML file

    Returns:
        Parsed GateConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Gate config not found: {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid config format in {config_path}")

    # Parse render config
    render_raw = raw.get("render", {})
    render = RenderConfig(
        engine=render_raw.get("engine", "CYCLES"),
        device=render_raw.get("device", "CPU"),
        resolution=tuple(render_raw.get("resolution", [768, 512])),
        samples=render_raw.get("samples", 128),
        seed=render_raw.get("seed", 1337),
        denoise=render_raw.get("denoise", False),
        threads=render_raw.get("threads", 4),
        output_format=render_raw.get("output", {}).get("format", "PNG"),
        color_depth=render_raw.get("output", {}).get("color_depth", 16),
    )

    # Parse critics config
    critics = {}
    for name, cfg in raw.get("critics", {}).items():
        if isinstance(cfg, dict):
            enabled = cfg.pop("enabled", True)
            critics[name] = CriticConfig(enabled=enabled, params=cfg)

    # Parse decision config
    decision_raw = raw.get("decision", {})
    decision = DecisionConfig(
        weights=decision_raw.get("weights", DecisionConfig().weights),
        overall_pass_min=decision_raw.get("overall_pass_min", 0.75),
        subscore_floors=decision_raw.get(
            "subscore_floors", DecisionConfig().subscore_floors
        ),
    )

    # Parse iteration config
    iteration_raw = raw.get("iteration", {})
    iteration = IterationConfig(
        max_iterations=iteration_raw.get(
            "max_iterations", iteration_raw.get("max_iters", 5)
        ),
        vote_pack_on_uncertainty=iteration_raw.get("vote_pack_on_uncertainty", True),
        uncertainty_band=iteration_raw.get("uncertainty_band", 0.03),
    )

    return GateConfig(
        gate_config_id=raw.get("gate_config_id", config_path.stem),
        category=raw.get("category", "unknown"),
        version=raw.get("version", "1.0.0"),
        lookdev_scene_id=raw.get("lookdev_scene_id"),
        camera_rig_id=raw.get("camera_rig_id"),
        render=render,
        critics=critics,
        decision=decision,
        iteration=iteration,
        hard_fail_codes=raw.get("hard_fail_codes", []),
        repair_playbook=raw.get("repair_playbook", {}),
    )


def find_gate_config(gate_config_id: str, search_paths: List[Path] = None) -> Path:
    """
    Find gate config file by ID.

    Args:
        gate_config_id: Gate configuration identifier (e.g., "car_realism_v001")
        search_paths: Paths to search for configs

    Returns:
        Path to config file

    Raises:
        FileNotFoundError: If config not found
    """
    if search_paths is None:
        # Default search paths (relative to repo root/workcell).
        search_paths = [Path("fab/gates"), Path(".fab/gates")]

        # Also search upwards from CWD to support running from subdirs (e.g. dev-kernel/).
        cwd = Path.cwd().resolve()
        for parent in [cwd, *cwd.parents]:
            search_paths.append(parent / "fab" / "gates")
            search_paths.append(parent / ".fab" / "gates")

        # De-duplicate while preserving order.
        seen: set[Path] = set()
        search_paths = [p for p in search_paths if not (p in seen or seen.add(p))]

    for base_path in search_paths:
        config_path = base_path / f"{gate_config_id}.yaml"
        if config_path.exists():
            return config_path

    raise FileNotFoundError(
        f"Gate config '{gate_config_id}' not found in: {search_paths}"
    )
