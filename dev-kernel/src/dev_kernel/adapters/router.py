"""
Toolchain Router - Smart selection of toolchains based on task characteristics.

Routes tasks to the most appropriate toolchain based on:
- Task complexity and risk
- Toolchain availability and health
- Cost optimization
- Historical performance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from dev_kernel.adapters.base import ToolchainAdapter
from dev_kernel.adapters.codex import CodexAdapter
from dev_kernel.adapters.claude import ClaudeAdapter
from dev_kernel.adapters.crush import CrushAdapter

if TYPE_CHECKING:
    from dev_kernel.state.models import Issue
    from dev_kernel.kernel.config import KernelConfig

logger = structlog.get_logger()


@dataclass
class RoutingDecision:
    """Result of routing decision."""

    toolchain: str
    reason: str
    alternatives: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0


@dataclass
class ToolchainProfile:
    """Profile of a toolchain's capabilities."""

    name: str
    max_complexity: str  # XS, S, M, L, XL
    best_for: list[str]  # tags like "auth", "api", "refactor"
    cost_tier: str  # low, medium, high
    speed_tier: str  # fast, medium, slow
    reliability: float  # 0-1


# Default profiles based on known characteristics
DEFAULT_PROFILES: dict[str, ToolchainProfile] = {
    "codex": ToolchainProfile(
        name="codex",
        max_complexity="XL",
        best_for=["refactor", "api", "test", "fix"],
        cost_tier="high",
        speed_tier="medium",
        reliability=0.85,
    ),
    "claude": ToolchainProfile(
        name="claude",
        max_complexity="XL",
        best_for=["auth", "security", "complex", "architecture"],
        cost_tier="high",
        speed_tier="medium",
        reliability=0.90,
    ),
    "crush": ToolchainProfile(
        name="crush",
        max_complexity="XL",
        best_for=["general", "flexible", "multi-provider"],
        cost_tier="medium",  # Can use cheaper models
        speed_tier="fast",
        reliability=0.85,
    ),
}


class ToolchainRouter:
    """
    Smart router for selecting the best toolchain for a task.

    Selection criteria:
    1. Explicit hint from issue (dk_tool_hint)
    2. Task tags matching toolchain profiles
    3. Complexity matching
    4. Cost optimization
    5. Availability
    """

    def __init__(
        self,
        config: KernelConfig,
        profiles: dict[str, ToolchainProfile] | None = None,
    ) -> None:
        self.config = config
        self.profiles = profiles or DEFAULT_PROFILES
        self._adapters: dict[str, ToolchainAdapter] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        """Initialize available adapters."""
        adapter_classes: dict[str, type[ToolchainAdapter]] = {
            "codex": CodexAdapter,
            "claude": ClaudeAdapter,
            "crush": CrushAdapter,
        }

        for name in self.config.toolchain_priority:
            if name in adapter_classes:
                self._adapters[name] = adapter_classes[name]()

    def route(self, issue: Issue) -> RoutingDecision:
        """
        Select the best toolchain for an issue.

        Returns routing decision with reasoning.
        """
        # Check explicit hint first
        if issue.dk_tool_hint and issue.dk_tool_hint in self._adapters:
            adapter = self._adapters[issue.dk_tool_hint]
            if adapter.available:
                return RoutingDecision(
                    toolchain=issue.dk_tool_hint,
                    reason="explicit_hint",
                    alternatives=self._get_alternatives(issue.dk_tool_hint),
                )

        # Score each toolchain
        scores: dict[str, float] = {}
        reasons: dict[str, str] = {}

        for name, adapter in self._adapters.items():
            if not adapter.available:
                continue

            score, reason = self._score_toolchain(name, issue)
            scores[name] = score
            reasons[name] = reason

        if not scores:
            # No available toolchains - return first in priority
            first = (
                self.config.toolchain_priority[0]
                if self.config.toolchain_priority
                else "codex"
            )
            return RoutingDecision(
                toolchain=first,
                reason="no_available_fallback",
                alternatives=[],
            )

        # Select best
        best = max(scores, key=lambda x: scores[x])
        alternatives = [n for n in scores if n != best]

        logger.debug(
            "Toolchain routed",
            issue_id=issue.id,
            selected=best,
            reason=reasons[best],
            scores=scores,
        )

        return RoutingDecision(
            toolchain=best,
            reason=reasons[best],
            alternatives=alternatives,
        )

    def _score_toolchain(self, name: str, issue: Issue) -> tuple[float, str]:
        """
        Score a toolchain for an issue.

        Returns (score, reason) tuple.
        """
        profile = self.profiles.get(name)
        if not profile:
            return 50.0, "no_profile"

        score = 50.0
        reason = "default"

        # Tag matching (0-20 points)
        tags = issue.tags or []
        matching_tags = len(set(tags) & set(profile.best_for))
        if matching_tags > 0:
            score += matching_tags * 10
            reason = f"tag_match:{','.join(set(tags) & set(profile.best_for))}"

        # Complexity matching (0-15 points)
        complexity_order = ["XS", "S", "M", "L", "XL"]
        issue_complexity = (
            complexity_order.index(issue.dk_size)
            if issue.dk_size in complexity_order
            else 2
        )
        max_complexity = complexity_order.index(profile.max_complexity)

        if issue_complexity <= max_complexity:
            score += 15
        else:
            score -= 20  # Penalize if over capacity

        # Risk matching (0-15 points)
        # High-risk tasks should go to high-reliability toolchains
        if issue.dk_risk in ("high", "critical"):
            score += profile.reliability * 15
            if profile.reliability >= 0.9:
                reason = "high_reliability_for_risk"

        # Cost optimization (0-10 points)
        # Lower cost is better for low-risk, simple tasks
        if issue.dk_risk == "low" and issue.dk_size in ("XS", "S"):
            cost_bonus = {"low": 10, "medium": 5, "high": 0}.get(profile.cost_tier, 5)
            score += cost_bonus
            if cost_bonus == 10:
                reason = "cost_optimized"

        # Priority order bonus (0-10 points)
        # Give slight preference to priority order
        try:
            priority_index = self.config.toolchain_priority.index(name)
            score += (len(self.config.toolchain_priority) - priority_index) * 2
        except ValueError:
            pass

        return score, reason

    def _get_alternatives(self, selected: str) -> list[str]:
        """Get alternative toolchains."""
        return [
            name
            for name, adapter in self._adapters.items()
            if name != selected and adapter.available
        ]

    def get_available(self) -> list[str]:
        """Get list of available toolchains."""
        return [name for name, adapter in self._adapters.items() if adapter.available]

    def health_check_all(self) -> dict[str, bool]:
        """Check health of all adapters."""
        results = {}
        for name, adapter in self._adapters.items():
            try:
                results[name] = adapter.health_check_sync()
            except Exception:
                results[name] = False
        return results
