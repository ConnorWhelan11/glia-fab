"""
Dispatcher - Spawns workcells, routes to toolchains, monitors execution.

Responsibilities:
- Create git worktrees for each task
- Write task manifests
- Route tasks to appropriate toolchains via adapters
- Monitor execution and collect results
- Handle timeouts and errors
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from dev_kernel.adapters import CodexAdapter, ClaudeAdapter, get_adapter
from dev_kernel.adapters.base import PatchProof

if TYPE_CHECKING:
    from dev_kernel.kernel.config import KernelConfig
    from dev_kernel.state.models import Issue

logger = structlog.get_logger()


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class DispatchResult:
    """Result of dispatching a task."""

    success: bool
    proof: PatchProof | None
    workcell_id: str
    issue_id: str
    toolchain: str
    duration_ms: int = 0
    error: str | None = None
    speculate_tag: str | None = None


@dataclass
class SpeculateResult:
    """Result of speculate+vote dispatch."""

    winner: DispatchResult | None
    candidates: list[DispatchResult] = field(default_factory=list)
    all_failed: bool = False


class Dispatcher:
    """
    Spawns workcells and routes tasks to toolchains.

    Uses the adapter system to execute tasks via different
    LLM-powered coding agents (Codex, Claude, etc).
    """

    def __init__(self, config: KernelConfig) -> None:
        self.config = config
        self._adapters: dict[str, Any] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        """Initialize available adapters."""
        for name in self.config.toolchain_priority:
            tc_config = self.config.toolchains.get(name, {})
            if isinstance(tc_config, dict):
                adapter_config = tc_config
            else:
                adapter_config = {
                    "model": getattr(tc_config, "model", None),
                    "timeout_seconds": getattr(tc_config, "timeout_seconds", 1800),
                }

            adapter = get_adapter(name, adapter_config)
            if adapter:
                self._adapters[name] = adapter
                logger.debug(
                    "Adapter initialized", name=name, available=adapter.available
                )

    def dispatch(
        self,
        issue: Issue,
        workcell_path: Path,
        speculate_tag: str | None = None,
    ) -> DispatchResult:
        """
        Dispatch a task to a workcell synchronously.

        1. Write task manifest
        2. Invoke toolchain via adapter
        3. Return result with proof
        """
        started_at = _utc_now()
        workcell_id = workcell_path.name

        # Determine toolchain
        toolchain = self._route_toolchain(issue)

        # Build and write manifest
        manifest = self._build_manifest(issue, workcell_id, toolchain, speculate_tag)
        manifest_path = workcell_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info(
            "Dispatching to toolchain",
            issue_id=issue.id,
            toolchain=toolchain,
            workcell=workcell_id,
            speculate=speculate_tag,
        )

        # Get adapter
        adapter = self._adapters.get(toolchain)
        if not adapter:
            logger.error("No adapter available", toolchain=toolchain)
            return DispatchResult(
                success=False,
                proof=None,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                error=f"No adapter available for {toolchain}",
                speculate_tag=speculate_tag,
            )

        # Get timeout from config
        tc_config = self.config.toolchains.get(toolchain)
        timeout_seconds = 1800  # default 30 min
        if tc_config:
            timeout_seconds = getattr(tc_config, "timeout_seconds", 1800)

        # Execute via adapter
        try:
            proof = adapter.execute_sync(
                manifest=manifest,
                workcell_path=workcell_path,
                timeout_seconds=timeout_seconds,
            )

            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            success = proof.status in ("success", "partial")

            logger.info(
                "Dispatch completed",
                issue_id=issue.id,
                status=proof.status,
                duration_ms=duration_ms,
            )

            return DispatchResult(
                success=success,
                proof=proof,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                duration_ms=duration_ms,
                speculate_tag=speculate_tag,
            )

        except Exception as e:
            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(
                "Dispatch failed",
                issue_id=issue.id,
                error=str(e),
            )

            return DispatchResult(
                success=False,
                proof=None,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                duration_ms=duration_ms,
                error=str(e),
                speculate_tag=speculate_tag,
            )

    async def dispatch_async(
        self,
        issue: Issue,
        workcell_path: Path,
        speculate_tag: str | None = None,
    ) -> DispatchResult:
        """
        Dispatch a task to a workcell asynchronously.
        """
        started_at = _utc_now()
        workcell_id = workcell_path.name

        # Determine toolchain
        toolchain = self._route_toolchain(issue)

        # Build and write manifest
        manifest = self._build_manifest(issue, workcell_id, toolchain, speculate_tag)
        manifest_path = workcell_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info(
            "Dispatching async to toolchain",
            issue_id=issue.id,
            toolchain=toolchain,
            workcell=workcell_id,
        )

        # Get adapter
        adapter = self._adapters.get(toolchain)
        if not adapter:
            return DispatchResult(
                success=False,
                proof=None,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                error=f"No adapter available for {toolchain}",
                speculate_tag=speculate_tag,
            )

        # Get timeout
        tc_config = self.config.toolchains.get(toolchain)
        timeout_seconds = 1800
        if tc_config:
            timeout_seconds = getattr(tc_config, "timeout_seconds", 1800)

        try:
            proof = await adapter.execute(
                manifest=manifest,
                workcell_path=workcell_path,
                timeout=timedelta(seconds=timeout_seconds),
            )

            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            success = proof.status in ("success", "partial")

            return DispatchResult(
                success=success,
                proof=proof,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                duration_ms=duration_ms,
                speculate_tag=speculate_tag,
            )

        except Exception as e:
            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            return DispatchResult(
                success=False,
                proof=None,
                workcell_id=workcell_id,
                issue_id=issue.id,
                toolchain=toolchain,
                duration_ms=duration_ms,
                error=str(e),
                speculate_tag=speculate_tag,
            )

    async def dispatch_speculate(
        self,
        issue: Issue,
        workcell_paths: list[tuple[str, Path]],
    ) -> SpeculateResult:
        """
        Dispatch multiple parallel workcells for speculate+vote.

        Args:
            issue: The issue to work on
            workcell_paths: List of (speculate_tag, workcell_path) tuples

        Returns:
            SpeculateResult with winner and all candidates
        """
        logger.info(
            "Dispatching speculate+vote",
            issue_id=issue.id,
            parallelism=len(workcell_paths),
        )

        # Launch all dispatches in parallel
        tasks = [self.dispatch_async(issue, path, tag) for tag, path in workcell_paths]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter to successful results
        candidates: list[DispatchResult] = []
        for result in results:
            if isinstance(result, DispatchResult):
                candidates.append(result)
            elif isinstance(result, Exception):
                logger.error("Speculate dispatch failed", error=str(result))

        if not candidates:
            return SpeculateResult(winner=None, candidates=[], all_failed=True)

        # Find winner (first successful with passing gates)
        winner = None
        for candidate in candidates:
            if candidate.success and candidate.proof:
                if candidate.proof.verification.get("all_passed", False):
                    winner = candidate
                    break

        # If no verified winner, take best successful one
        if not winner:
            successful = [c for c in candidates if c.success]
            if successful:
                # Sort by confidence
                successful.sort(
                    key=lambda x: x.proof.confidence if x.proof else 0,
                    reverse=True,
                )
                winner = successful[0]

        return SpeculateResult(
            winner=winner,
            candidates=candidates,
            all_failed=winner is None,
        )

    def apply_patch(self, proof: PatchProof, workcell_path: Path) -> bool:
        """Apply the workcell's patch to main."""
        try:
            branch = proof.patch.get("branch", "")
            if not branch:
                # Get branch from workcell
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=workcell_path,
                    capture_output=True,
                    text=True,
                )
                branch = result.stdout.strip()

            if not branch:
                logger.error("No branch to merge")
                return False

            # Checkout main and merge
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.config.repo_root,
                capture_output=True,
            )

            result = subprocess.run(
                ["git", "merge", branch, "--no-ff", "-m", f"Merge {branch}"],
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error("Failed to merge", error=result.stderr)
                return False

            logger.info("Patch applied", branch=branch)
            return True

        except Exception as e:
            logger.error("Failed to apply patch", error=str(e))
            return False

    def _route_toolchain(self, issue: Issue) -> str:
        """Route issue to appropriate toolchain based on rules."""
        # Check explicit hint from issue
        if issue.dk_tool_hint:
            if issue.dk_tool_hint in self._adapters:
                return issue.dk_tool_hint

        # Use priority order from config, pick first available
        for toolchain in self.config.toolchain_priority:
            if toolchain in self._adapters:
                adapter = self._adapters[toolchain]
                if adapter.available:
                    return toolchain

        # Default to first in priority
        return (
            self.config.toolchain_priority[0]
            if self.config.toolchain_priority
            else "codex"
        )

    def _build_manifest(
        self,
        issue: Issue,
        workcell_id: str,
        toolchain: str,
        speculate_tag: str | None,
    ) -> dict[str, Any]:
        """Build task manifest for workcell."""
        # Get issue tags for routing
        tags = getattr(issue, "tags", []) or []

        # Build quality gates based on issue tags
        quality_gates = self._build_quality_gates(tags)

        return {
            "schema_version": "1.0.0",
            "workcell_id": workcell_id,
            "branch_name": f"wc/{issue.id}/{workcell_id}",
            "issue": {
                "id": issue.id,
                "title": issue.title,
                "description": issue.description,
                "acceptance_criteria": issue.acceptance_criteria or [],
                "context_files": issue.context_files or [],
                "forbidden_paths": issue.dk_forbidden_paths or [],
                "dk_estimated_tokens": issue.dk_estimated_tokens,
                "tags": tags,  # Include tags for gate routing
            },
            "toolchain": toolchain,
            "toolchain_config": {
                "model": self._get_model_for_toolchain(toolchain),
            },
            "quality_gates": quality_gates,
            "speculate_mode": speculate_tag is not None,
            "speculate_tag": speculate_tag,
        }

    def _build_quality_gates(self, tags: list[str]) -> dict[str, Any]:
        """
        Build quality gates configuration based on issue tags.

        Asset-tagged issues get fab-realism gates instead of/in addition to code gates.
        """
        # Default code gates
        gates: dict[str, Any] = {
            "test": self.config.gates.test_command,
            "typecheck": self.config.gates.typecheck_command,
            "lint": self.config.gates.lint_command,
        }

        # Check for asset tags that require fab-realism gate
        asset_tags = [t for t in tags if t.startswith("asset:")]
        gate_tags = [t for t in tags if t.startswith("gate:")]

        if asset_tags or "gate:realism" in gate_tags:
            # Determine asset category from tags
            category = "car"  # Default
            for tag in asset_tags:
                # Extract category from "asset:car", "asset:vehicle", etc.
                parts = tag.split(":")
                if len(parts) >= 2:
                    category = parts[1]
                    break

            # Determine gate config from tags
            gate_config_id = f"{category}_realism_v001"
            for tag in gate_tags:
                if tag.startswith("gate:config:"):
                    gate_config_id = tag.replace("gate:config:", "")
                    break

            # Add fab-realism gate
            gates["fab-realism"] = {
                "type": "fab-realism",
                "category": category,
                "gate_config_id": gate_config_id,
                "command": f"python -m dev_kernel.fab.gate --asset {{asset_path}} --config {gate_config_id} --out {{output_dir}}",
            }

            # Optional engine integration gate (Godot Web export)
            if "gate:godot" in gate_tags or "gate:engine" in gate_tags:
                godot_config_id = "godot_integration_v001"
                for tag in gate_tags:
                    if tag.startswith("gate:godot-config:"):
                        godot_config_id = tag.replace("gate:godot-config:", "")
                        break

                gates["fab-godot"] = {
                    "type": "fab-godot",
                    "gate_config_id": godot_config_id,
                    # Workcell-relative path (works for monorepo tasks)
                    "template_dir": "fab/godot/template",
                }

            # For asset-only issues, disable code gates
            if "gate:asset-only" in gate_tags:
                gates.pop("test", None)
                gates.pop("typecheck", None)
                gates.pop("lint", None)

        return gates

    def _get_model_for_toolchain(self, toolchain: str) -> str:
        """Get the model to use for a toolchain."""
        tc_config = self.config.toolchains.get(toolchain)
        if tc_config:
            model = getattr(tc_config, "model", None)
            if model:
                return model

        # Defaults
        defaults = {
            "codex": "o3",
            "claude": "claude-sonnet-4-20250514",
        }
        return defaults.get(toolchain, "")

    def get_available_toolchains(self) -> list[str]:
        """Get list of available toolchains."""
        return [name for name, adapter in self._adapters.items() if adapter.available]
