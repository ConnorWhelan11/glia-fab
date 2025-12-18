"""Tests for the Dispatcher."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_kernel.kernel.dispatcher import Dispatcher, DispatchResult
from dev_kernel.kernel.config import KernelConfig, ToolchainConfig, GatesConfig
from dev_kernel.state.models import Issue


def _now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def make_issue(
    id: str = "42",
    title: str = "Test Issue",
    tool_hint: str | None = None,
) -> Issue:
    """Helper to create test issues."""
    now = _now()
    return Issue(
        id=id,
        title=title,
        description="Test description",
        status="open",
        created=now,
        updated=now,
        dk_priority="P2",
        dk_tool_hint=tool_hint,
    )


@pytest.fixture
def config() -> KernelConfig:
    """Default config for tests."""
    cfg = KernelConfig(
        max_concurrent_workcells=3,
        toolchain_priority=["codex", "claude"],
        gates=GatesConfig(
            test_command="pytest",
            typecheck_command="mypy .",
            lint_command="ruff check .",
        ),
    )
    return cfg


class TestDispatcher:
    """Tests for Dispatcher."""

    def test_route_toolchain_uses_priority(self, config: KernelConfig) -> None:
        """Routes to first available toolchain by priority."""
        dispatcher = Dispatcher(config)
        issue = make_issue()

        toolchain = dispatcher._route_toolchain(issue)

        # Should return first in priority that has an adapter
        assert toolchain in ["codex", "claude"]

    def test_route_toolchain_respects_hint(self, config: KernelConfig) -> None:
        """Respects dk_tool_hint if specified."""
        dispatcher = Dispatcher(config)
        issue = make_issue(tool_hint="claude")

        toolchain = dispatcher._route_toolchain(issue)

        assert toolchain == "claude"

    def test_build_manifest(self, config: KernelConfig) -> None:
        """Builds correct manifest structure."""
        dispatcher = Dispatcher(config)
        issue = make_issue(id="42", title="Test Issue")

        manifest = dispatcher._build_manifest(issue, "wc-42-123", "codex", None)

        assert manifest["schema_version"] == "1.0.0"
        assert manifest["workcell_id"] == "wc-42-123"
        assert manifest["issue"]["id"] == "42"
        assert manifest["issue"]["title"] == "Test Issue"
        assert manifest["toolchain"] == "codex"
        assert manifest["speculate_mode"] is False
        assert "quality_gates" in manifest

    def test_build_manifest_with_speculate(self, config: KernelConfig) -> None:
        """Manifest includes speculate info when specified."""
        dispatcher = Dispatcher(config)
        issue = make_issue()

        manifest = dispatcher._build_manifest(issue, "wc-42", "codex", "spec-0")

        assert manifest["speculate_mode"] is True
        assert manifest["speculate_tag"] == "spec-0"

    def test_get_available_toolchains(self, config: KernelConfig) -> None:
        """Returns list of available toolchains."""
        dispatcher = Dispatcher(config)

        available = dispatcher.get_available_toolchains()

        # Will be empty if CLIs aren't installed, but should be a list
        assert isinstance(available, list)


class TestDispatchResult:
    """Tests for DispatchResult dataclass."""

    def test_creation(self) -> None:
        """Can create DispatchResult."""
        result = DispatchResult(
            success=True,
            proof=None,
            workcell_id="wc-42",
            issue_id="42",
            toolchain="codex",
            duration_ms=1000,
        )

        assert result.success is True
        assert result.workcell_id == "wc-42"
        assert result.duration_ms == 1000

    def test_with_error(self) -> None:
        """Can create failed DispatchResult with error."""
        result = DispatchResult(
            success=False,
            proof=None,
            workcell_id="wc-42",
            issue_id="42",
            toolchain="codex",
            error="Timeout",
        )

        assert result.success is False
        assert result.error == "Timeout"


class TestManifestWriting:
    """Tests for manifest file writing."""

    def test_writes_manifest_to_workcell(
        self, config: KernelConfig, tmp_path: Path
    ) -> None:
        """Writes manifest.json to workcell path."""
        dispatcher = Dispatcher(config)
        issue = make_issue()

        # Create workcell directory
        workcell_path = tmp_path / "wc-42"
        workcell_path.mkdir()

        # Build manifest manually (since dispatch would need real adapter)
        manifest = dispatcher._build_manifest(issue, "wc-42", "codex", None)
        manifest_path = workcell_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        # Verify
        assert manifest_path.exists()
        loaded = json.loads(manifest_path.read_text())
        assert loaded["issue"]["id"] == "42"

