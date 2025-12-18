"""Tests for the Scheduler."""

from datetime import datetime, timezone, timedelta

import pytest

from dev_kernel.kernel.scheduler import Scheduler, ScheduleResult, SIZE_TO_HOURS
from dev_kernel.kernel.config import KernelConfig, SpeculationConfig
from dev_kernel.state.models import Issue, Dep, BeadsGraph


def _now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def make_issue(
    id: str,
    status: str = "open",
    priority: str = "P2",
    risk: str = "medium",
    size: str = "M",
    speculate: bool = False,
) -> Issue:
    """Helper to create test issues."""
    now = _now()
    return Issue(
        id=id,
        title=f"Issue {id}",
        description=f"Test issue {id}",
        status=status,
        created=now,
        updated=now,
        dk_priority=priority,
        dk_risk=risk,
        dk_size=size,
        dk_speculate=speculate,
        dk_attempts=0,
        dk_max_attempts=3,
    )


def make_dep(from_id: str, to_id: str, dep_type: str = "blocks") -> Dep:
    """Helper to create test deps."""
    return Dep(from_id=from_id, to_id=to_id, dep_type=dep_type, created=_now())


@pytest.fixture
def config() -> KernelConfig:
    """Default config for tests."""
    return KernelConfig(
        max_concurrent_workcells=3,
        max_concurrent_tokens=200_000,
        starvation_threshold_hours=4.0,
        speculation=SpeculationConfig(
            enabled=True,
            default_parallelism=2,
            auto_trigger_on_critical_path=True,
            auto_trigger_risk_levels=["high", "critical"],
        ),
    )


class TestComputeReadySet:
    """Tests for compute_ready_set."""

    def test_finds_open_issues_with_no_deps(self, config: KernelConfig) -> None:
        """Open issues with no deps are ready."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="open"),
                make_issue("2", status="open"),
            ],
            deps=[],
        )

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 2
        assert {i.id for i in ready} == {"1", "2"}

    def test_excludes_done_issues(self, config: KernelConfig) -> None:
        """Done issues are not ready."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="done"),
                make_issue("2", status="open"),
            ],
            deps=[],
        )

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 1
        assert ready[0].id == "2"

    def test_respects_blocking_deps(self, config: KernelConfig) -> None:
        """Issues with pending blockers are not ready."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="open"),
                make_issue("2", status="open"),
            ],
            deps=[make_dep("1", "2", "blocks")],
        )

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 1
        assert ready[0].id == "1"

    def test_ready_when_blockers_done(self, config: KernelConfig) -> None:
        """Issues become ready when blockers are done."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="done"),
                make_issue("2", status="open"),
            ],
            deps=[make_dep("1", "2", "blocks")],
        )

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 1
        assert ready[0].id == "2"

    def test_excludes_running_tasks(self, config: KernelConfig) -> None:
        """Issues already running are excluded."""
        scheduler = Scheduler(config, running_tasks={"1"})
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="open"),
                make_issue("2", status="open"),
            ],
            deps=[],
        )

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 1
        assert ready[0].id == "2"

    def test_excludes_max_attempts_reached(self, config: KernelConfig) -> None:
        """Issues at max attempts are excluded."""
        scheduler = Scheduler(config)
        issue = make_issue("1", status="open")
        issue.dk_attempts = 3

        graph = BeadsGraph(issues=[issue], deps=[])

        ready = scheduler.compute_ready_set(graph)

        assert len(ready) == 0


class TestComputeCriticalPath:
    """Tests for compute_critical_path."""

    def test_single_issue(self, config: KernelConfig) -> None:
        """Single issue is its own critical path."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(issues=[make_issue("1")], deps=[])

        path = scheduler.compute_critical_path(graph)

        assert len(path) == 1
        assert path[0].id == "1"

    def test_linear_chain(self, config: KernelConfig) -> None:
        """Linear chain returns full path."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[make_issue("1"), make_issue("2"), make_issue("3")],
            deps=[
                make_dep("1", "2", "blocks"),
                make_dep("2", "3", "blocks"),
            ],
        )

        path = scheduler.compute_critical_path(graph)

        assert len(path) == 3
        assert [p.id for p in path] == ["1", "2", "3"]

    def test_chooses_longest_path(self, config: KernelConfig) -> None:
        """Selects longest path when multiple exist."""
        scheduler = Scheduler(config)
        # Path 1: 1 -> 2 (2 issues)
        # Path 2: 3 -> 4 -> 5 (3 issues)
        graph = BeadsGraph(
            issues=[
                make_issue("1"),
                make_issue("2"),
                make_issue("3"),
                make_issue("4"),
                make_issue("5"),
            ],
            deps=[
                make_dep("1", "2", "blocks"),
                make_dep("3", "4", "blocks"),
                make_dep("4", "5", "blocks"),
            ],
        )

        path = scheduler.compute_critical_path(graph)

        assert len(path) == 3
        assert [p.id for p in path] == ["3", "4", "5"]

    def test_weights_by_size(self, config: KernelConfig) -> None:
        """Path weight considers issue size."""
        scheduler = Scheduler(config)
        # Path 1: 1 (XL=16) -> 2 (XS=1) = 17
        # Path 2: 3 (S=2) -> 4 (S=2) -> 5 (S=2) = 6
        graph = BeadsGraph(
            issues=[
                make_issue("1", size="XL"),
                make_issue("2", size="XS"),
                make_issue("3", size="S"),
                make_issue("4", size="S"),
                make_issue("5", size="S"),
            ],
            deps=[
                make_dep("1", "2", "blocks"),
                make_dep("3", "4", "blocks"),
                make_dep("4", "5", "blocks"),
            ],
        )

        path = scheduler.compute_critical_path(graph)

        # Path 1 should be selected as 17 > 6
        assert [p.id for p in path] == ["1", "2"]


class TestPackLanes:
    """Tests for pack_lanes."""

    def test_respects_slot_limit(self, config: KernelConfig) -> None:
        """Should not exceed max_concurrent_workcells."""
        config.max_concurrent_workcells = 2
        scheduler = Scheduler(config)

        issues = [make_issue(str(i)) for i in range(5)]
        graph = BeadsGraph(issues=issues, deps=[])

        scheduled, skipped, reasons = scheduler.pack_lanes(issues, [])

        assert len(scheduled) == 2
        assert len(skipped) == 3
        assert all(reasons[i.id] == "no_slots" for i in skipped)

    def test_respects_token_limit(self, config: KernelConfig) -> None:
        """Should not exceed max_concurrent_tokens."""
        config.max_concurrent_tokens = 100_000
        scheduler = Scheduler(config)

        issues = [make_issue(str(i)) for i in range(5)]
        for issue in issues:
            issue.dk_estimated_tokens = 40_000

        graph = BeadsGraph(issues=issues, deps=[])

        scheduled, skipped, reasons = scheduler.pack_lanes(issues, [])

        assert len(scheduled) == 2  # 2 * 40k = 80k < 100k
        assert len(skipped) == 3

    def test_prioritizes_critical_path(self, config: KernelConfig) -> None:
        """Critical path items are scheduled first."""
        scheduler = Scheduler(config)

        issues = [
            make_issue("1", priority="P3"),
            make_issue("2", priority="P3"),
            make_issue("3", priority="P3"),
        ]
        critical_path = [issues[2]]  # Issue 3 is on critical path

        config.max_concurrent_workcells = 1

        scheduled, _, _ = scheduler.pack_lanes(issues, critical_path)

        assert scheduled[0].id == "3"  # Critical path first


class TestShouldSpeculate:
    """Tests for should_speculate."""

    def test_explicit_speculate_flag(self, config: KernelConfig) -> None:
        """Returns True if dk_speculate is True."""
        scheduler = Scheduler(config)
        issue = make_issue("1", speculate=True)

        assert scheduler.should_speculate(issue, []) is True

    def test_force_speculate_config(self, config: KernelConfig) -> None:
        """Returns True if config.force_speculate is True."""
        config.force_speculate = True
        scheduler = Scheduler(config)
        issue = make_issue("1")

        assert scheduler.should_speculate(issue, []) is True

    def test_high_risk_on_critical_path(self, config: KernelConfig) -> None:
        """Returns True for high-risk items on critical path."""
        scheduler = Scheduler(config)
        issue = make_issue("1", risk="high")

        assert scheduler.should_speculate(issue, [issue]) is True

    def test_low_risk_not_speculate(self, config: KernelConfig) -> None:
        """Returns False for low-risk items."""
        scheduler = Scheduler(config)
        issue = make_issue("1", risk="low")

        assert scheduler.should_speculate(issue, [issue]) is False

    def test_disabled_speculation(self, config: KernelConfig) -> None:
        """Returns False if speculation is disabled."""
        config.speculation.enabled = False
        scheduler = Scheduler(config)
        issue = make_issue("1", speculate=True)

        assert scheduler.should_speculate(issue, []) is False


class TestSchedule:
    """Tests for the full schedule() method."""

    def test_full_cycle(self, config: KernelConfig) -> None:
        """Complete scheduling cycle works."""
        scheduler = Scheduler(config)
        graph = BeadsGraph(
            issues=[
                make_issue("1", status="open", priority="P1"),
                make_issue("2", status="open", priority="P2"),
                make_issue("3", status="done"),
            ],
            deps=[make_dep("3", "1", "blocks")],
        )

        result = scheduler.schedule(graph)

        assert isinstance(result, ScheduleResult)
        assert len(result.ready_issues) == 2
        assert len(result.scheduled_lanes) <= config.max_concurrent_workcells

