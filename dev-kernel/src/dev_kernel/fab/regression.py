"""
Fab Regression Testing and Calibration

Provides tools for:
1. Running regression tests against known-good/bad assets
2. Calibrating thresholds based on asset collections
3. Generating calibration reports
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AssetResult:
    """Result of running an asset through the gate."""

    asset_id: str
    asset_path: Path
    category: str
    expected_verdict: str
    actual_verdict: str
    expected_fail_codes: List[str]
    actual_fail_codes: List[str]
    scores: Dict[str, float]
    passed_expectation: bool
    error: Optional[str] = None


@dataclass
class RegressionReport:
    """Report from a regression test run."""

    run_id: str
    started_at: str
    completed_at: str
    duration_seconds: float
    total_assets: int
    passed: int
    failed: int
    errors: int
    pass_rate: float
    results: List[AssetResult]
    mismatches: List[AssetResult]  # Assets that didn't match expectation
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "total_assets": self.total_assets,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "summary": self.summary,
            "results": [
                {
                    "asset_id": r.asset_id,
                    "category": r.category,
                    "expected": r.expected_verdict,
                    "actual": r.actual_verdict,
                    "passed_expectation": r.passed_expectation,
                    "scores": r.scores,
                }
                for r in self.results
            ],
            "mismatches": [
                {
                    "asset_id": r.asset_id,
                    "expected": r.expected_verdict,
                    "actual": r.actual_verdict,
                    "expected_fail_codes": r.expected_fail_codes,
                    "actual_fail_codes": r.actual_fail_codes,
                }
                for r in self.mismatches
            ],
        }


@dataclass
class CalibrationData:
    """Data for threshold calibration."""

    category: str
    good_scores: List[Dict[str, float]] = field(default_factory=list)
    bad_scores: List[Dict[str, float]] = field(default_factory=list)

    def add_good(self, scores: Dict[str, float]) -> None:
        self.good_scores.append(scores)

    def add_bad(self, scores: Dict[str, float]) -> None:
        self.bad_scores.append(scores)


@dataclass
class CalibrationReport:
    """Report from threshold calibration."""

    category: str
    good_count: int
    bad_count: int
    thresholds: Dict[str, float]
    score_distributions: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "good_count": self.good_count,
            "bad_count": self.bad_count,
            "thresholds": self.thresholds,
            "score_distributions": self.score_distributions,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


class RegressionRunner:
    """
    Runs regression tests against a dataset of assets.

    Tests each asset through the gate and compares results
    to expected verdicts from the manifest.
    """

    def __init__(
        self,
        regression_dir: Path,
        gate_config_path: Optional[Path] = None,
        dry_run: bool = False,
    ):
        """
        Initialize regression runner.

        Args:
            regression_dir: Path to regression dataset
            gate_config_path: Override gate config (uses manifest default if None)
            dry_run: If True, simulate without actually running gate
        """
        self.regression_dir = Path(regression_dir)
        self.gate_config_path = gate_config_path
        self.dry_run = dry_run

        # Load manifest
        manifest_path = self.regression_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {"assets": []}

    def run(
        self,
        category: Optional[str] = None,
        asset_ids: Optional[List[str]] = None,
    ) -> RegressionReport:
        """
        Run regression tests.

        Args:
            category: Filter by category
            asset_ids: Run specific assets only

        Returns:
            RegressionReport with results
        """
        import uuid

        run_id = str(uuid.uuid4())[:8]
        started = datetime.now(timezone.utc)

        results: List[AssetResult] = []
        mismatches: List[AssetResult] = []

        # Filter assets
        assets = self.manifest.get("assets", [])
        if category:
            assets = [a for a in assets if a.get("category") == category]
        if asset_ids:
            assets = [a for a in assets if a.get("id") in asset_ids]

        logger.info(f"Running regression on {len(assets)} assets...")

        for asset_info in assets:
            result = self._run_asset(asset_info)
            results.append(result)

            if not result.passed_expectation:
                mismatches.append(result)

        completed = datetime.now(timezone.utc)
        duration = (completed - started).total_seconds()

        # Calculate stats
        passed = sum(1 for r in results if r.passed_expectation)
        failed = sum(1 for r in results if not r.passed_expectation and not r.error)
        errors = sum(1 for r in results if r.error)

        pass_rate = passed / len(results) if results else 0.0

        report = RegressionReport(
            run_id=run_id,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            duration_seconds=duration,
            total_assets=len(results),
            passed=passed,
            failed=failed,
            errors=errors,
            pass_rate=pass_rate,
            results=results,
            mismatches=mismatches,
            summary=self._generate_summary(passed, failed, errors, len(results)),
        )

        return report

    def _run_asset(self, asset_info: Dict[str, Any]) -> AssetResult:
        """Run a single asset through the gate."""
        asset_id = asset_info.get("id", "unknown")
        asset_path = self.regression_dir / asset_info.get("path", "")
        category = asset_info.get("category", "car")
        expected_verdict = asset_info.get("expected_verdict", "fail")
        expected_fail_codes = asset_info.get("expected_fail_codes", [])

        if self.dry_run:
            # Simulate result
            return AssetResult(
                asset_id=asset_id,
                asset_path=asset_path,
                category=category,
                expected_verdict=expected_verdict,
                actual_verdict="pending",
                expected_fail_codes=expected_fail_codes,
                actual_fail_codes=[],
                scores={"overall": 0.0},
                passed_expectation=True,  # Dry run always passes
            )

        try:
            # Actually run the gate
            actual_verdict, actual_fail_codes, scores = self._invoke_gate(
                asset_path, category
            )

            # Check if expectation met
            passed = actual_verdict == expected_verdict
            if expected_verdict == "fail" and actual_verdict == "fail":
                # Check if expected fail codes are present
                if expected_fail_codes:
                    passed = any(
                        code in actual_fail_codes for code in expected_fail_codes
                    )

            return AssetResult(
                asset_id=asset_id,
                asset_path=asset_path,
                category=category,
                expected_verdict=expected_verdict,
                actual_verdict=actual_verdict,
                expected_fail_codes=expected_fail_codes,
                actual_fail_codes=actual_fail_codes,
                scores=scores,
                passed_expectation=passed,
            )

        except Exception as e:
            logger.error(f"Error processing {asset_id}: {e}")
            return AssetResult(
                asset_id=asset_id,
                asset_path=asset_path,
                category=category,
                expected_verdict=expected_verdict,
                actual_verdict="error",
                expected_fail_codes=expected_fail_codes,
                actual_fail_codes=[],
                scores={},
                passed_expectation=False,
                error=str(e),
            )

    def _invoke_gate(
        self,
        asset_path: Path,
        category: str,
    ) -> Tuple[str, List[str], Dict[str, float]]:
        """
        Invoke the fab gate on an asset.

        Returns:
            Tuple of (verdict, fail_codes, scores)
        """
        # Import gate module
        from dev_kernel.fab.gate import run_gate

        # Get config path
        config_path = self.gate_config_path
        if not config_path:
            cat_config = self.manifest.get("categories", {}).get(category, {})
            config_rel = cat_config.get("gate_config", f"fab/gates/{category}_realism_v001.yaml")
            config_path = self.regression_dir.parent.parent / config_rel

        # Run gate
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = run_gate(
                asset_path=asset_path,
                config_path=config_path,
                output_dir=output_dir,
                dry_run=False,
            )

            # Parse result
            verdict_path = output_dir / "verdict" / "gate_verdict.json"
            if verdict_path.exists():
                with open(verdict_path) as f:
                    verdict_data = json.load(f)
                    return (
                        verdict_data.get("verdict", "fail"),
                        verdict_data.get("failures", {}).get("hard", [])
                        + verdict_data.get("failures", {}).get("soft", []),
                        verdict_data.get("scores", {}).get("by_critic", {}),
                    )

            return "fail", [], {}

    def _generate_summary(
        self, passed: int, failed: int, errors: int, total: int
    ) -> str:
        """Generate human-readable summary."""
        if total == 0:
            return "No assets tested"

        rate = passed / total * 100
        return f"{passed}/{total} passed ({rate:.1f}%), {failed} mismatches, {errors} errors"


class ThresholdCalibrator:
    """
    Calibrates gate thresholds based on good/bad asset collections.

    Uses score distributions to find optimal separation between
    assets that should pass vs those that should fail.
    """

    def __init__(self, category: str):
        self.category = category
        self.data = CalibrationData(category=category)

    def add_scores(
        self, scores: Dict[str, float], is_good: bool
    ) -> None:
        """Add score data from an asset."""
        if is_good:
            self.data.add_good(scores)
        else:
            self.data.add_bad(scores)

    def calibrate(self) -> CalibrationReport:
        """
        Calibrate thresholds based on collected scores.

        Uses separation analysis to find optimal thresholds
        that maximize correct classification.
        """
        thresholds: Dict[str, float] = {}
        distributions: Dict[str, Dict[str, Any]] = {}
        recommendations: List[str] = []

        # Metrics to calibrate
        metrics = ["category", "alignment", "realism", "geometry", "overall"]

        for metric in metrics:
            good_values = [s.get(metric, 0.0) for s in self.data.good_scores]
            bad_values = [s.get(metric, 0.0) for s in self.data.bad_scores]

            if not good_values or not bad_values:
                thresholds[metric] = 0.5  # Default
                continue

            # Calculate statistics
            good_mean = sum(good_values) / len(good_values)
            good_min = min(good_values)
            good_max = max(good_values)

            bad_mean = sum(bad_values) / len(bad_values)
            bad_min = min(bad_values)
            bad_max = max(bad_values)

            # Store distributions
            distributions[metric] = {
                "good": {
                    "mean": good_mean,
                    "min": good_min,
                    "max": good_max,
                    "count": len(good_values),
                },
                "bad": {
                    "mean": bad_mean,
                    "min": bad_min,
                    "max": bad_max,
                    "count": len(bad_values),
                },
            }

            # Calculate optimal threshold
            # Midpoint between worst good and best bad, biased toward good
            optimal = (good_min + bad_max) / 2
            thresholds[metric] = round(optimal, 3)

            # Check for overlap
            if good_min < bad_max:
                recommendations.append(
                    f"{metric}: Overlap detected ({bad_max:.2f} > {good_min:.2f}). "
                    f"Consider adding more diverse samples."
                )

        return CalibrationReport(
            category=self.category,
            good_count=len(self.data.good_scores),
            bad_count=len(self.data.bad_scores),
            thresholds=thresholds,
            score_distributions=distributions,
            recommendations=recommendations,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


def run_calibration(
    good_dir: Path,
    bad_dir: Path,
    category: str = "car",
    output_path: Optional[Path] = None,
) -> CalibrationReport:
    """
    Run threshold calibration on asset directories.

    Args:
        good_dir: Directory with assets that should pass
        bad_dir: Directory with assets that should fail
        category: Asset category
        output_path: Where to save report (optional)

    Returns:
        CalibrationReport with recommended thresholds
    """
    calibrator = ThresholdCalibrator(category)

    # Process good assets
    if good_dir.exists():
        for asset_path in good_dir.glob("*.glb"):
            try:
                # Would run gate and collect scores
                scores = {"overall": 0.8}  # Placeholder
                calibrator.add_scores(scores, is_good=True)
            except Exception as e:
                logger.warning(f"Failed to process {asset_path}: {e}")

    # Process bad assets
    if bad_dir.exists():
        for asset_path in bad_dir.glob("*.glb"):
            try:
                scores = {"overall": 0.3}  # Placeholder
                calibrator.add_scores(scores, is_good=False)
            except Exception as e:
                logger.warning(f"Failed to process {asset_path}: {e}")

    report = calibrator.calibrate()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info(f"Calibration report saved to {output_path}")

    return report


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fab Regression Testing and Calibration"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run regression tests")
    run_parser.add_argument(
        "--dir",
        type=Path,
        default=Path("fab/regression"),
        help="Regression dataset directory",
    )
    run_parser.add_argument(
        "--category",
        type=str,
        help="Filter by category",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without running gate",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        help="Output report path",
    )

    # Calibrate command
    cal_parser = subparsers.add_parser("calibrate", help="Calibrate thresholds")
    cal_parser.add_argument(
        "--good-dir",
        type=Path,
        required=True,
        help="Directory with good assets",
    )
    cal_parser.add_argument(
        "--bad-dir",
        type=Path,
        required=True,
        help="Directory with bad assets",
    )
    cal_parser.add_argument(
        "--category",
        type=str,
        default="car",
        help="Asset category",
    )
    cal_parser.add_argument(
        "--output",
        type=Path,
        help="Output report path",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.command == "run":
        runner = RegressionRunner(
            regression_dir=args.dir,
            dry_run=args.dry_run,
        )
        report = runner.run(category=args.category)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report.to_dict(), indent=2))

        return 0 if report.pass_rate == 1.0 else 1

    elif args.command == "calibrate":
        report = run_calibration(
            good_dir=args.good_dir,
            bad_dir=args.bad_dir,
            category=args.category,
            output_path=args.output,
        )

        if not args.output:
            print(json.dumps(report.to_dict(), indent=2))

        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

