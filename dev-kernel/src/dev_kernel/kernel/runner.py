"""
Kernel Runner - Main orchestration loop.

Coordinates the full cycle:
1. Load Beads state
2. Schedule ready tasks
3. Dispatch to workcells (parallel)
4. Verify results
5. Write back to Beads
6. Handle failures → create issues
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from dev_kernel.kernel.config import KernelConfig
from dev_kernel.kernel.scheduler import Scheduler, ScheduleResult
from dev_kernel.kernel.dispatcher import Dispatcher, DispatchResult
from dev_kernel.kernel.verifier import Verifier
from dev_kernel.state.manager import StateManager
from dev_kernel.workcell.manager import WorkcellManager

if TYPE_CHECKING:
    from dev_kernel.state.models import Issue

logger = structlog.get_logger()
console = Console()


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class KernelRunner:
    """
    Main kernel orchestration loop.

    Coordinates scheduling, dispatch, verification, and state updates.
    Supports both synchronous (single-threaded) and asynchronous (parallel)
    execution modes.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        config: KernelConfig | None = None,
        single_cycle: bool = False,
        target_issue: str | None = None,
        max_concurrent: int | None = None,
        force_speculate: bool = False,
        dry_run: bool = False,
        watch_mode: bool = False,
    ) -> None:
        # Load or use provided config
        if config:
            self.config = config
        elif config_path:
            self.config = KernelConfig.load(config_path)
        else:
            self.config = KernelConfig()

        # Apply runtime overrides
        self.config.force_speculate = force_speculate
        self.config.dry_run = dry_run
        self.config.watch_mode = watch_mode

        if max_concurrent:
            self.config.max_concurrent_workcells = max_concurrent

        self.single_cycle = single_cycle
        self.target_issue = target_issue

        # Track running tasks
        self._running_tasks: set[str] = set()

        # Initialize components
        self.state_manager = StateManager(self.config)
        self.scheduler = Scheduler(self.config, self._running_tasks)
        self.dispatcher = Dispatcher(self.config)
        self.verifier = Verifier(self.config)
        self.workcell_manager = WorkcellManager(self.config, self.config.repo_root)

        self._running = False
        self._cycle_count = 0
        self._stats = {
            "issues_completed": 0,
            "issues_failed": 0,
            "total_duration_ms": 0,
        }

    def run(self) -> None:
        """Run the kernel loop (synchronous entry point)."""
        asyncio.run(self.run_async())

    async def run_async(self) -> None:
        """Run the kernel loop asynchronously."""
        self._running = True

        console.print("\n[bold blue]Dev Kernel[/bold blue] starting...")
        console.print(f"[dim]Config:[/dim] {self.config.config_path}")
        console.print(f"[dim]Mode:[/dim] {'dry-run' if self.config.dry_run else 'live'}")
        console.print(f"[dim]Max Concurrent:[/dim] {self.config.max_concurrent_workcells}")

        available = self.dispatcher.get_available_toolchains()
        console.print(f"[dim]Toolchains:[/dim] {', '.join(available) if available else 'none'}")

        if self.target_issue:
            console.print(f"[dim]Target:[/dim] Issue #{self.target_issue}")

        console.print()

        try:
            while self._running:
                self._cycle_count += 1
                logger.info("Starting kernel cycle", cycle=self._cycle_count)

                had_work = await self._run_cycle()

                if self.single_cycle:
                    console.print("\n[green]✓[/green] Single cycle complete")
                    break

                if not had_work and not self.config.watch_mode:
                    console.print("\n[green]✓[/green] No more ready work")
                    break

                if self.config.watch_mode:
                    console.print("[dim]Waiting for Beads changes...[/dim]")
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            self._running = False

        self._display_summary()

    async def _run_cycle(self) -> bool:
        """
        Execute one scheduling cycle.

        Returns True if work was dispatched.
        """
        # Load current state
        graph = self.state_manager.load_beads_graph()

        if not graph.issues:
            console.print("[yellow]No issues found in Beads[/yellow]")
            return False

        # Filter to target issue if specified
        if self.target_issue:
            graph = graph.filter_to_issue(self.target_issue)
            if not graph.issues:
                console.print(f"[yellow]Issue #{self.target_issue} not found[/yellow]")
                return False

        # Update scheduler with current running tasks
        self.scheduler.update_running_tasks(self._running_tasks)

        # Schedule
        schedule = self.scheduler.schedule(graph)

        if not schedule.scheduled_lanes:
            console.print("[dim]Nothing ready to schedule[/dim]")
            return False

        # Display schedule
        self._display_schedule(schedule)

        if self.config.dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            return True

        # Dispatch work in parallel
        await self._dispatch_parallel(schedule)

        return True

    async def _dispatch_parallel(self, schedule: ScheduleResult) -> None:
        """Dispatch all scheduled work in parallel."""
        spec_ids = {i.id for i in schedule.speculate_issues}

        # Separate speculate vs single dispatch
        speculate_issues = [i for i in schedule.scheduled_lanes if i.id in spec_ids]
        single_issues = [i for i in schedule.scheduled_lanes if i.id not in spec_ids]

        # Create tasks for all dispatches
        tasks = []

        for issue in single_issues:
            tasks.append(self._dispatch_single_async(issue))

        for issue in speculate_issues:
            tasks.append(self._dispatch_speculate_async(issue))

        # Run all in parallel
        if tasks:
            console.print(f"\n[cyan]Dispatching {len(tasks)} task(s) in parallel...[/cyan]")
            await asyncio.gather(*tasks)

    async def _dispatch_single_async(self, issue: Issue) -> None:
        """Dispatch a single workcell for an issue asynchronously."""
        console.print(f"\n[cyan]Dispatching[/cyan] #{issue.id}: {issue.title}")

        # Track as running
        self._running_tasks.add(issue.id)

        try:
            # Create workcell
            workcell_path = self.workcell_manager.create(issue.id)

            # Update issue status
            self.state_manager.update_issue_status(issue.id, "running")

            # Run toolchain via async dispatch
            result = await self.dispatcher.dispatch_async(issue, workcell_path)

            if result.success and result.proof:
                # Verify
                verified = self.verifier.verify(result.proof, workcell_path)

                if verified:
                    await self._handle_success(issue, result, workcell_path)
                else:
                    await self._handle_failure(issue, result, workcell_path)
            else:
                await self._handle_failure(issue, result, workcell_path)

        finally:
            self._running_tasks.discard(issue.id)

    async def _dispatch_speculate_async(self, issue: Issue) -> None:
        """Dispatch multiple parallel workcells for speculate+vote."""
        from dev_kernel.kernel.routing import speculate_parallelism, speculate_toolchains

        # Determine which toolchains to run in parallel for this issue.
        candidates = speculate_toolchains(self.config, issue)
        if not candidates:
            candidates = list(self.config.toolchain_priority)

        available = set(self.dispatcher.get_available_toolchains())
        candidates = [c for c in candidates if c in available]

        if not candidates:
            console.print("  [red]No available toolchains for speculate[/red]")
            return

        desired_parallelism = speculate_parallelism(self.config, issue)
        parallelism = min(desired_parallelism, len(candidates)) or 1
        candidates = candidates[:parallelism]
        console.print(
            f"\n[magenta]Speculate[/magenta] #{issue.id}: {issue.title} "
            f"(×{parallelism}: {', '.join(candidates)})"
        )

        # Track as running
        self._running_tasks.add(issue.id)

        try:
            # Create one workcell per candidate toolchain.
            workcells: list[tuple[str, str, Path]] = []
            for toolchain in candidates:
                tag = f"spec-{toolchain}"
                path = self.workcell_manager.create(issue.id, speculate_tag=tag)
                workcells.append((toolchain, tag, path))

            # Update issue status
            self.state_manager.update_issue_status(issue.id, "running")

            # Dispatch all candidates in parallel (one per toolchain).
            dispatch_tasks = [
                self.dispatcher.dispatch_async(
                    issue,
                    path,
                    speculate_tag=tag,
                    toolchain_override=toolchain,
                )
                for toolchain, tag, path in workcells
            ]
            results = await asyncio.gather(*dispatch_tasks)

            workcell_by_id = {path.name: path for _, _, path in workcells}

            # Verify all candidates before voting.
            for r in results:
                if r.proof:
                    path = workcell_by_id.get(r.workcell_id)
                    if path:
                        self.verifier.verify(r.proof, path)

            proofs = [r.proof for r in results if r.proof]
            winner_proof = self.verifier.vote(proofs) if proofs else None

            winner_result: DispatchResult | None = None
            winner_path: Path | None = None

            if winner_proof:
                for r in results:
                    if r.proof and r.proof.workcell_id == winner_proof.workcell_id:
                        winner_result = r
                        winner_path = workcell_by_id.get(r.workcell_id)
                        break

            # Fallback if vote didn't return a winner (e.g., all failed gates).
            if not winner_result:
                passing = [
                    r
                    for r in results
                    if r.proof
                    and isinstance(r.proof.verification, dict)
                    and r.proof.verification.get("all_passed", False)
                ]
                if passing:
                    passing.sort(
                        key=lambda x: x.proof.confidence if x.proof else 0,
                        reverse=True,
                    )
                    winner_result = passing[0]
                    winner_path = workcell_by_id.get(winner_result.workcell_id)
                else:
                    successful = [r for r in results if r.success and r.proof]
                    if successful:
                        successful.sort(
                            key=lambda x: x.proof.confidence if x.proof else 0,
                            reverse=True,
                        )
                        winner_result = successful[0]
                        winner_path = workcell_by_id.get(winner_result.workcell_id)

            # If still no winner, fail the issue using the first candidate (best-effort).
            if not winner_result or not winner_path:
                fallback_path = workcells[0][2]
                await self._handle_failure(issue, results[0] if results else None, fallback_path)
                for _, _, path in workcells[1:]:
                    self.workcell_manager.cleanup(path, keep_logs=False)
                return

            verified = (
                bool(winner_result.proof)
                and isinstance(winner_result.proof.verification, dict)
                and winner_result.proof.verification.get("all_passed", False)
            )

            if verified:
                await self._handle_success(issue, winner_result, winner_path)
            else:
                await self._handle_failure(issue, winner_result, winner_path)

            # Cleanup non-winners (keep logs only for the chosen candidate).
            for _, _, path in workcells:
                if path.name == winner_path.name:
                    continue
                self.workcell_manager.cleanup(path, keep_logs=False)

        finally:
            self._running_tasks.discard(issue.id)

    async def _handle_success(
        self,
        issue: Issue,
        result: DispatchResult,
        workcell_path: Path,
    ) -> None:
        """Handle successful workcell completion."""
        console.print(f"  [green]✓[/green] #{issue.id} completed")

        self._stats["issues_completed"] += 1
        self._stats["total_duration_ms"] += result.duration_ms

        if result.proof:
            # Apply patch (merge to main)
            self.dispatcher.apply_patch(result.proof, workcell_path)

        # Update Beads
        self.state_manager.update_issue_status(issue.id, "done")

        # Log event
        self.state_manager.add_event(
            issue.id,
            "completed",
            {
                "toolchain": result.toolchain,
                "duration_ms": result.duration_ms,
                "speculate_tag": result.speculate_tag,
            },
        )

        # Cleanup workcell
        self.workcell_manager.cleanup(workcell_path, keep_logs=True)

    async def _handle_failure(
        self,
        issue: Issue,
        result: DispatchResult | None,
        workcell_path: Path,
    ) -> None:
        """Handle workcell failure."""
        console.print(f"  [red]✗[/red] #{issue.id} failed")

        self._stats["issues_failed"] += 1
        if result:
            self._stats["total_duration_ms"] += result.duration_ms

        # Update attempts
        current_attempts = self.state_manager.increment_attempts(issue.id)

        # Prefer verification context over generic dispatch errors.
        error_summary = None
        if result and result.error:
            error_summary = result.error
        elif result and result.proof and isinstance(result.proof.verification, dict):
            blocking = result.proof.verification.get("blocking_failures") or []
            if blocking:
                error_summary = f"Gate failures: {', '.join(blocking)}"

        # Log event
        self.state_manager.add_event(
            issue.id,
            "failed",
            {
                "toolchain": result.toolchain if result else "unknown",
                "error": error_summary or "Unknown error",
                "attempt": current_attempts,
            },
        )

        # If this is an asset issue and fab-* gates provided repair hints, persist them back
        # onto the issue description so the next attempt has concrete guidance.
        if result:
            self._maybe_update_issue_with_repair_hints(issue, result, current_attempts)

        # Check if should escalate
        if current_attempts >= issue.dk_max_attempts:
            self.state_manager.update_issue_status(issue.id, "escalated")
            console.print(f"  [yellow]⚠[/yellow] #{issue.id} escalated (max attempts reached)")

            # Create escalation issue
            self._create_escalation_issue(issue, result, error_summary)
        else:
            # Re-queue for another attempt; the scheduler already enforces max attempts.
            self.state_manager.update_issue_status(issue.id, "ready")
            console.print(f"  [dim]Attempt {current_attempts}/{issue.dk_max_attempts}[/dim]")

        # Cleanup workcell (keep logs for debugging)
        self.workcell_manager.cleanup(workcell_path, keep_logs=True)

    def _maybe_update_issue_with_repair_hints(
        self,
        issue: Issue,
        result: DispatchResult,
        attempt: int,
    ) -> None:
        """Write the latest fab gate repair hints back to the issue description."""
        if not any(t.startswith("asset:") for t in (issue.tags or [])):
            return

        if not result.proof or not isinstance(result.proof.verification, dict):
            return

        gates = result.proof.verification.get("gates")
        if not isinstance(gates, dict):
            return

        failing_with_actions: list[tuple[str, list[dict[str, Any]]]] = []
        for gate_name, gate_result in gates.items():
            if not isinstance(gate_result, dict):
                continue
            if gate_result.get("passed") is True:
                continue
            actions = gate_result.get("next_actions")
            if isinstance(actions, list) and actions:
                typed_actions = [a for a in actions if isinstance(a, dict)]
                if typed_actions:
                    failing_with_actions.append((str(gate_name), typed_actions))

        if not failing_with_actions:
            return

        start_marker = "<!-- DEV_KERNEL_AUTOGEN_REPAIR -->"
        end_marker = "<!-- /DEV_KERNEL_AUTOGEN_REPAIR -->"

        base = (issue.description or "").strip()
        if start_marker in base and end_marker in base:
            start = base.find(start_marker)
            end = base.find(end_marker, start)
            if end != -1:
                base = (base[:start] + base[end + len(end_marker) :]).strip()

        lines: list[str] = []
        lines.append(start_marker)
        lines.append(f"## Kernel Repair Hints (Attempt {attempt})")
        lines.append(
            "These instructions were generated from the most recent failed fab gate run."
        )
        lines.append("")

        for gate_name, actions in failing_with_actions:
            lines.append(f"### {gate_name}")
            for action in actions[:12]:
                priority = action.get("priority", 3)
                fail_code = action.get("fail_code", "UNKNOWN")
                instructions = str(action.get("instructions", "")).strip()
                if not instructions:
                    instructions = f"Fix {fail_code}"
                lines.append(f"- [P{priority}] `{fail_code}`: {instructions}")
            lines.append("")

        lines.append(end_marker)

        new_description = (base + "\n\n" + "\n".join(lines)).strip()
        try:
            self.state_manager.update_issue(issue.id, description=new_description)
        except Exception as e:
            logger.warning("Failed to update issue with repair hints", issue_id=issue.id, error=str(e))

    def _create_escalation_issue(
        self,
        original_issue: Issue,
        result: DispatchResult | None,
        error_summary: str | None = None,
    ) -> None:
        """Create a new issue for human review after escalation."""
        error = error_summary or (result.error if result else None) or "Unknown error after max attempts"

        title = f"[ESCALATION] {original_issue.title}"
        description = (
            f"Automated processing failed after {original_issue.dk_max_attempts} attempts.\n\n"
            f"## Original Issue #{original_issue.id}\n"
            f"{original_issue.description or '(no description)'}\n\n"
            f"## Failure Details\n{error}\n\n"
            f"## Action Required\nManual review and intervention needed."
        )
        tags = sorted(set((original_issue.tags or []) + ["escalation", "needs-human"]))

        try:
            new_issue_id = self.state_manager.create_issue(
                title=title,
                description=description,
                priority=original_issue.dk_priority or "P2",
                tags=tags,
            )

            if new_issue_id:
                self.state_manager.update_issue(
                    new_issue_id,
                    dk_parent=original_issue.id,
                )
                console.print(f"  [dim]Created escalation issue #{new_issue_id}[/dim]")
        except Exception as e:
            logger.error("Failed to create escalation issue", error=str(e))

    def _display_schedule(self, schedule: ScheduleResult) -> None:
        """Display the scheduling plan."""
        table = Table(title=f"Scheduled Work (Cycle {self._cycle_count})")
        table.add_column("Issue", style="cyan")
        table.add_column("Title")
        table.add_column("Priority")
        table.add_column("Risk")
        table.add_column("Mode")

        spec_ids = {i.id for i in schedule.speculate_issues}

        for issue in schedule.scheduled_lanes:
            mode = "[magenta]speculate[/magenta]" if issue.id in spec_ids else "single"
            table.add_row(
                f"#{issue.id}",
                issue.title[:40] + ("..." if len(issue.title) > 40 else ""),
                issue.dk_priority or "P2",
                issue.dk_risk or "medium",
                mode,
            )

        console.print(table)

        if schedule.skipped_issues:
            console.print(
                f"[dim]Skipped {len(schedule.skipped_issues)} issues "
                f"(slots/tokens)[/dim]"
            )

    def _display_summary(self) -> None:
        """Display run summary."""
        if self._stats["issues_completed"] > 0 or self._stats["issues_failed"] > 0:
            console.print("\n")
            summary = Panel(
                f"[green]Completed:[/green] {self._stats['issues_completed']}  "
                f"[red]Failed:[/red] {self._stats['issues_failed']}  "
                f"[dim]Cycles:[/dim] {self._cycle_count}  "
                f"[dim]Total Time:[/dim] {self._stats['total_duration_ms'] / 1000:.1f}s",
                title="Run Summary",
            )
            console.print(summary)

    def stop(self) -> None:
        """Stop the kernel loop."""
        self._running = False
