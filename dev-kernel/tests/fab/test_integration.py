"""
Fab V0 Integration Test

Tests the complete pipeline:
  Issue (with asset tags) → Manifest → Gate → Render → Critics → Verdict → Archive

This test uses the simple_car.glb test asset and validates:
1. Manifest includes fab-realism gate when asset tags present
2. Geometry critic runs and produces valid output
3. Category critic runs (stub mode without ML deps)
4. Gate produces verdict JSON
5. Archives preserve render artifacts recursively
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent.parent.parent


class TestFabIntegration:
    """Integration tests for Fab/Realism Gate pipeline."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        d = tempfile.mkdtemp(prefix="fab_test_")
        yield Path(d)
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def test_asset(self):
        """Path to test asset."""
        asset = REPO_ROOT / "fab" / "test_assets" / "simple_car.glb"
        if not asset.exists():
            pytest.skip("Test asset not found - run lookdev scene creation first")
        return asset

    @pytest.fixture
    def gate_config(self):
        """Path to gate config."""
        config = REPO_ROOT / "fab" / "gates" / "car_realism_v001.yaml"
        if not config.exists():
            pytest.skip("Gate config not found")
        return config

    def test_gate_config_loads(self, gate_config):
        """Test that gate config loads correctly."""
        from dev_kernel.fab.config import load_gate_config

        config = load_gate_config(gate_config)

        assert config.gate_config_id == "car_realism_v001"
        assert config.category == "car"
        assert config.render.engine == "CYCLES"
        assert config.render.samples == 128

    def test_manifest_includes_fab_gate_for_asset_tags(self):
        """Test that dispatcher includes fab-realism gate for asset-tagged issues."""
        from dev_kernel.kernel.dispatcher import Dispatcher

        # Create mock config
        mock_config = MagicMock()
        mock_config.gates.test_command = "pytest"
        mock_config.gates.typecheck_command = "mypy ."
        mock_config.gates.lint_command = "ruff check ."
        mock_config.toolchain_priority = []
        mock_config.toolchains = {}

        dispatcher = Dispatcher(mock_config)

        # Test with asset tags
        asset_tags = ["asset:car", "gate:realism"]
        gates = dispatcher._build_quality_gates(asset_tags)

        assert "fab-realism" in gates
        assert gates["fab-realism"]["type"] == "fab-realism"
        assert gates["fab-realism"]["category"] == "car"
        assert "test" in gates  # Code gates still present by default

    def test_manifest_asset_only_disables_code_gates(self):
        """Test that gate:asset-only disables code gates."""
        from dev_kernel.kernel.dispatcher import Dispatcher

        mock_config = MagicMock()
        mock_config.gates.test_command = "pytest"
        mock_config.gates.typecheck_command = "mypy ."
        mock_config.gates.lint_command = "ruff check ."
        mock_config.toolchain_priority = []
        mock_config.toolchains = {}

        dispatcher = Dispatcher(mock_config)

        # Test with asset-only tag
        asset_tags = ["asset:car", "gate:realism", "gate:asset-only"]
        gates = dispatcher._build_quality_gates(asset_tags)

        assert "fab-realism" in gates
        assert "test" not in gates
        assert "typecheck" not in gates
        assert "lint" not in gates

    def test_manifest_includes_fab_godot_when_tagged(self):
        """Test that gate:godot adds the fab-godot engine integration gate."""
        from dev_kernel.kernel.dispatcher import Dispatcher

        mock_config = MagicMock()
        mock_config.gates.test_command = "pytest"
        mock_config.gates.typecheck_command = "mypy ."
        mock_config.gates.lint_command = "ruff check ."
        mock_config.toolchain_priority = []
        mock_config.toolchains = {}

        dispatcher = Dispatcher(mock_config)

        tags = ["asset:interior_architecture", "gate:realism", "gate:godot"]
        gates = dispatcher._build_quality_gates(tags)

        assert "fab-realism" in gates
        assert "fab-godot" in gates
        assert gates["fab-godot"]["gate_config_id"] == "godot_integration_v001"

    def test_geometry_critic_evaluates_asset(self, test_asset, temp_dir):
        """Test geometry critic produces valid output."""
        import importlib.util

        if importlib.util.find_spec("trimesh") is None:
            pytest.skip("trimesh not installed (dev-kernel[fab] extra required)")

        from dev_kernel.fab.critics.geometry import GeometryCritic

        critic = GeometryCritic(category="car")
        result = critic.evaluate(test_asset)

        assert result is not None
        assert result.bounds is not None
        assert result.mesh_metrics is not None

        # Test asset is intentionally wrong scale - should have fail codes
        assert len(result.fail_codes) > 0

        # Serialize to JSON
        result_dict = result.to_dict()
        assert "score" in result_dict
        assert "bounds" in result_dict
        assert "mesh_metrics" in result_dict

        # Write to file
        output_path = temp_dir / "geometry_result.json"
        with open(output_path, "w") as f:
            json.dump(result_dict, f, indent=2)

        assert output_path.exists()

    def test_category_critic_evaluates_renders(self, temp_dir):
        """Test category critic works (stub mode without ML deps)."""
        from dev_kernel.fab.critics.category import CategoryCritic

        # Create mock render files
        beauty_dir = temp_dir / "beauty"
        clay_dir = temp_dir / "clay"
        beauty_dir.mkdir()
        clay_dir.mkdir()

        # Create dummy PNG files (just touch them)
        for i in range(5):
            (beauty_dir / f"beauty_view_{i}.png").touch()
            (clay_dir / f"clay_view_{i}.png").touch()

        critic = CategoryCritic(category="car", min_views_passing=3)
        result = critic.evaluate(
            list(beauty_dir.glob("*.png")),
            list(clay_dir.glob("*.png")),
        )

        assert result is not None
        assert result.views_evaluated == 10
        # Stub mode with empty files = low confidence
        assert len(result.view_scores) == 10

    def test_gate_dry_run_produces_valid_output(
        self, test_asset, gate_config, temp_dir
    ):
        """Test gate CLI dry-run produces valid JSON."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "dev_kernel.fab.gate",
                "--asset",
                str(test_asset),
                "--config",
                str(gate_config),
                "--out",
                str(temp_dir),
                "--dry-run",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "dev-kernel",
        )

        assert result.returncode == 0, f"Gate failed: {result.stderr}"

        # Parse JSON output
        output = json.loads(result.stdout)
        assert "run_id" in output
        assert "verdict" in output
        assert "scores" in output

        # Check artifacts created
        assert (temp_dir / "verdict" / "gate_verdict.json").exists()
        assert (temp_dir / "manifest.json").exists()

    def test_critics_cli_geometry(self, test_asset, gate_config, temp_dir):
        """Test critics CLI geometry subcommand."""
        output_path = temp_dir / "geometry.json"

        result = subprocess.run(
            [
                "python",
                "-m",
                "dev_kernel.fab.critics.cli",
                "geometry",
                "--mesh",
                str(test_asset),
                "--config",
                str(gate_config),
                "--out",
                str(output_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "dev-kernel",
        )

        # Geometry critic should complete (exit 1 = failed checks, but ran successfully)
        assert result.returncode in (0, 1)

        # Output file created
        assert output_path.exists()

        # Valid JSON
        with open(output_path) as f:
            data = json.load(f)

        assert "score" in data
        assert "bounds" in data
        assert "fail_codes" in data

    def test_schema_validation(self):
        """Test that all fab schemas are valid JSON Schema."""
        schemas_dir = REPO_ROOT / "dev-kernel" / "schemas" / "fab"

        if not schemas_dir.exists():
            pytest.skip("Schemas directory not found")

        for schema_file in schemas_dir.glob("*.json"):
            with open(schema_file) as f:
                schema = json.load(f)

            assert "$id" in schema or "$schema" in schema
            assert "type" in schema or "properties" in schema

    def test_archive_preserves_nested_structure(self, temp_dir):
        """Test that archive preserves nested directory structure."""
        from dev_kernel.workcell.manager import WorkcellManager

        # Create mock workcell structure
        workcell_path = temp_dir / "wc-test-123"
        logs_path = workcell_path / "logs"
        fab_path = logs_path / "fab" / "fab-realism"
        fab_path.mkdir(parents=True)

        # Create nested files
        (logs_path / "stdout.log").write_text("stdout content")
        (fab_path / "verdict.json").write_text('{"passed": true}')
        (fab_path / "render_output.png").write_bytes(b"PNG data")

        # Create proof and manifest
        (workcell_path / "proof.json").write_text('{"status": "success"}')
        (workcell_path / "manifest.json").write_text('{"workcell_id": "test"}')
        (workcell_path / ".workcell").write_text('{"id": "wc-test-123"}')

        # Mock config
        mock_config = MagicMock()

        # Create manager with temp archives dir
        manager = WorkcellManager.__new__(WorkcellManager)
        manager.config = mock_config
        manager.repo_root = temp_dir
        manager.workcells_dir = temp_dir
        manager.archives_dir = temp_dir / "archives"
        manager.archives_dir.mkdir()

        # Archive
        manager._archive_logs(workcell_path)

        # Verify structure preserved
        archive_path = manager.archives_dir / "wc-test-123"
        assert archive_path.exists()
        assert (archive_path / "logs" / "stdout.log").exists()
        assert (archive_path / "logs" / "fab" / "fab-realism" / "verdict.json").exists()
        assert (
            archive_path / "logs" / "fab" / "fab-realism" / "render_output.png"
        ).exists()
        assert (archive_path / "proof.json").exists()
        assert (archive_path / "manifest.json").exists()


class TestFabModuleImports:
    """Test that fab module imports work correctly."""

    def test_fab_module_imports(self):
        """Test main fab module imports."""
        from dev_kernel.fab import (
            GateConfig,
            load_gate_config,
            find_gate_config,
            run_gate,
            GateResult,
            run_render_harness,
            RenderResult,
        )

        assert GateConfig is not None
        assert load_gate_config is not None

    def test_critics_import(self):
        """Test critics import."""
        from dev_kernel.fab.critics import (
            CategoryCritic,
            CategoryResult,
            GeometryCritic,
            GeometryResult,
        )

        assert CategoryCritic is not None
        assert GeometryCritic is not None

    def test_config_find_gate_config(self):
        """Test finding gate config by ID."""
        from dev_kernel.fab.config import find_gate_config

        try:
            config_path = find_gate_config("car_realism_v001")
            assert config_path.exists()
            assert "car_realism_v001" in config_path.name
        except FileNotFoundError:
            pytest.skip("Gate config not found in expected locations")
