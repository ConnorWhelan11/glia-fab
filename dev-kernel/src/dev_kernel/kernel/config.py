"""
Kernel Configuration - All settings for the Dev Kernel orchestrator.

Loaded from YAML config file with environment variable override support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ToolchainConfig:
    """Configuration for a specific toolchain adapter."""

    name: str
    enabled: bool = True
    command: str = ""
    timeout_seconds: int = 1800  # 30 minutes
    max_tokens: int = 100_000
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class GatesConfig:
    """Configuration for quality gates."""

    test_command: str = "pytest"
    typecheck_command: str = "mypy ."
    lint_command: str = "ruff check ."
    build_command: str | None = None
    timeout_seconds: int = 300
    retry_flaky: int = 2


@dataclass
class SpeculationConfig:
    """Configuration for speculate+vote mode."""

    enabled: bool = True
    default_parallelism: int = 2
    max_parallelism: int = 3
    vote_threshold: float = 0.7
    auto_trigger_on_critical_path: bool = True
    auto_trigger_risk_levels: list[str] = field(
        default_factory=lambda: ["high", "critical"]
    )


@dataclass
class KernelConfig:
    """Main kernel configuration."""

    # Execution limits
    max_concurrent_workcells: int = 3
    max_concurrent_tokens: int = 200_000
    starvation_threshold_hours: float = 4.0

    # Paths
    repo_root: Path = field(default_factory=Path.cwd)
    beads_path: Path = field(default_factory=lambda: Path(".beads"))
    config_path: Path = field(default_factory=lambda: Path(".dev-kernel/config.yaml"))
    workcells_dir: Path = field(default_factory=lambda: Path(".workcells"))
    logs_dir: Path = field(default_factory=lambda: Path(".dev-kernel/logs"))

    # Toolchain priority order
    toolchain_priority: list[str] = field(
        default_factory=lambda: ["codex", "claude", "crush"]
    )

    # Sub-configs
    toolchains: dict[str, ToolchainConfig] = field(default_factory=dict)
    gates: GatesConfig = field(default_factory=GatesConfig)
    speculation: SpeculationConfig = field(default_factory=SpeculationConfig)

    # Runtime overrides
    force_speculate: bool = False
    dry_run: bool = False
    watch_mode: bool = False

    @classmethod
    def load(cls, config_path: Path) -> KernelConfig:
        """Load configuration from YAML file."""
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data, config_path)

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path | None = None) -> KernelConfig:
        """Create config from dictionary."""
        # Extract nested configs
        toolchains_data = data.pop("toolchains", {})
        gates_data = data.pop("gates", {})
        speculation_data = data.pop("speculation", {})

        # Build toolchain configs
        toolchains = {}
        for name, tc_data in toolchains_data.items():
            if isinstance(tc_data, dict):
                toolchains[name] = ToolchainConfig(name=name, **tc_data)

        # Build main config
        config = cls(
            max_concurrent_workcells=data.get("max_concurrent_workcells", 3),
            max_concurrent_tokens=data.get("max_concurrent_tokens", 200_000),
            starvation_threshold_hours=data.get("starvation_threshold_hours", 4.0),
            toolchain_priority=data.get(
                "toolchain_priority", ["codex", "claude", "crush"]
            ),
            toolchains=toolchains,
            gates=GatesConfig(**gates_data) if gates_data else GatesConfig(),
            speculation=SpeculationConfig(**speculation_data)
            if speculation_data
            else SpeculationConfig(),
        )

        if config_path:
            config.config_path = config_path
            config.repo_root = config_path.parent.parent

        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary."""
        return {
            "max_concurrent_workcells": self.max_concurrent_workcells,
            "max_concurrent_tokens": self.max_concurrent_tokens,
            "starvation_threshold_hours": self.starvation_threshold_hours,
            "toolchain_priority": self.toolchain_priority,
            "toolchains": {
                name: {
                    "enabled": tc.enabled,
                    "command": tc.command,
                    "timeout_seconds": tc.timeout_seconds,
                    "max_tokens": tc.max_tokens,
                }
                for name, tc in self.toolchains.items()
            },
            "gates": {
                "test_command": self.gates.test_command,
                "typecheck_command": self.gates.typecheck_command,
                "lint_command": self.gates.lint_command,
                "build_command": self.gates.build_command,
                "timeout_seconds": self.gates.timeout_seconds,
            },
            "speculation": {
                "enabled": self.speculation.enabled,
                "default_parallelism": self.speculation.default_parallelism,
                "vote_threshold": self.speculation.vote_threshold,
            },
        }

