"""
Scheduler - Computes ready set, critical path, and lane packing.

Responsibilities:
- Compute which issues are ready to work on
- Find the critical path through the dependency graph
- Pack ready issues into parallel execution lanes
- Trigger speculate+vote mode for high-risk tasks
- Prevent starvation of long-waiting tasks
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dev_kernel.state.models import Issue, BeadsGraph
    from dev_kernel.kernel.config import KernelConfig


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# Size to hours mapping for critical path calculation
SIZE_TO_HOURS = {"XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16}


@dataclass
class ScheduleResult:
    """Result of a scheduling cycle."""

    ready_issues: list[Issue]
    critical_path: list[Issue]
    scheduled_lanes: list[Issue]
    speculate_issues: list[Issue]
    skipped_issues: list[Issue] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def total_estimated_tokens(self) -> int:
        """Total estimated tokens for scheduled work."""
        return sum(i.dk_estimated_tokens or 50000 for i in self.scheduled_lanes)

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Ready: {len(self.ready_issues)}, "
            f"Scheduled: {len(self.scheduled_lanes)}, "
            f"Speculate: {len(self.speculate_issues)}, "
            f"Tokens: {self.total_estimated_tokens:,}"
        )


class Scheduler:
    """
    Computes ready set, critical path, and lane packing.

    The scheduler implements a priority-based algorithm that:
    1. Finds all issues with satisfied dependencies
    2. Computes critical path through the dependency graph
    3. Prioritizes critical path items
    4. Packs into parallel lanes respecting resource constraints
    5. Identifies candidates for speculate+vote mode
    """

    def __init__(self, config: KernelConfig, running_tasks: set[str] | None = None) -> None:
        self.config = config
        self.running_tasks = running_tasks or set()

    def schedule(self, graph: BeadsGraph) -> ScheduleResult:
        """
        Run a full scheduling cycle.

        Returns ready issues, critical path, and scheduled lanes.
        """
        ready_set = self.compute_ready_set(graph)
        critical_path = self.compute_critical_path(graph)
        ready_set = self.prevent_starvation(ready_set)
        scheduled, skipped, reasons = self.pack_lanes(ready_set, critical_path)
        speculate = [i for i in scheduled if self.should_speculate(i, critical_path)]

        return ScheduleResult(
            ready_issues=ready_set,
            critical_path=critical_path,
            scheduled_lanes=scheduled,
            speculate_issues=speculate,
            skipped_issues=skipped,
            reasons=reasons,
        )

    def compute_ready_set(self, graph: BeadsGraph) -> list[Issue]:
        """
        Compute which issues are ready to work on.

        An issue is ready if:
        1. status == 'open' or status == 'ready'
        2. All blocking deps have status == 'done'
        3. Not currently running in any workcell
        4. attempts < max_attempts
        """
        ready: list[Issue] = []

        for issue in graph.issues:
            # Check status
            if issue.status not in ("open", "ready"):
                continue

            # Check if already running
            if issue.id in self.running_tasks:
                continue

            # Check attempts
            if issue.dk_attempts >= issue.dk_max_attempts:
                continue

            # Check blocking deps
            blockers = graph.get_blocking_deps(issue.id)
            if all(b.status == "done" for b in blockers):
                ready.append(issue)

        return ready

    def compute_critical_path(self, graph: BeadsGraph) -> list[Issue]:
        """
        Compute the critical path through the dependency graph.

        Critical path = longest chain weighted by estimated effort.
        Uses topological sort + dynamic programming.
        """
        if not graph.issues:
            return []

        # Build adjacency list (A blocks B means edge A→B)
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        issue_map = {i.id: i for i in graph.issues}

        for issue in graph.issues:
            # Find all issues that this issue blocks
            for dep in graph.deps:
                if dep.from_id == issue.id and dep.dep_type == "blocks":
                    adj[issue.id].append(dep.to_id)
                    in_degree[dep.to_id] += 1

        # Initialize in_degree for all issues
        for issue in graph.issues:
            if issue.id not in in_degree:
                in_degree[issue.id] = 0

        # Topological sort using Kahn's algorithm
        queue = deque([i for i in graph.issues if in_degree[i.id] == 0])
        topo_order: list[Issue] = []

        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for neighbor_id in adj[node.id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    neighbor = issue_map.get(neighbor_id)
                    if neighbor:
                        queue.append(neighbor)

        if not topo_order:
            return []

        # DP: longest path ending at each node
        dist = {i.id: SIZE_TO_HOURS.get(i.dk_size, 4) for i in graph.issues}
        parent: dict[str, str | None] = {i.id: None for i in graph.issues}

        for node in topo_order:
            for neighbor_id in adj[node.id]:
                neighbor = issue_map.get(neighbor_id)
                if neighbor:
                    new_dist = dist[node.id] + SIZE_TO_HOURS.get(neighbor.dk_size, 4)
                    if new_dist > dist[neighbor_id]:
                        dist[neighbor_id] = new_dist
                        parent[neighbor_id] = node.id

        # Backtrack from max
        end_id: str = max(dist, key=lambda x: dist[x])
        path: list[Issue] = []

        current: str | None = end_id
        while current:
            issue = issue_map.get(current)
            if issue:
                path.append(issue)
            current = parent.get(current)

        return list(reversed(path))

    def pack_lanes(
        self,
        ready_set: list[Issue],
        critical_path: list[Issue],
    ) -> tuple[list[Issue], list[Issue], dict[str, str]]:
        """
        Pack ready issues into parallel lanes respecting:
        - max_concurrent_workcells
        - max_concurrent_tokens
        - Critical path priority

        Returns (scheduled, skipped, reasons)
        """
        lanes: list[Issue] = []
        skipped: list[Issue] = []
        reasons: dict[str, str] = {}

        remaining_slots = self.config.max_concurrent_workcells
        remaining_tokens = self.config.max_concurrent_tokens

        # Priority 1: Critical path items that are ready
        cp_ids = {i.id for i in critical_path}
        cp_ready = [i for i in ready_set if i.id in cp_ids]

        # Priority 2: High priority items (sorted by priority, then risk)
        other_ready = sorted(
            [i for i in ready_set if i.id not in cp_ids],
            key=lambda x: (
                x.dk_priority or "P2",
                -{"low": 0, "medium": 1, "high": 2, "critical": 3}.get(x.dk_risk, 1),
            ),
        )

        # Pack into lanes (critical path first, then others)
        for issue in cp_ready + other_ready:
            est_tokens = issue.dk_estimated_tokens or 50000

            # Check slot availability
            if remaining_slots <= 0:
                skipped.append(issue)
                reasons[issue.id] = "no_slots"
                continue

            # Check token budget
            if remaining_tokens < est_tokens:
                skipped.append(issue)
                reasons[issue.id] = "token_limit"
                continue

            # Schedule this issue
            lanes.append(issue)
            remaining_slots -= 1
            remaining_tokens -= est_tokens

            # If speculate mode, reserve additional slots for parallel attempts
            if issue.dk_speculate and self.config.speculation.enabled:
                extra_slots = min(
                    self.config.speculation.default_parallelism - 1,
                    remaining_slots,
                )
                for _ in range(extra_slots):
                    if remaining_slots > 0 and remaining_tokens >= est_tokens:
                        remaining_slots -= 1
                        remaining_tokens -= est_tokens

        return lanes, skipped, reasons

    def should_speculate(self, issue: Issue, critical_path: list[Issue]) -> bool:
        """
        Determine if an issue should use speculate+vote mode.

        Triggered when:
        1. Issue has dk_speculate: true
        2. Issue is on critical path AND has dk_risk >= 'high'
        3. Config has force_speculate enabled
        """
        if not self.config.speculation.enabled:
            return False

        # Explicit speculate flag
        if issue.dk_speculate:
            return True

        # Force speculate mode
        if self.config.force_speculate:
            return True

        # Auto-trigger for high-risk critical path items
        if self.config.speculation.auto_trigger_on_critical_path:
            cp_ids = {i.id for i in critical_path}
            if issue.id in cp_ids:
                if issue.dk_risk in self.config.speculation.auto_trigger_risk_levels:
                    return True

        return False

    def prevent_starvation(self, ready_set: list[Issue]) -> list[Issue]:
        """
        Boost priority of issues that have been ready but unscheduled for too long.

        This prevents lower-priority issues from being starved indefinitely.
        """
        now = _utc_now()

        for issue in ready_set:
            if issue.ready_since:
                # Handle timezone-aware vs naive datetimes
                ready_since = issue.ready_since
                if ready_since.tzinfo is None:
                    # Assume UTC if naive
                    ready_since = ready_since.replace(tzinfo=timezone.utc)

                wait_hours = (now - ready_since).total_seconds() / 3600

                # After threshold hours waiting, boost priority
                if wait_hours > self.config.starvation_threshold_hours:
                    if issue.dk_priority and issue.dk_priority.startswith("P"):
                        try:
                            current = int(issue.dk_priority[1])
                            issue.dk_priority = f"P{max(0, current - 1)}"
                        except ValueError:
                            pass

                # After 24 hours, force to front
                if wait_hours > 24:
                    issue.dk_priority = "P0"
                    issue.dk_starved = True

        return sorted(
            ready_set,
            key=lambda x: (x.dk_priority or "P2", not getattr(x, "dk_starved", False)),
        )

    def update_running_tasks(self, task_ids: set[str]) -> None:
        """Update the set of currently running task IDs."""
        self.running_tasks = task_ids
