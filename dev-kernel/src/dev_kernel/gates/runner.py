"""
GateRunner - Execute quality gates and collect results.

Responsibilities:
- Run quality gate commands (test, lint, typecheck, build)
- Capture output and exit codes
- Handle timeouts and retries
- Track flaky tests
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


@dataclass
class GateResult:
    """Result of running a single quality gate."""

    name: str
    passed: bool
    exit_code: int
    duration_ms: int
    output_path: str | None = None
    failure_summary: str | None = None
    attempt: int = 1
    flaky_detected: bool = False


@dataclass
class GateConfig:
    """Configuration for a quality gate."""

    name: str
    command: str
    timeout: int = 300  # seconds
    retries: int = 1


class GateRunner:
    """
    Executes quality gates and collects results.
    """

    def __init__(
        self,
        logs_dir: Path | None = None,
        cwd: Path | None = None,
        gates_config: dict[str, str] | None = None,
    ) -> None:
        self.logs_dir = logs_dir
        self.cwd = cwd or Path.cwd()
        self.gates_config = gates_config or {
            "test": "pytest",
            "typecheck": "mypy .",
            "lint": "ruff check .",
        }

    @classmethod
    def from_workcell(cls) -> GateRunner:
        """Create a GateRunner from within a workcell."""
        cwd = Path.cwd()
        logs_dir = cwd / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Try to load config from manifest if available
        manifest_path = cwd / "manifest.json"
        gates_config = None

        if manifest_path.exists():
            import json

            try:
                manifest = json.loads(manifest_path.read_text())
                gates_config = manifest.get("quality_gates")
            except (json.JSONDecodeError, OSError):
                pass

        return cls(logs_dir=logs_dir, cwd=cwd, gates_config=gates_config)

    def run_gate(
        self,
        name: str,
        auto_fix: bool = False,
    ) -> dict:
        """
        Run a single gate synchronously (for CLI use).

        Returns a dict with pass/fail and details.
        """
        import subprocess
        from datetime import datetime

        command = self.gates_config.get(name, "")
        if not command:
            return {"passed": False, "error": f"Unknown gate: {name}"}

        if auto_fix and name == "lint":
            command = command.replace("ruff check", "ruff check --fix")

        started_at = datetime.utcnow()

        result = subprocess.run(
            command,
            shell=True,
            cwd=self.cwd,
            capture_output=True,
            text=True,
        )

        duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        passed = result.returncode == 0

        # Save output
        if self.logs_dir:
            log_path = self.logs_dir / f"{name}.log"
            with open(log_path, "w") as f:
                f.write(f"=== STDOUT ===\n{result.stdout}\n")
                f.write(f"=== STDERR ===\n{result.stderr}\n")

        return {
            "passed": passed,
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
            "output": result.stdout if not passed else None,
            "error": result.stderr if not passed else None,
        }

    def run_all(self) -> dict[str, dict]:
        """Run all gates synchronously (for CLI use)."""
        results = {}
        for name in self.gates_config:
            results[name] = self.run_gate(name)
        return results

    async def run_gate_async(
        self,
        name: str,
        command: str,
        cwd: Path,
        timeout: int = 300,
        attempt: int = 1,
    ) -> GateResult:
        """
        Run a single quality gate.

        Returns GateResult with pass/fail and execution details.
        """
        started_at = datetime.utcnow()

        logger.info("Running gate", gate=name, command=command, attempt=attempt)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            exit_code = process.returncode or 0
            passed = exit_code == 0

            # Save output
            output_path = None
            if self.logs_dir:
                output_path = str(self.logs_dir / f"{name}.log")
                with open(output_path, "w") as f:
                    f.write(f"=== STDOUT ===\n{stdout.decode()}\n")
                    f.write(f"=== STDERR ===\n{stderr.decode()}\n")

            # Extract failure summary
            failure_summary = None
            if not passed:
                failure_summary = self._extract_failure_summary(
                    stdout.decode(),
                    stderr.decode(),
                )

            logger.info(
                "Gate completed",
                gate=name,
                passed=passed,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

            return GateResult(
                name=name,
                passed=passed,
                exit_code=exit_code,
                duration_ms=duration_ms,
                output_path=output_path,
                failure_summary=failure_summary,
                attempt=attempt,
            )

        except asyncio.TimeoutError:
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error("Gate timed out", gate=name, timeout=timeout)

            return GateResult(
                name=name,
                passed=False,
                exit_code=-1,
                duration_ms=duration_ms,
                failure_summary=f"Timeout after {timeout}s",
                attempt=attempt,
            )

    async def run_all_gates(
        self,
        cwd: Path,
        gates: dict[str, str] | list[GateConfig],
    ) -> dict[str, GateResult]:
        """
        Run all configured quality gates.

        Gates are run sequentially to fail fast.
        """
        results: dict[str, GateResult] = {}

        # Convert dict to GateConfig if needed
        if isinstance(gates, dict):
            gate_configs = [
                GateConfig(name=name, command=cmd)
                for name, cmd in gates.items()
            ]
        else:
            gate_configs = gates

        for gate in gate_configs:
            result = await self.run_gate_async(
                name=gate.name,
                command=gate.command,
                cwd=cwd,
                timeout=gate.timeout,
            )

            results[gate.name] = result

            # Retry if failed and retries configured
            if not result.passed and gate.retries > 1:
                for attempt in range(2, gate.retries + 1):
                    logger.info(
                        "Retrying gate",
                        gate=gate.name,
                        attempt=attempt,
                        max_attempts=gate.retries,
                    )

                    result = await self.run_gate_async(
                        name=gate.name,
                        command=gate.command,
                        cwd=cwd,
                        timeout=gate.timeout,
                        attempt=attempt,
                    )

                    results[gate.name] = result

                    if result.passed:
                        # Mark as flaky if passed on retry
                        result.flaky_detected = True
                        break

        return results

    def _extract_failure_summary(self, stdout: str, stderr: str) -> str:
        """Extract a summary of the failure from output."""
        # Look for common patterns
        lines: list[str] = []

        # Check stderr first
        for line in stderr.split("\n"):
            line = line.strip()
            if any(
                pattern in line.lower()
                for pattern in ["error", "failed", "failure", "exception"]
            ):
                lines.append(line)
                if len(lines) >= 5:
                    break

        # If nothing in stderr, check stdout
        if not lines:
            for line in stdout.split("\n"):
                line = line.strip()
                if any(
                    pattern in line.lower()
                    for pattern in ["error", "failed", "failure", "exception"]
                ):
                    lines.append(line)
                    if len(lines) >= 5:
                        break

        if lines:
            return "\n".join(lines)

        # Default: last few lines
        all_lines = (stdout + stderr).strip().split("\n")
        return "\n".join(all_lines[-5:])

