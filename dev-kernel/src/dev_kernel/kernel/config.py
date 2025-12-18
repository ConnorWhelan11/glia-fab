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
    path: str = ""  # CLI executable (defaults to toolchain name)
    model: str | None = None  # Default model for this toolchain
    timeout_seconds: int = 1800  # 30 minutes
    max_tokens: int = 100_000
    env: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)  # adapter-specific passthrough


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
class RoutingRule:
    """A single routing rule (evaluated in order)."""

    match: dict[str, Any] = field(default_factory=dict)
    use: list[str] = field(default_factory=list)
    speculate: bool = False
    parallelism: int | None = None


@dataclass
class RoutingConfig:
    """Toolchain routing configuration."""

    rules: list[RoutingRule] = field(default_factory=list)
    fallbacks: dict[str, list[str]] = field(default_factory=dict)


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
    routing: RoutingConfig = field(default_factory=RoutingConfig)

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
        data = dict(data or {})

        # Support both "flat" config keys and the documented nested "version: 1.0" format.
        scheduling_data = data.get("scheduling") or {}
        toolchains_data = data.get("toolchains") or {}
        routing_data = data.get("routing") or {}
        gates_data = data.get("gates") or {}
        speculation_data = data.get("speculation") or {}

        # Back-compat: allow flat keys at top-level (tests + older configs).
        max_concurrent_workcells = scheduling_data.get(
            "max_concurrent_workcells", data.get("max_concurrent_workcells", 3)
        )
        max_concurrent_tokens = scheduling_data.get(
            "max_concurrent_tokens", data.get("max_concurrent_tokens", 200_000)
        )
        starvation_threshold_hours = scheduling_data.get(
            "starvation_threshold_hours", data.get("starvation_threshold_hours", 4.0)
        )

        # Build toolchain configs
        toolchains = {}
        for name, tc_data in toolchains_data.items():
            if isinstance(tc_data, dict):
                import shlex

                # Support both:
                # - {model: "...", timeout_seconds: ...}
                # - {path: "...", default_model: "...", timeout_minutes: ... , config: {...}}
                timeout_seconds = int(tc_data.get("timeout_seconds", 0) or 0)
                if not timeout_seconds and tc_data.get("timeout_minutes"):
                    timeout_seconds = int(tc_data["timeout_minutes"]) * 60

                raw_config = tc_data.get("config")
                adapter_config: dict[str, Any] = dict(raw_config) if isinstance(raw_config, dict) else {}

                # Back-compat: allow "command" to include an executable + flags.
                path_value = tc_data.get("path")
                command_value = tc_data.get("command")
                parsed_args: list[str] = []
                if not path_value and isinstance(command_value, str) and command_value.strip():
                    try:
                        parsed_args = shlex.split(command_value)
                    except ValueError:
                        parsed_args = command_value.split()
                    if parsed_args:
                        path_value = parsed_args[0]

                # Promote a few common adapter keys when provided at the top-level.
                for key in ("approval_mode", "skip_permissions", "provider", "auto_approve", "agent"):
                    if key in tc_data and key not in adapter_config:
                        adapter_config[key] = tc_data[key]

                # Best-effort parsing of common flags from legacy "command".
                if parsed_args:
                    if "--model" in parsed_args and "model" not in adapter_config:
                        try:
                            adapter_config["model"] = parsed_args[parsed_args.index("--model") + 1]
                        except Exception:
                            pass
                    if "--approval-mode" in parsed_args and "approval_mode" not in adapter_config:
                        try:
                            adapter_config["approval_mode"] = parsed_args[parsed_args.index("--approval-mode") + 1]
                        except Exception:
                            pass
                    if "--dangerously-skip-permissions" in parsed_args and "skip_permissions" not in adapter_config:
                        adapter_config["skip_permissions"] = True
                    if "-y" in parsed_args and "auto_approve" not in adapter_config:
                        adapter_config["auto_approve"] = True

                toolchains[name] = ToolchainConfig(
                    name=name,
                    enabled=bool(tc_data.get("enabled", True)),
                    path=str(path_value or ""),
                    model=tc_data.get("model") or adapter_config.get("model") or tc_data.get("default_model"),
                    timeout_seconds=timeout_seconds or 1800,
                    max_tokens=int(tc_data.get("max_tokens", 100_000)),
                    env=dict(tc_data.get("env") or {}),
                    config=adapter_config,
                )

        # Build routing config (optional)
        routing_rules: list[RoutingRule] = []
        rules_data = routing_data.get("rules") if isinstance(routing_data, dict) else None
        if isinstance(rules_data, list):
            for rule in rules_data:
                if not isinstance(rule, dict):
                    continue
                match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
                use = rule.get("use")
                if isinstance(use, str):
                    use_list = [use]
                elif isinstance(use, list):
                    use_list = [str(x) for x in use]
                else:
                    use_list = []

                parallelism_value = rule.get("parallelism")
                parallelism_int: int | None = None
                if parallelism_value is not None:
                    try:
                        parallelism_int = int(parallelism_value)
                    except (TypeError, ValueError):
                        parallelism_int = None

                routing_rules.append(
                    RoutingRule(
                        match=dict(match),
                        use=use_list,
                        speculate=bool(rule.get("speculate", False)),
                        parallelism=parallelism_int,
                    )
                )

        fallbacks = {}
        fallbacks_data = routing_data.get("fallbacks") if isinstance(routing_data, dict) else None
        if isinstance(fallbacks_data, dict):
            for k, v in fallbacks_data.items():
                if isinstance(v, list):
                    fallbacks[str(k)] = [str(x) for x in v]

        # Normalize speculation config: support docs-style "auto_trigger" nesting and ignore unknown keys.
        speculation_data = dict(speculation_data) if isinstance(speculation_data, dict) else {}
        auto_trigger = speculation_data.pop("auto_trigger", None)
        if isinstance(auto_trigger, dict):
            if "on_critical_path" in auto_trigger and "auto_trigger_on_critical_path" not in speculation_data:
                speculation_data["auto_trigger_on_critical_path"] = auto_trigger.get("on_critical_path")
            if "risk_levels" in auto_trigger and "auto_trigger_risk_levels" not in speculation_data:
                speculation_data["auto_trigger_risk_levels"] = auto_trigger.get("risk_levels")

        def _filter_keys(src: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
            return {k: v for k, v in src.items() if k in allowed}

        gates_kwargs = _filter_keys(
            dict(gates_data) if isinstance(gates_data, dict) else {},
            {"test_command", "typecheck_command", "lint_command", "build_command", "timeout_seconds", "retry_flaky"},
        )
        speculation_kwargs = _filter_keys(
            speculation_data,
            {
                "enabled",
                "default_parallelism",
                "max_parallelism",
                "vote_threshold",
                "auto_trigger_on_critical_path",
                "auto_trigger_risk_levels",
            },
        )

        # Build main config
        config = cls(
            max_concurrent_workcells=int(max_concurrent_workcells),
            max_concurrent_tokens=int(max_concurrent_tokens),
            starvation_threshold_hours=float(starvation_threshold_hours),
            toolchain_priority=data.get(
                "toolchain_priority", ["codex", "claude", "crush"]
            ),
            toolchains=toolchains,
            gates=GatesConfig(**gates_kwargs) if gates_kwargs else GatesConfig(),
            speculation=SpeculationConfig(**speculation_kwargs) if speculation_kwargs else SpeculationConfig(),
            routing=RoutingConfig(rules=routing_rules, fallbacks=fallbacks),
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
                    "path": tc.path,
                    "model": tc.model,
                    "timeout_seconds": tc.timeout_seconds,
                    "max_tokens": tc.max_tokens,
                    "env": tc.env,
                    "config": tc.config,
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
            "routing": {
                "rules": [
                    {
                        "match": r.match,
                        "use": r.use,
                        "speculate": r.speculate,
                        "parallelism": r.parallelism,
                    }
                    for r in self.routing.rules
                ],
                "fallbacks": self.routing.fallbacks,
            },
        }
