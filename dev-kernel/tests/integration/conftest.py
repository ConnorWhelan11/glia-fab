"""Fixtures for integration tests."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest


def _utc_now() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture
def mock_beads_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Create a mock Beads repository with issues and dependencies.

    Structure:
    - .beads/issues.jsonl
    - .beads/deps.jsonl
    - .dev-kernel/config.yaml
    - .git/ (initialized)
    """
    repo_root = tmp_path / "test-repo"
    repo_root.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_root,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_root,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_root,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_root / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_root, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_root,
        capture_output=True,
    )

    # Create main branch
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=repo_root,
        capture_output=True,
    )

    # Create .beads directory
    beads_dir = repo_root / ".beads"
    beads_dir.mkdir()

    now = _utc_now()

    # Create issues
    issues = [
        {
            "id": "1",
            "title": "Add user authentication",
            "description": "Implement JWT-based authentication with refresh tokens",
            "status": "open",
            "created": now,
            "updated": now,
            "tags": ["auth", "security"],
            "dk_priority": "P1",
            "dk_risk": "high",
            "dk_size": "L",
            "dk_estimated_tokens": 80000,
        },
        {
            "id": "2",
            "title": "Create user model",
            "description": "Define User model with email, password hash, and profile fields",
            "status": "done",
            "created": now,
            "updated": now,
            "tags": ["model"],
            "dk_priority": "P1",
            "dk_risk": "low",
            "dk_size": "S",
        },
        {
            "id": "3",
            "title": "Add login endpoint",
            "description": "POST /api/auth/login endpoint that returns JWT tokens",
            "status": "open",
            "created": now,
            "updated": now,
            "tags": ["api", "auth"],
            "dk_priority": "P1",
            "dk_risk": "medium",
            "dk_size": "M",
        },
        {
            "id": "4",
            "title": "Add token refresh endpoint",
            "description": "POST /api/auth/refresh endpoint for token renewal",
            "status": "open",
            "created": now,
            "updated": now,
            "tags": ["api", "auth"],
            "dk_priority": "P2",
            "dk_risk": "medium",
            "dk_size": "S",
        },
        {
            "id": "5",
            "title": "Write authentication tests",
            "description": "Comprehensive test suite for auth endpoints",
            "status": "open",
            "created": now,
            "updated": now,
            "tags": ["test"],
            "dk_priority": "P2",
            "dk_risk": "low",
            "dk_size": "M",
        },
    ]

    issues_file = beads_dir / "issues.jsonl"
    with open(issues_file, "w") as f:
        for issue in issues:
            f.write(json.dumps(issue) + "\n")

    # Create dependencies
    deps = [
        # Issue 1 (auth) blocks issue 3 (login) and 4 (refresh)
        {
            "from": "2",
            "to": "3",
            "type": "blocks",
            "created": now,
        },  # user model blocks login
        {
            "from": "3",
            "to": "4",
            "type": "blocks",
            "created": now,
        },  # login blocks refresh
        {
            "from": "3",
            "to": "5",
            "type": "blocks",
            "created": now,
        },  # login blocks tests
        {
            "from": "4",
            "to": "5",
            "type": "blocks",
            "created": now,
        },  # refresh blocks tests
    ]

    deps_file = beads_dir / "deps.jsonl"
    with open(deps_file, "w") as f:
        for dep in deps:
            f.write(json.dumps(dep) + "\n")

    # Create .dev-kernel directory
    dk_dir = repo_root / ".dev-kernel"
    dk_dir.mkdir()

    # Create config
    config = {
        "max_concurrent_workcells": 2,
        "max_concurrent_tokens": 150000,
        "toolchain_priority": ["codex", "claude"],
        "toolchains": {
            "codex": {
                "enabled": True,
                "timeout_seconds": 60,
            },
            "claude": {
                "enabled": True,
                "timeout_seconds": 60,
            },
        },
        "gates": {
            "test_command": "echo 'tests pass'",
            "typecheck_command": "echo 'types ok'",
            "lint_command": "echo 'lint ok'",
        },
        "speculation": {
            "enabled": True,
            "default_parallelism": 2,
        },
    }

    config_file = dk_dir / "config.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # Create logs directory
    (dk_dir / "logs").mkdir()

    yield repo_root


@pytest.fixture
def mock_adapter(monkeypatch):
    """
    Mock the adapter execution to simulate successful completion.

    This allows testing the full flow without actually running LLM agents.
    """
    from dev_kernel.adapters.base import PatchProof

    def mock_execute_sync(self, manifest, workcell_path, timeout_seconds=1800):
        """Mock execute that creates a successful proof."""
        # Create logs directory
        logs_dir = workcell_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Write mock logs
        (logs_dir / f"{self.name}-stdout.log").write_text("Mock execution successful\n")
        (logs_dir / f"{self.name}-stderr.log").write_text("")

        # Create mock proof
        return PatchProof(
            schema_version="1.0.0",
            workcell_id=manifest.get("workcell_id", "unknown"),
            issue_id=manifest.get("issue", {}).get("id", "unknown"),
            status="success",
            patch={
                "branch": manifest.get("branch_name", ""),
                "base_commit": "abc123",
                "head_commit": "def456",
                "diff_stats": {"files_changed": 2, "insertions": 50, "deletions": 10},
                "files_modified": ["src/auth.py", "tests/test_auth.py"],
                "forbidden_path_violations": [],
            },
            verification={
                "gates": {
                    "test": {"passed": True, "exit_code": 0},
                    "typecheck": {"passed": True, "exit_code": 0},
                    "lint": {"passed": True, "exit_code": 0},
                },
                "all_passed": True,
                "blocking_failures": [],
            },
            metadata={
                "toolchain": self.name,
                "model": "mock",
                "duration_ms": 1000,
            },
            confidence=0.85,
            risk_classification="low",
        )

    # Patch both adapters
    from dev_kernel.adapters.codex import CodexAdapter
    from dev_kernel.adapters.claude import ClaudeAdapter

    monkeypatch.setattr(CodexAdapter, "execute_sync", mock_execute_sync)
    monkeypatch.setattr(ClaudeAdapter, "execute_sync", mock_execute_sync)

    # Mock availability check
    monkeypatch.setattr(CodexAdapter, "available", property(lambda self: True))
    monkeypatch.setattr(ClaudeAdapter, "available", property(lambda self: True))


@pytest.fixture
def mock_workcell_manager(monkeypatch, tmp_path):
    """Mock workcell manager to avoid actual git worktree operations."""
    from dev_kernel.workcell.manager import WorkcellManager

    workcells_dir = tmp_path / ".workcells"
    workcells_dir.mkdir()

    def mock_create(self, issue_id, speculate_tag=None):
        """Create a mock workcell directory."""
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if speculate_tag:
            name = f"wc-{issue_id}-{speculate_tag}-{timestamp}"
        else:
            name = f"wc-{issue_id}-{timestamp}"

        wc_path = workcells_dir / name
        wc_path.mkdir(parents=True)
        (wc_path / "logs").mkdir()

        return wc_path

    def mock_cleanup(self, workcell_path, keep_logs=False):
        """Mock cleanup."""
        pass  # Don't actually delete in tests

    monkeypatch.setattr(WorkcellManager, "create", mock_create)
    monkeypatch.setattr(WorkcellManager, "cleanup", mock_cleanup)
