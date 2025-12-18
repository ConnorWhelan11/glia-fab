"""
Fab Iteration Loop - Iterate-until-pass repair cycle.

Implements the state machine:
  GENERATE → EXPORT → RENDER → CRITIC → VERDICT
    ↓ fail                              ↓ pass
  REPAIR ←─────────────────────────────→ DONE

This module provides functions for:
- Determining if an issue needs repair vs escalation
- Creating repair issues from gate failures
- Injecting critic feedback into repair instructions
- Tracking iteration history
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import GateConfig

logger = logging.getLogger(__name__)


@dataclass
class RepairIssue:
    """A repair issue generated from gate failure."""

    title: str
    description: str
    parent_issue_id: str
    iteration_index: int
    fail_codes: List[str]
    repair_instructions: str
    priority: int = 2
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "parent_issue_id": self.parent_issue_id,
            "iteration_index": self.iteration_index,
            "fail_codes": self.fail_codes,
            "repair_instructions": self.repair_instructions,
            "priority": self.priority,
            "tags": self.tags,
            "context": self.context,
        }


@dataclass
class IterationState:
    """Tracks iteration state for an asset issue."""

    issue_id: str
    current_iteration: int = 0
    max_iterations: int = 5
    status: str = "active"  # active, passed, escalated, abandoned
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_fail_codes: List[str] = field(default_factory=list)
    last_scores: Dict[str, float] = field(default_factory=dict)
    template_fallback_suggested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "history": self.history,
            "last_fail_codes": self.last_fail_codes,
            "last_scores": self.last_scores,
            "template_fallback_suggested": self.template_fallback_suggested,
        }


class IterationManager:
    """
    Manages iterate-until-pass cycles for asset issues.

    Tracks iteration state, determines repair vs escalation,
    and generates repair issues with critic feedback.
    """

    def __init__(
        self,
        gate_config: GateConfig,
        state_dir: Optional[Path] = None,
    ):
        """
        Initialize iteration manager.

        Args:
            gate_config: Gate configuration with repair playbook
            state_dir: Directory to persist iteration state
        """
        self.gate_config = gate_config
        self.state_dir = state_dir
        self._states: Dict[str, IterationState] = {}

    def get_state(self, issue_id: str) -> IterationState:
        """Get or create iteration state for an issue."""
        if issue_id not in self._states:
            # Try to load from disk
            if self.state_dir:
                state_path = self.state_dir / f"{issue_id}_iteration.json"
                if state_path.exists():
                    try:
                        with open(state_path) as f:
                            data = json.load(f)
                        self._states[issue_id] = IterationState(
                            issue_id=data.get("issue_id", issue_id),
                            current_iteration=data.get("current_iteration", 0),
                            max_iterations=data.get("max_iterations", self.gate_config.iteration.max_iterations),
                            status=data.get("status", "active"),
                            history=data.get("history", []),
                            last_fail_codes=data.get("last_fail_codes", []),
                            last_scores=data.get("last_scores", {}),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to load iteration state: {e}")

            if issue_id not in self._states:
                self._states[issue_id] = IterationState(
                    issue_id=issue_id,
                    max_iterations=self.gate_config.iteration.max_iterations,
                )

        return self._states[issue_id]

    def save_state(self, state: IterationState) -> None:
        """Persist iteration state to disk."""
        if not self.state_dir:
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        state_path = self.state_dir / f"{state.issue_id}_iteration.json"

        try:
            with open(state_path, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save iteration state: {e}")

    def record_gate_result(
        self,
        issue_id: str,
        verdict: str,
        scores: Dict[str, float],
        fail_codes: List[str],
        run_id: str,
    ) -> IterationState:
        """
        Record a gate result for an issue.

        Returns updated iteration state.
        """
        state = self.get_state(issue_id)

        # Record in history
        state.history.append({
            "iteration": state.current_iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "verdict": verdict,
            "scores": scores,
            "fail_codes": fail_codes,
        })

        state.last_fail_codes = fail_codes
        state.last_scores = scores

        if verdict == "pass":
            state.status = "passed"
        elif state.current_iteration >= state.max_iterations - 1:
            state.status = "escalated"
        else:
            state.current_iteration += 1

        self.save_state(state)
        return state

    def should_retry(self, issue_id: str) -> bool:
        """Check if an issue should be retried."""
        state = self.get_state(issue_id)

        if state.status == "passed":
            return False
        if state.status == "escalated":
            return False
        if state.status == "abandoned":
            return False
        if state.current_iteration >= state.max_iterations:
            return False

        return True

    def should_escalate(self, issue_id: str) -> bool:
        """Check if an issue should be escalated."""
        state = self.get_state(issue_id)

        # Max iterations reached
        if state.current_iteration >= state.max_iterations:
            return True

        # Check for repeated hard fails
        if len(state.history) >= 2:
            recent_hard_fails = []
            for entry in state.history[-2:]:
                hard_fails = [c for c in entry.get("fail_codes", [])
                             if c in self.gate_config.hard_fail_codes]
                recent_hard_fails.extend(hard_fails)

            # Same hard fail code twice = escalate
            from collections import Counter
            counts = Counter(recent_hard_fails)
            if any(c >= 2 for c in counts.values()):
                return True

        return False

    def should_suggest_template(self, issue_id: str) -> bool:
        """Check if template fallback should be suggested."""
        state = self.get_state(issue_id)

        # Already suggested
        if state.template_fallback_suggested:
            return False

        # After 2+ iterations with geometry failures
        if state.current_iteration >= 2:
            geo_fails = ["GEO_SCALE_IMPLAUSIBLE", "GEO_WHEEL_COUNT_LOW", "GEO_TRI_COUNT_TRIVIAL"]
            for entry in state.history:
                if any(code in entry.get("fail_codes", []) for code in geo_fails):
                    return True

        return False

    def create_repair_issue(
        self,
        original_issue_id: str,
        original_title: str,
        fail_codes: List[str],
        scores: Dict[str, float],
        render_paths: Optional[List[str]] = None,
    ) -> RepairIssue:
        """
        Create a repair issue from gate failure.

        Args:
            original_issue_id: ID of the original issue
            original_title: Title of the original issue
            fail_codes: Failure codes from gate
            scores: Scores from critics
            render_paths: Paths to failing render images

        Returns:
            RepairIssue with instructions
        """
        state = self.get_state(original_issue_id)

        # Build repair instructions from playbook
        instructions = self._build_repair_instructions(fail_codes, scores)

        # Check for template suggestion
        suggest_template = self.should_suggest_template(original_issue_id)
        if suggest_template:
            state.template_fallback_suggested = True
            self.save_state(state)
            instructions += self._get_template_suggestion()

        # Build description
        description = self._build_repair_description(
            original_issue_id=original_issue_id,
            iteration=state.current_iteration,
            fail_codes=fail_codes,
            scores=scores,
            instructions=instructions,
            render_paths=render_paths,
        )

        # Determine priority from fail codes
        priority = self._determine_priority(fail_codes)

        return RepairIssue(
            title=f"[REPAIR {state.current_iteration}] {original_title}",
            description=description,
            parent_issue_id=original_issue_id,
            iteration_index=state.current_iteration,
            fail_codes=fail_codes,
            repair_instructions=instructions,
            priority=priority,
            tags=["repair", "asset", f"iteration:{state.current_iteration}"],
            context={
                "scores": scores,
                "render_paths": render_paths or [],
                "template_suggested": suggest_template,
            },
        )

    def _build_repair_instructions(
        self,
        fail_codes: List[str],
        scores: Dict[str, float],
    ) -> str:
        """Build repair instructions from fail codes."""
        sections = []

        # Group by priority
        high_priority = []
        medium_priority = []
        low_priority = []

        for code in fail_codes:
            if code in self.gate_config.repair_playbook:
                entry = self.gate_config.repair_playbook[code]
                priority = entry.get("priority", 3)
                item = (code, entry.get("instructions", f"Fix {code}"))

                if priority == 1:
                    high_priority.append(item)
                elif priority == 2:
                    medium_priority.append(item)
                else:
                    low_priority.append(item)

        # Build sections
        if high_priority:
            sections.append("## Critical Issues (Must Fix)\n")
            for code, instructions in high_priority:
                sections.append(f"### {code}\n{instructions}\n")

        if medium_priority:
            sections.append("## Important Issues\n")
            for code, instructions in medium_priority:
                sections.append(f"### {code}\n{instructions}\n")

        if low_priority:
            sections.append("## Minor Issues\n")
            for code, instructions in low_priority:
                sections.append(f"### {code}\n{instructions}\n")

        # Add scores summary
        sections.append("## Current Scores\n")
        for critic, score in scores.items():
            status = "✓" if score >= 0.6 else "✗"
            sections.append(f"- {critic}: {score:.2f} {status}\n")

        return "\n".join(sections)

    def _build_repair_description(
        self,
        original_issue_id: str,
        iteration: int,
        fail_codes: List[str],
        scores: Dict[str, float],
        instructions: str,
        render_paths: Optional[List[str]] = None,
    ) -> str:
        """Build full repair issue description."""
        parts = [
            f"**Repair iteration {iteration + 1} for issue #{original_issue_id}**\n",
            f"The previous attempt failed gate evaluation with the following issues:\n",
            f"\n**Failure codes:** {', '.join(fail_codes)}\n",
            f"\n---\n\n{instructions}\n",
        ]

        if render_paths:
            parts.append("\n## Reference Renders\n")
            parts.append("Review these renders to understand the current state:\n")
            for path in render_paths[:5]:  # Limit to 5
                parts.append(f"- `{path}`\n")

        parts.append("\n---\n")
        parts.append(f"\n*Iteration {iteration + 1} of {self.gate_config.iteration.max_iterations}*")

        return "".join(parts)

    def _get_template_suggestion(self) -> str:
        """Get template fallback suggestion text."""
        template_ref = "car_sedan_template_v001"  # Default

        # Check iteration config for template
        if hasattr(self.gate_config, "iteration"):
            template_fallback = getattr(self.gate_config.iteration, "template_fallback", None)
            if template_fallback:
                default = getattr(template_fallback, "default_template", None)
                if default:
                    template_ref = default

        return f"""

## 💡 Template Fallback Recommended

After multiple failed attempts, consider starting from a known-good template:

**Suggested template:** `{template_ref}`

Using a template provides:
- Correct scale and proportions
- Named parts (Body, Wheels, etc.)
- Baseline materials that pass the gate

To use:
1. Load the template from `fab/templates/car/sedan_v001/`
2. Modify colors, materials, and details as needed
3. Preserve the core geometry and part structure
"""

    def _determine_priority(self, fail_codes: List[str]) -> int:
        """Determine repair priority from fail codes."""
        # Check playbook priorities
        min_priority = 5

        for code in fail_codes:
            if code in self.gate_config.repair_playbook:
                entry = self.gate_config.repair_playbook[code]
                priority = entry.get("priority", 3)
                min_priority = min(min_priority, priority)

        # Hard fails = priority 1
        if any(code in self.gate_config.hard_fail_codes for code in fail_codes):
            min_priority = 1

        return min_priority


def should_create_repair_issue(
    issue_tags: List[str],
    verdict: str,
    iteration_index: int,
    max_iterations: int,
) -> bool:
    """
    Determine if a repair issue should be created.

    Asset issues that fail get repair issues instead of blocking.
    """
    # Only for asset-tagged issues
    is_asset = any(t.startswith("asset:") for t in issue_tags)
    if not is_asset:
        return False

    # Must have failed
    if verdict == "pass":
        return False

    # Not at max iterations
    if iteration_index >= max_iterations - 1:
        return False

    return True


def create_repair_context(
    gate_result: Dict[str, Any],
    render_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Create context for repair issue from gate result.

    Extracts key information for the repair issue description.
    """
    context = {
        "scores": gate_result.get("scores", {}),
        "fail_codes": {
            "hard": gate_result.get("failures", {}).get("hard", []),
            "soft": gate_result.get("failures", {}).get("soft", []),
        },
        "next_actions": gate_result.get("next_actions", []),
    }

    # Include render paths if available
    if render_dir and render_dir.exists():
        beauty_dir = render_dir / "beauty"
        if beauty_dir.exists():
            context["render_paths"] = [str(p) for p in sorted(beauty_dir.glob("*.png"))[:5]]

    return context

