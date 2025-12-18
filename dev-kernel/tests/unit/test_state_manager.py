"""Tests for StateManager."""

from pathlib import Path

import pytest

from dev_kernel.state.manager import StateManager
from dev_kernel.state.models import BeadsGraph, Issue


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def beads_dir(fixtures_dir: Path) -> Path:
    """Path to test Beads directory."""
    return fixtures_dir / "beads"


@pytest.fixture
def state_manager(beads_dir: Path, tmp_path: Path) -> StateManager:
    """Create StateManager with test fixtures."""
    # Copy fixtures to tmp_path
    import shutil

    tmp_beads = tmp_path / ".beads"
    shutil.copytree(beads_dir, tmp_beads)

    return StateManager(repo_root=tmp_path)


class TestLoadGraph:
    """Tests for load_graph method."""

    def test_loads_issues_from_jsonl(self, state_manager: StateManager) -> None:
        """Should load issues from issues.jsonl."""
        graph = state_manager.load_graph()

        assert len(graph.issues) == 8
        assert graph.get_issue("1") is not None
        assert graph.get_issue("2") is not None

    def test_loads_deps_from_jsonl(self, state_manager: StateManager) -> None:
        """Should load dependencies from deps.jsonl."""
        graph = state_manager.load_graph()

        assert len(graph.deps) == 4

    def test_issue_fields_parsed_correctly(self, state_manager: StateManager) -> None:
        """Should parse all issue fields correctly."""
        graph = state_manager.load_graph()
        issue = graph.get_issue("2")

        assert issue is not None
        assert issue.id == "2"
        assert issue.title == "Implement user authentication"
        assert issue.status == "ready"
        assert issue.dk_priority == "P1"
        assert issue.dk_risk == "high"
        assert issue.dk_size == "L"
        assert issue.dk_speculate is True
        assert "src/auth/" in (issue.context_files or [])
        assert "src/auth/secrets.ts" in issue.dk_forbidden_paths


class TestGetBlockingDeps:
    """Tests for dependency resolution."""

    def test_finds_blocking_issues(self, state_manager: StateManager) -> None:
        """Should find issues that block another issue."""
        graph = state_manager.load_graph()

        # Issue 2 is blocked by issue 1
        blockers = graph.get_blocking_deps("2")
        assert len(blockers) == 1
        assert blockers[0].id == "1"

    def test_finds_blocked_issues(self, state_manager: StateManager) -> None:
        """Should find issues blocked by an issue."""
        graph = state_manager.load_graph()

        # Issue 2 blocks issues 3 and 5
        blocked = graph.get_blocked_by("2")
        assert len(blocked) == 2
        blocked_ids = {i.id for i in blocked}
        assert "3" in blocked_ids
        assert "5" in blocked_ids


class TestGetReadyIssues:
    """Tests for ready issue computation."""

    def test_finds_ready_issues(self, state_manager: StateManager) -> None:
        """Should find issues that are ready to work on."""
        ready = state_manager.get_ready_issues()

        # Issue 2 should be ready (blocked by done issue 1)
        # Issue 4 should be ready (no blockers)
        # Issue 6 should be ready (no blockers)
        ready_ids = {i.id for i in ready}

        assert "2" in ready_ids  # blocked by done issue
        assert "4" in ready_ids  # no deps
        assert "6" in ready_ids  # no deps

        # Issue 3 should NOT be ready (blocked by ready issue 2)
        assert "3" not in ready_ids


class TestCreateIssue:
    """Tests for issue creation."""

    def test_creates_issue_in_file(self, state_manager: StateManager) -> None:
        """Should create a new issue in the JSONL file."""
        # Force file mode
        state_manager._bd_available = False

        issue_id = state_manager.create_issue(
            title="New test issue",
            description="Test description",
            priority="P1",
            tags=["test"],
        )

        assert issue_id is not None

        # Reload and verify
        graph = state_manager.load_graph()
        issue = graph.get_issue(issue_id)

        assert issue is not None
        assert issue.title == "New test issue"
        assert issue.dk_priority == "P1"


class TestUpdateIssue:
    """Tests for issue updates."""

    def test_updates_status_in_file(self, state_manager: StateManager) -> None:
        """Should update issue status in the JSONL file."""
        # Force file mode
        state_manager._bd_available = False

        success = state_manager.update_issue("2", status="running")
        assert success is True

        # Reload and verify
        graph = state_manager.load_graph()
        issue = graph.get_issue("2")

        assert issue is not None
        assert issue.status == "running"


class TestAddDep:
    """Tests for dependency creation."""

    def test_adds_dep_to_file(self, state_manager: StateManager) -> None:
        """Should add a dependency to the deps file."""
        # Force file mode
        state_manager._bd_available = False

        success = state_manager.add_dep("4", "6", dep_type="blocks")
        assert success is True

        # Reload and verify
        graph = state_manager.load_graph()
        blockers = graph.get_blocking_deps("6")

        assert len(blockers) == 1
        assert blockers[0].id == "4"


class TestFilterToIssue:
    """Tests for graph filtering."""

    def test_filters_to_related_issues(self, state_manager: StateManager) -> None:
        """Should filter graph to issue and its deps."""
        graph = state_manager.load_graph()
        filtered = graph.filter_to_issue("3")

        # Issue 3 is blocked by 2 and 10
        # So filtered should have 3, 2, and 10
        issue_ids = {i.id for i in filtered.issues}

        assert "3" in issue_ids
        assert "2" in issue_ids
        assert "10" in issue_ids
        assert "1" not in issue_ids  # Not directly related

