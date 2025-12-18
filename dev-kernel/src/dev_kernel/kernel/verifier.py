"""
Verifier - Runs quality gates, compares candidates, implements vote selection.

Responsibilities:
- Run quality gates on workcell output
- Validate diffs against forbidden paths
- Compare speculate candidates
- Select winner via voting algorithm
- Support manifest-driven gates (including fab-realism for assets)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from dev_kernel.adapters.base import PatchProof
from dev_kernel.gates.runner import GateRunner

if TYPE_CHECKING:
    from dev_kernel.kernel.config import KernelConfig

logger = structlog.get_logger()


@dataclass
class VerificationResult:
    """Result of verifying a workcell's output."""

    workcell_id: str
    all_passed: bool
    gate_results: dict[str, dict]
    blocking_failures: list[str]
    forbidden_path_violations: list[str]


class Verifier:
    """
    Runs quality gates and implements vote selection.

    The verifier is responsible for:
    1. Running all quality gates (test, typecheck, lint)
    2. Checking for forbidden path violations
    3. Scoring and selecting winners in speculate+vote mode
    """

    def __init__(self, config: KernelConfig) -> None:
        self.config = config

    def verify(self, proof: PatchProof, workcell_path: Path) -> bool:
        """
        Verify a workcell's output.

        Returns True if verification passes.
        """
        workcell_id = workcell_path.name

        # Check forbidden paths
        violations = self._check_forbidden_paths(proof)
        if violations:
            logger.warning(
                "Forbidden path violations",
                workcell_id=workcell_id,
                violations=violations,
            )
            return False

        # Check if proof already has passing verification
        verification = proof.verification
        if isinstance(verification, dict) and verification.get("all_passed"):
            return True

        # Load gates from manifest (manifest-driven gates)
        gates_config = self._load_gates_from_manifest(workcell_path)

        # Separate fab gates from code gates
        fab_gates = {k: v for k, v in gates_config.items() if k.startswith("fab-")}
        code_gates = {k: v for k, v in gates_config.items() if not k.startswith("fab-")}

        results: dict[str, dict[str, Any]] = {}

        # Run code gates
        if code_gates:
            runner = GateRunner(
                logs_dir=workcell_path / "logs",
                cwd=workcell_path,
                gates_config=code_gates,
            )
            code_results = runner.run_all()
            results.update(code_results)

        # Run fab gates: run realism-style gates first, then optional engine integration (fab-godot).
        fab_items = list(fab_gates.items())
        godot_gate: tuple[str, Any] | None = None
        non_godot_fab_gates: list[tuple[str, Any]] = []
        for name, cfg in fab_items:
            if name == "fab-godot":
                godot_gate = (name, cfg)
            else:
                non_godot_fab_gates.append((name, cfg))

        for gate_name, gate_config in non_godot_fab_gates:
            fab_result = self._run_fab_gate(gate_name, gate_config, workcell_path, proof)
            results[gate_name] = fab_result

        if godot_gate is not None:
            gate_name, gate_config = godot_gate
            upstream_failed = any(
                results.get(name, {}).get("passed") is False for name, _ in non_godot_fab_gates
            )
            if upstream_failed:
                results[gate_name] = {
                    "passed": True,
                    "skipped": True,
                    "reason": "Skipped fab-godot because an upstream fab gate failed",
                    "duration_ms": 0,
                }
            else:
                fab_result = self._run_fab_gate(gate_name, gate_config, workcell_path, proof)
                results[gate_name] = fab_result

        all_passed = all(r.get("passed", False) for r in results.values())

        if not all_passed:
            failures = [name for name, r in results.items() if not r.get("passed")]
            logger.warning(
                "Gate failures",
                workcell_id=workcell_id,
                failures=failures,
            )

        # Update proof verification
        proof.verification = {
            "gates": results,
            "all_passed": all_passed,
            "blocking_failures": [name for name, r in results.items() if not r.get("passed")],
        }

        # Persist updated proof to disk
        self._persist_proof(proof, workcell_path)

        return all_passed

    def _load_gates_from_manifest(self, workcell_path: Path) -> dict[str, Any]:
        """Load quality gates from workcell manifest.json."""
        manifest_path = workcell_path / "manifest.json"

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                gates = manifest.get("quality_gates", {})
                if gates:
                    logger.debug("Loaded gates from manifest", gates=list(gates.keys()))
                    return gates
            except Exception as e:
                logger.warning("Failed to load manifest", error=str(e))

        # Fallback to config defaults
        return {
            "test": self.config.gates.test_command,
            "typecheck": self.config.gates.typecheck_command,
            "lint": self.config.gates.lint_command,
        }

    def _run_fab_gate(
        self,
        gate_name: str,
        gate_config: dict[str, Any],
        workcell_path: Path,
        proof: PatchProof,
    ) -> dict[str, Any]:
        """Run a fab-* gate (e.g. fab-gate realism, fab-godot integration)."""
        import subprocess
        import time

        logger.info("Running fab gate", gate=gate_name, config=gate_config)

        start_time = time.time()
        gate_output_dir = workcell_path / "logs" / "fab" / gate_name

        try:
            # Find asset file in workcell
            asset_path = self._find_asset_file(workcell_path, proof)
            if not asset_path:
                return {
                    "passed": False,
                    "exit_code": 1,
                    "error": "No asset file found",
                    "duration_ms": int((time.time() - start_time) * 1000),
                }

            gate_config_id = gate_config.get("gate_config_id", "car_realism_v001")

            if gate_name == "fab-godot":
                template_dir = gate_config.get("template_dir") or gate_config.get("template")
                cmd = [
                    "python",
                    "-m",
                    "dev_kernel.fab.godot",
                    "--asset",
                    str(asset_path),
                    "--config",
                    gate_config_id,
                    "--out",
                    str(gate_output_dir),
                    "--json",
                ]
                if template_dir:
                    cmd.extend(["--template-dir", str(template_dir)])
            else:
                # Run the Fab realism gate CLI
                cmd = [
                    "python",
                    "-m",
                    "dev_kernel.fab.gate",
                    "--asset",
                    str(asset_path),
                    "--config",
                    gate_config_id,
                    "--out",
                    str(gate_output_dir),
                    "--json",
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=workcell_path,
                timeout=1800,  # 30 minute timeout (rendering + critics)
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse result: prefer structured verdict over exit code.
            passed = result.returncode == 0
            gate_result: dict[str, Any] = {
                "passed": passed,
                "exit_code": result.returncode,
                "duration_ms": duration_ms,
            }

            # Try to parse JSON output
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                    verdict = output.get("verdict", "unknown")
                    gate_result["verdict"] = verdict
                    gate_result["scores"] = output.get("scores", {})
                    gate_result["failures"] = output.get("failures", {})
                    gate_result["next_actions"] = output.get("next_actions", [])
                    gate_result["artifacts"] = output.get("artifacts", {})

                    if verdict in ("pass", "fail", "escalate"):
                        passed = verdict == "pass"
                        gate_result["passed"] = passed
                except json.JSONDecodeError:
                    pass

            if result.stderr:
                gate_result["stderr"] = result.stderr[:1000]

            logger.info(
                "Fab gate completed",
                gate=gate_name,
                passed=passed,
                duration_ms=duration_ms,
            )

            return gate_result

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "exit_code": -1,
                "error": "Gate timeout",
                "duration_ms": int((time.time() - start_time) * 1000),
            }
        except Exception as e:
            logger.error("Fab gate failed", gate=gate_name, error=str(e))
            return {
                "passed": False,
                "exit_code": -1,
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }

    def _find_asset_file(self, workcell_path: Path, proof: PatchProof) -> Path | None:
        """Find the asset file in a workcell."""
        # Check proof for asset path
        if proof.patch:
            asset_path = proof.patch.get("asset_path")
            if asset_path:
                path = Path(asset_path)
                if path.is_absolute() and path.exists():
                    return path
                relative = workcell_path / asset_path
                if relative.exists():
                    return relative

        # Search for common asset patterns
        patterns = ["*.glb", "*.gltf", "*.blend", "asset.glb", "output.glb"]
        for pattern in patterns:
            matches = list(workcell_path.glob(pattern))
            if matches:
                return matches[0]
            # Also check common output directories
            for subdir in ["output", "assets", "export"]:
                matches = list((workcell_path / subdir).glob(pattern))
                if matches:
                    return matches[0]

        return None

    def _persist_proof(self, proof: PatchProof, workcell_path: Path) -> None:
        """Persist updated proof.json to workcell."""
        proof_path = workcell_path / "proof.json"
        try:
            proof_data = {
                "schema_version": "1.0.0",
                "workcell_id": proof.workcell_id,
                "status": proof.status,
                "confidence": proof.confidence,
                "risk_classification": proof.risk_classification,
                "patch": proof.patch,
                "verification": proof.verification,
                "metadata": proof.metadata,
            }
            proof_path.write_text(json.dumps(proof_data, indent=2, default=str))
            logger.debug("Persisted proof", path=str(proof_path))
        except Exception as e:
            logger.warning("Failed to persist proof", error=str(e))

    async def verify_async(
        self, proof: PatchProof, workcell_path: Path
    ) -> VerificationResult:
        """
        Verify a workcell's output asynchronously.

        Returns detailed verification result.
        """
        workcell_id = workcell_path.name

        # Check forbidden paths
        violations = self._check_forbidden_paths(proof)
        if violations:
            return VerificationResult(
                workcell_id=workcell_id,
                all_passed=False,
                gate_results={},
                blocking_failures=["forbidden-paths"],
                forbidden_path_violations=violations,
            )

        # Run gates asynchronously
        runner = GateRunner(
            logs_dir=workcell_path / "logs",
            cwd=workcell_path,
            gates_config={
                "test": self.config.gates.test_command,
                "typecheck": self.config.gates.typecheck_command,
                "lint": self.config.gates.lint_command,
            },
        )

        gate_results = await runner.run_all_gates(
            workcell_path,
            {
                "test": self.config.gates.test_command,
                "typecheck": self.config.gates.typecheck_command,
                "lint": self.config.gates.lint_command,
            },
        )

        # Convert to dict format
        results_dict = {
            name: {
                "passed": r.passed,
                "exit_code": r.exit_code,
                "duration_ms": r.duration_ms,
            }
            for name, r in gate_results.items()
        }

        blocking_failures = [name for name, r in gate_results.items() if not r.passed]

        return VerificationResult(
            workcell_id=workcell_id,
            all_passed=len(blocking_failures) == 0,
            gate_results=results_dict,
            blocking_failures=blocking_failures,
            forbidden_path_violations=[],
        )

    def vote(self, candidates: list[PatchProof]) -> PatchProof | None:
        """
        Select winner from speculate candidates via voting algorithm.

        Scoring components:
        1. Verification (all gates pass) - 40%
        2. Confidence score - 20%
        3. Diff size (smaller is better) - 15%
        4. Risk classification - 15%
        5. Execution time (faster is better) - 10%
        """
        scores: dict[str, float] = {}
        valid_candidates: list[PatchProof] = []

        for candidate in candidates:
            # Auto-reject if gates failed
            verification = candidate.verification
            all_passed = False
            if isinstance(verification, dict):
                all_passed = verification.get("all_passed", False)

            if not all_passed:
                scores[candidate.workcell_id] = 0
                continue

            score = self._score_candidate(candidate, candidates)
            scores[candidate.workcell_id] = score
            valid_candidates.append(candidate)

        if not valid_candidates:
            logger.warning("No valid candidates in vote")
            return None

        # Find winner
        best = max(valid_candidates, key=lambda c: scores[c.workcell_id])
        best_score = scores[best.workcell_id]

        logger.info(
            "Vote winner selected",
            winner=best.workcell_id,
            score=best_score,
            candidates=len(candidates),
        )

        # Check threshold
        threshold = self.config.speculation.vote_threshold * 100

        if best_score >= threshold:
            return best

        logger.warning(
            "Winner below threshold",
            score=best_score,
            threshold=threshold,
        )
        return None

    def _score_candidate(
        self, candidate: PatchProof, all_candidates: list[PatchProof]
    ) -> float:
        """Score a single candidate."""
        score = 0.0

        # Verification: 40 points (already checked, so always add)
        score += 40

        # Confidence: 0-20 points
        score += candidate.confidence * 20

        # Diff size: 0-15 points (smaller is better)
        patch = candidate.patch or {}
        diff_stats = patch.get("diff_stats", {})
        this_lines = diff_stats.get("insertions", 0) + diff_stats.get("deletions", 0)

        max_lines = max(
            (c.patch or {}).get("diff_stats", {}).get("insertions", 0)
            + (c.patch or {}).get("diff_stats", {}).get("deletions", 0)
            for c in all_candidates
        ) or 1

        score += (1 - this_lines / max_lines) * 15

        # Risk: 0-15 points
        risk_scores = {"low": 15, "medium": 10, "high": 5, "critical": 0}
        score += risk_scores.get(candidate.risk_classification, 5)

        # Speed: 0-10 points (faster is better)
        metadata = candidate.metadata or {}
        this_duration = metadata.get("duration_ms", 0) or 0

        max_duration = max(
            (c.metadata or {}).get("duration_ms", 0) or 0 for c in all_candidates
        ) or 1

        if max_duration > 0:
            score += (1 - this_duration / max_duration) * 10
        else:
            score += 10

        return score

    def _check_forbidden_paths(self, proof: PatchProof) -> list[str]:
        """Check if proof has forbidden path violations."""
        patch = proof.patch or {}
        return patch.get("forbidden_path_violations", [])
