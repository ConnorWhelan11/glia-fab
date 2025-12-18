"""Tests for toolchain adapters."""

from pathlib import Path

import pytest

from dev_kernel.adapters import CodexAdapter, ClaudeAdapter, CrushAdapter, get_adapter, get_available_adapters
from dev_kernel.adapters.base import PatchProof


@pytest.fixture
def sample_manifest() -> dict:
    """Create a sample task manifest."""
    return {
        "schema_version": "1.0.0",
        "workcell_id": "wc-42-20250117T120000Z",
        "issue": {
            "id": "42",
            "title": "Add user authentication",
            "description": "Implement JWT-based auth with refresh tokens",
            "acceptance_criteria": [
                "Users can log in with email/password",
                "JWT tokens are issued on successful login",
                "Refresh tokens extend session",
            ],
            "context_files": ["src/auth/", "src/middleware/"],
            "forbidden_paths": ["src/auth/secrets.ts", "migrations/"],
        },
        "toolchain": "codex",
        "toolchain_config": {
            "model": "o3",
        },
        "quality_gates": {
            "test": "pytest",
            "typecheck": "mypy .",
            "lint": "ruff check .",
        },
        "branch_name": "wc/42/20250117T120000Z",
    }


class TestCodexAdapter:
    """Tests for CodexAdapter."""

    def test_init_default_config(self) -> None:
        """Should initialize with default config."""
        adapter = CodexAdapter()

        assert adapter.name == "codex"
        assert adapter.default_model == "o3"
        assert adapter.approval_mode == "full-auto"

    def test_init_custom_config(self) -> None:
        """Should accept custom config."""
        adapter = CodexAdapter({
            "model": "gpt-4o",
            "approval_mode": "suggest",
        })

        assert adapter.default_model == "gpt-4o"
        assert adapter.approval_mode == "suggest"

    def test_build_prompt(self, sample_manifest: dict) -> None:
        """Should build a well-formatted prompt."""
        adapter = CodexAdapter()
        prompt = adapter._build_prompt(sample_manifest)

        assert "Add user authentication" in prompt
        assert "JWT-based auth" in prompt
        assert "Acceptance Criteria" in prompt
        assert "Forbidden Paths" in prompt
        assert "src/auth/secrets.ts" in prompt
        assert "Quality Gates" in prompt
        assert "pytest" in prompt

    def test_estimate_cost(self, sample_manifest: dict) -> None:
        """Should estimate cost correctly."""
        adapter = CodexAdapter()
        estimate = adapter.estimate_cost(sample_manifest)

        assert estimate.model == "o3"
        assert estimate.estimated_tokens == 50000  # default
        assert estimate.estimated_cost_usd > 0

    def test_build_command(self, tmp_path: Path) -> None:
        """Should build correct command."""
        adapter = CodexAdapter()
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test")

        cmd = adapter._build_command(prompt_file, "o3")

        assert cmd[0] == "codex"
        assert "--prompt" in cmd
        assert "--approval-mode" in cmd
        assert "full-auto" in cmd
        assert "--model" in cmd
        assert "o3" in cmd

    def test_parse_diff_stats(self) -> None:
        """Should parse git diff stats correctly."""
        adapter = CodexAdapter()

        # Normal output
        stats = " 3 files changed, 42 insertions(+), 12 deletions(-)"
        files, ins, dels = adapter._parse_diff_stats(stats)
        assert files == 3
        assert ins == 42
        assert dels == 12

        # Single file
        stats = " 1 file changed, 5 insertions(+)"
        files, ins, dels = adapter._parse_diff_stats(stats)
        assert files == 1
        assert ins == 5
        assert dels == 0

        # Empty
        files, ins, dels = adapter._parse_diff_stats("")
        assert files == 0
        assert ins == 0
        assert dels == 0

    def test_check_forbidden_paths(self) -> None:
        """Should detect forbidden path violations."""
        adapter = CodexAdapter()

        files = ["src/auth/login.ts", "src/auth/secrets.ts", "src/api/routes.ts"]
        forbidden = ["src/auth/secrets.ts", "migrations/"]

        violations = adapter._check_forbidden_paths(files, forbidden)

        assert "src/auth/secrets.ts" in violations
        assert "src/auth/login.ts" not in violations

    def test_check_forbidden_paths_with_wildcards(self) -> None:
        """Should handle glob-like patterns."""
        adapter = CodexAdapter()

        files = ["migrations/001_init.sql", "migrations/002_users.sql", "src/db.ts"]
        forbidden = ["migrations/"]

        violations = adapter._check_forbidden_paths(files, forbidden)

        assert "migrations/001_init.sql" in violations
        assert "migrations/002_users.sql" in violations
        assert len(violations) == 2

    def test_classify_risk_critical(self) -> None:
        """Should classify as critical when forbidden paths violated."""
        adapter = CodexAdapter()
        patch_info = {
            "forbidden_path_violations": ["src/secrets.ts"],
            "files_modified": [],
            "diff_stats": {"insertions": 0, "deletions": 0},
        }

        risk = adapter._classify_risk(patch_info, {})
        assert risk == "critical"

    def test_classify_risk_high_sensitive_files(self) -> None:
        """Should classify as high risk for sensitive files."""
        adapter = CodexAdapter()
        patch_info = {
            "forbidden_path_violations": [],
            "files_modified": ["src/auth/password.ts"],
            "diff_stats": {"insertions": 10, "deletions": 5},
        }

        risk = adapter._classify_risk(patch_info, {})
        assert risk == "high"

    def test_classify_risk_high_large_changes(self) -> None:
        """Should classify as high risk for large changes."""
        adapter = CodexAdapter()
        patch_info = {
            "forbidden_path_violations": [],
            "files_modified": ["src/utils.ts"],
            "diff_stats": {"insertions": 400, "deletions": 200},
        }

        risk = adapter._classify_risk(patch_info, {})
        assert risk == "high"

    def test_classify_risk_low(self) -> None:
        """Should classify as low risk for small safe changes."""
        adapter = CodexAdapter()
        patch_info = {
            "forbidden_path_violations": [],
            "files_modified": ["src/utils.ts"],
            "diff_stats": {"insertions": 10, "deletions": 5},
        }

        risk = adapter._classify_risk(patch_info, {})
        assert risk == "low"


class TestClaudeAdapter:
    """Tests for ClaudeAdapter."""

    def test_init_default_config(self) -> None:
        """Should initialize with default config."""
        adapter = ClaudeAdapter()

        assert adapter.name == "claude"
        assert "claude" in adapter.default_model.lower() or "sonnet" in adapter.default_model.lower()
        assert adapter.skip_permissions is True

    def test_estimate_cost(self, sample_manifest: dict) -> None:
        """Should estimate cost correctly."""
        adapter = ClaudeAdapter()
        estimate = adapter.estimate_cost(sample_manifest)

        assert estimate.estimated_tokens == 50000
        assert estimate.estimated_cost_usd > 0


class TestCrushAdapter:
    """Tests for CrushAdapter (Charmbracelet Crush)."""

    def test_init_default_config(self) -> None:
        """Should initialize with default config."""
        adapter = CrushAdapter()

        assert adapter.name == "crush"
        assert "claude" in adapter.default_model.lower() or "sonnet" in adapter.default_model.lower()
        assert adapter.auto_approve is True
        assert adapter.provider == "anthropic"

    def test_init_custom_config(self) -> None:
        """Should accept custom config."""
        adapter = CrushAdapter({
            "model": "gpt-4o",
            "provider": "openai",
            "auto_approve": False,
        })

        assert adapter.default_model == "gpt-4o"
        assert adapter.provider == "openai"
        assert adapter.auto_approve is False

    def test_estimate_cost_anthropic(self, sample_manifest: dict) -> None:
        """Should estimate cost correctly for Anthropic models."""
        adapter = CrushAdapter()
        estimate = adapter.estimate_cost(sample_manifest)

        assert estimate.estimated_tokens == 50000
        assert estimate.estimated_cost_usd > 0

    def test_estimate_cost_openai(self, sample_manifest: dict) -> None:
        """Should estimate cost correctly for OpenAI models."""
        sample_manifest["toolchain_config"] = {"model": "gpt-4o"}
        adapter = CrushAdapter()
        estimate = adapter.estimate_cost(sample_manifest)

        assert estimate.model == "gpt-4o"
        assert estimate.estimated_cost_usd > 0

    def test_estimate_cost_deepseek(self, sample_manifest: dict) -> None:
        """Should estimate cost correctly for Deepseek models."""
        sample_manifest["toolchain_config"] = {"model": "deepseek-chat"}
        adapter = CrushAdapter()
        estimate = adapter.estimate_cost(sample_manifest)

        assert estimate.model == "deepseek-chat"
        # Deepseek is cheap
        assert estimate.estimated_cost_usd < 1.0

    def test_build_prompt(self, sample_manifest: dict) -> None:
        """Should build a well-formatted prompt."""
        adapter = CrushAdapter()
        prompt = adapter._build_prompt(sample_manifest)

        assert "Add user authentication" in prompt
        assert "JWT-based auth" in prompt
        assert "Acceptance Criteria" in prompt

    def test_classify_risk_critical(self) -> None:
        """Should classify as critical when forbidden paths violated."""
        adapter = CrushAdapter()
        patch_info = {
            "forbidden_path_violations": ["src/secrets.ts"],
            "files_modified": [],
            "diff_stats": {"insertions": 0, "deletions": 0},
        }

        risk = adapter._classify_risk(patch_info)
        assert risk == "critical"

    def test_classify_risk_high_sensitive_files(self) -> None:
        """Should classify as high risk for sensitive files."""
        adapter = CrushAdapter()
        patch_info = {
            "forbidden_path_violations": [],
            "files_modified": ["src/auth/password.ts"],
            "diff_stats": {"insertions": 10, "deletions": 5},
        }

        risk = adapter._classify_risk(patch_info)
        assert risk == "high"


class TestGetAdapter:
    """Tests for get_adapter helper."""

    def test_get_codex(self) -> None:
        """Should return CodexAdapter for 'codex'."""
        adapter = get_adapter("codex")
        assert adapter is not None
        assert isinstance(adapter, CodexAdapter)

    def test_get_claude(self) -> None:
        """Should return ClaudeAdapter for 'claude'."""
        adapter = get_adapter("claude")
        assert adapter is not None
        assert isinstance(adapter, ClaudeAdapter)

    def test_get_crush(self) -> None:
        """Should return CrushAdapter for 'crush'."""
        adapter = get_adapter("crush")
        assert adapter is not None
        assert isinstance(adapter, CrushAdapter)

    def test_get_unknown(self) -> None:
        """Should return None for unknown adapter."""
        adapter = get_adapter("unknown")
        assert adapter is None

    def test_case_insensitive(self) -> None:
        """Should be case-insensitive."""
        assert get_adapter("CODEX") is not None
        assert get_adapter("Claude") is not None
        assert get_adapter("CRUSH") is not None


class TestPatchProof:
    """Tests for PatchProof dataclass."""

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        proof = PatchProof(
            schema_version="1.0.0",
            workcell_id="wc-42",
            issue_id="42",
            status="success",
            patch={"files_modified": ["file.ts"]},
            verification={"all_passed": True},
            metadata={"toolchain": "codex"},
            confidence=0.9,
            risk_classification="low",
        )

        d = proof.to_dict()

        assert d["schema_version"] == "1.0.0"
        assert d["workcell_id"] == "wc-42"
        assert d["status"] == "success"
        assert d["confidence"] == 0.9

