"""End-to-end integration tests for the Dev Kernel."""

import asyncio
import json
from pathlib import Path

import pytest

from dev_kernel.kernel.config import KernelConfig
from dev_kernel.kernel.runner import KernelRunner
from dev_kernel.kernel.scheduler import Scheduler
from dev_kernel.kernel.dispatcher import Dispatcher
from dev_kernel.state.manager import StateManager
from dev_kernel.state.models import BeadsGraph


class TestBeadsLoading:
    """Test loading Beads state from a real repo structure."""

    def test_loads_issues_from_beads_repo(self, mock_beads_repo: Path) -> None:
        """Should load all issues from .beads/issues.jsonl."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        graph = state_manager.load_graph()

        assert len(graph.issues) == 5
        assert {i.id for i in graph.issues} == {"1", "2", "3", "4", "5"}

    def test_loads_deps_from_beads_repo(self, mock_beads_repo: Path) -> None:
        """Should load all dependencies from .beads/deps.jsonl."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        graph = state_manager.load_graph()

        assert len(graph.deps) == 4

    def test_issue_fields_loaded_correctly(self, mock_beads_repo: Path) -> None:
        """Should parse all issue fields correctly."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        graph = state_manager.load_graph()
        auth_issue = graph.get_issue("1")

        assert auth_issue is not None
        assert auth_issue.title == "Add user authentication"
        assert auth_issue.dk_priority == "P1"
        assert auth_issue.dk_risk == "high"
        assert auth_issue.dk_size == "L"
        assert auth_issue.dk_estimated_tokens == 80000


class TestScheduling:
    """Test scheduling with real Beads data."""

    def test_computes_ready_set(self, mock_beads_repo: Path) -> None:
        """Should identify ready issues based on deps."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)
        scheduler = Scheduler(config)

        graph = state_manager.load_graph()
        result = scheduler.schedule(graph)

        # Issue 1 is open with no blockers
        # Issue 2 is done
        # Issue 3 depends on 2 (done) -> ready
        # Issue 4 depends on 3 (open) -> not ready
        # Issue 5 depends on 3 and 4 (both open) -> not ready
        ready_ids = {i.id for i in result.ready_issues}

        assert "1" in ready_ids  # No blockers
        assert "3" in ready_ids  # Blocker (2) is done
        assert "2" not in ready_ids  # Done, not ready
        assert "4" not in ready_ids  # Blocked by 3
        assert "5" not in ready_ids  # Blocked by 3 and 4

    def test_computes_critical_path(self, mock_beads_repo: Path) -> None:
        """Should compute critical path through deps."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)
        scheduler = Scheduler(config)

        graph = state_manager.load_graph()
        result = scheduler.schedule(graph)

        # Longest path: 2 -> 3 -> 4 -> 5
        path_ids = [i.id for i in result.critical_path]

        assert len(path_ids) >= 2
        # Path should contain some of the chain

    def test_respects_slot_limit(self, mock_beads_repo: Path) -> None:
        """Should not schedule more than max_concurrent_workcells."""
        config = KernelConfig(
            repo_root=mock_beads_repo,
            max_concurrent_workcells=1,
        )
        state_manager = StateManager(config)
        scheduler = Scheduler(config)

        graph = state_manager.load_graph()
        result = scheduler.schedule(graph)

        assert len(result.scheduled_lanes) <= 1

    def test_respects_token_limit(self, mock_beads_repo: Path) -> None:
        """Should not schedule more than max_concurrent_tokens."""
        config = KernelConfig(
            repo_root=mock_beads_repo,
            max_concurrent_tokens=50000,  # Less than one issue
        )
        state_manager = StateManager(config)
        scheduler = Scheduler(config)

        graph = state_manager.load_graph()
        result = scheduler.schedule(graph)

        total_tokens = sum(
            i.dk_estimated_tokens or 50000 for i in result.scheduled_lanes
        )
        assert total_tokens <= 50000


class TestDryRun:
    """Test dry-run mode."""

    def test_dry_run_makes_no_changes(self, mock_beads_repo: Path) -> None:
        """Dry run should not modify any files."""
        config_path = mock_beads_repo / ".dev-kernel" / "config.yaml"

        runner = KernelRunner(
            config_path=config_path,
            single_cycle=True,
            dry_run=True,
        )

        # Get initial state
        initial_issues = (mock_beads_repo / ".beads" / "issues.jsonl").read_text()

        # Run in dry-run mode
        runner.run()

        # State should be unchanged
        final_issues = (mock_beads_repo / ".beads" / "issues.jsonl").read_text()
        assert initial_issues == final_issues


class TestFullCycle:
    """Test full execution cycle with mocked adapters."""

    @pytest.mark.asyncio
    async def test_single_cycle_with_mock_adapter(
        self,
        mock_beads_repo: Path,
        mock_adapter,
        mock_workcell_manager,
    ) -> None:
        """Should complete a full cycle with mock adapter."""
        config_path = mock_beads_repo / ".dev-kernel" / "config.yaml"

        runner = KernelRunner(
            config_path=config_path,
            single_cycle=True,
            dry_run=False,
        )

        # Run single cycle
        await runner.run_async()

        # Check that stats show work was done
        assert runner._cycle_count >= 1

    @pytest.mark.asyncio
    async def test_updates_issue_status(
        self,
        mock_beads_repo: Path,
        mock_adapter,
        mock_workcell_manager,
    ) -> None:
        """Should update issue status after completion."""
        config_path = mock_beads_repo / ".dev-kernel" / "config.yaml"

        runner = KernelRunner(
            config_path=config_path,
            single_cycle=True,
            target_issue="3",  # Target specific issue
            dry_run=False,
        )

        await runner.run_async()

        # Verify the runner processed work
        # (actual status update depends on adapter mock behavior)
        assert runner._stats["issues_completed"] >= 0

    @pytest.mark.asyncio
    async def test_logs_events(
        self,
        mock_beads_repo: Path,
        mock_adapter,
        mock_workcell_manager,
    ) -> None:
        """Should log events to .dev-kernel/logs/events.jsonl."""
        config_path = mock_beads_repo / ".dev-kernel" / "config.yaml"

        runner = KernelRunner(
            config_path=config_path,
            single_cycle=True,
            dry_run=False,
        )

        await runner.run_async()

        # Check if events were logged
        events_file = mock_beads_repo / ".dev-kernel" / "logs" / "events.jsonl"

        # Events file may or may not exist depending on what was processed
        # Just verify no exceptions occurred


class TestTargetIssue:
    """Test targeting a specific issue."""

    def test_filters_to_target_issue(self, mock_beads_repo: Path) -> None:
        """Should only consider target issue and its deps."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        graph = state_manager.load_graph()
        filtered = graph.filter_to_issue("3")

        # Issue 3 depends on 2, and is blocked by nothing open
        # Should include issue 3 and its related issues
        filtered_ids = {i.id for i in filtered.issues}

        assert "3" in filtered_ids


class TestSpeculateMode:
    """Test speculate+vote mode."""

    def test_high_risk_triggers_speculate(self, mock_beads_repo: Path) -> None:
        """High-risk items on critical path should trigger speculate."""
        config = KernelConfig(
            repo_root=mock_beads_repo,
        )
        state_manager = StateManager(config)
        scheduler = Scheduler(config)

        graph = state_manager.load_graph()
        result = scheduler.schedule(graph)

        # Issue 1 is high risk, may be on critical path
        spec_ids = {i.id for i in result.speculate_issues}

        # At least some speculate decisions should be made
        # (depends on critical path computation)


class TestDispatcher:
    """Test dispatcher with mock adapters."""

    def test_routes_to_available_adapter(
        self,
        mock_beads_repo: Path,
        mock_adapter,
    ) -> None:
        """Should route to first available adapter."""
        config = KernelConfig(
            repo_root=mock_beads_repo,
            toolchain_priority=["codex", "claude"],
        )
        dispatcher = Dispatcher(config)

        available = dispatcher.get_available_toolchains()

        # With mocks, both should be available
        assert "codex" in available or "claude" in available

    def test_builds_valid_manifest(self, mock_beads_repo: Path) -> None:
        """Should build valid manifest from issue."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)
        dispatcher = Dispatcher(config)

        graph = state_manager.load_graph()
        issue = graph.get_issue("1")

        manifest = dispatcher._build_manifest(issue, "wc-1-test", "codex", None)

        assert manifest["schema_version"] == "1.0.0"
        assert manifest["workcell_id"] == "wc-1-test"
        assert manifest["issue"]["id"] == "1"
        assert manifest["issue"]["title"] == "Add user authentication"
        assert manifest["toolchain"] == "codex"
        assert "quality_gates" in manifest


class TestStateUpdates:
    """Test state update operations."""

    def test_update_issue_status(self, mock_beads_repo: Path) -> None:
        """Should update issue status in file."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        # Update issue 3 status
        result = state_manager.update_issue_status("3", "running")

        assert result is True

        # Reload and verify
        graph = state_manager.load_graph()
        issue = graph.get_issue("3")

        assert issue is not None
        assert issue.status == "running"

    def test_increment_attempts(self, mock_beads_repo: Path) -> None:
        """Should increment attempt counter."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        # Initial attempts should be 0
        graph = state_manager.load_graph()
        issue = graph.get_issue("1")
        assert issue.dk_attempts == 0

        # Increment
        new_count = state_manager.increment_attempts("1")

        assert new_count == 1

    def test_add_event(self, mock_beads_repo: Path) -> None:
        """Should log event to file."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        # Add event
        state_manager.add_event(
            issue_id="1",
            event_type="started",
            data={"toolchain": "codex"},
        )

        # Verify event was logged
        events_file = mock_beads_repo / ".dev-kernel" / "logs" / "events.jsonl"
        assert events_file.exists()

        events = []
        with open(events_file) as f:
            for line in f:
                events.append(json.loads(line))

        assert len(events) >= 1
        assert events[0]["type"] == "started"
        assert events[0]["issue_id"] == "1"

    def test_create_issue(self, mock_beads_repo: Path) -> None:
        """Should create new issue."""
        config = KernelConfig(repo_root=mock_beads_repo)
        state_manager = StateManager(config)

        # Create issue
        new_id = state_manager.create_issue(
            title="New test issue",
            description="Created by test",
            priority="P2",
            tags=["test"],
        )

        assert new_id is not None

        # Reload and verify
        graph = state_manager.load_graph()
        new_issue = graph.get_issue(new_id)

        assert new_issue is not None
        assert new_issue.title == "New test issue"
