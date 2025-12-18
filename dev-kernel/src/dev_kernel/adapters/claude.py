"""
Claude Code Adapter - Anthropic Claude Code toolchain integration.

https://github.com/anthropics/claude-code
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from dev_kernel.adapters.base import CostEstimate, PatchProof, ToolchainAdapter

logger = structlog.get_logger()


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ClaudeAdapter(ToolchainAdapter):
    """
    Adapter for Claude Code CLI.

    Claude Code is an agentic coding tool that can:
    - Understand and navigate codebases
    - Make changes across multiple files
    - Run commands and verify changes
    """

    name = "claude"
    supports_mcp = True
    supports_streaming = True

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.default_model = self.config.get("model", "claude-sonnet-4-20250514")
        self.skip_permissions = self.config.get("skip_permissions", True)
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        """Check if claude CLI is available."""
        if self._available is None:
            self._available = shutil.which("claude") is not None
        return self._available

    def execute_sync(
        self,
        manifest: dict,
        workcell_path: Path,
        timeout_seconds: int = 1800,
    ) -> PatchProof:
        """
        Execute task synchronously using Claude CLI.
        """
        started_at = _utc_now()
        workcell_id = manifest.get("workcell_id", "unknown")
        issue_id = manifest.get("issue", {}).get("id", "unknown")

        # Ensure logs directory exists
        logs_dir = workcell_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Build and write prompt
        prompt = self._build_prompt(manifest)
        prompt_file = workcell_path / "prompt.md"
        prompt_file.write_text(prompt)

        # Get configuration
        model = manifest.get("toolchain_config", {}).get("model", self.default_model)

        # Build command
        cmd = self._build_command(prompt_file, model)

        logger.info(
            "Executing Claude",
            workcell_id=workcell_id,
            issue_id=issue_id,
            model=model,
        )

        try:
            result = subprocess.run(
                cmd,
                cwd=workcell_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Save logs
            self._save_logs(logs_dir, result.stdout, result.stderr)

            # Parse and return proof
            proof = self._parse_output(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                manifest=manifest,
                workcell_path=workcell_path,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

            # Write proof to file
            proof_path = workcell_path / "proof.json"
            proof_path.write_text(json.dumps(proof.to_dict(), indent=2))

            logger.info(
                "Claude execution completed",
                workcell_id=workcell_id,
                status=proof.status,
                duration_ms=duration_ms,
            )

            return proof

        except subprocess.TimeoutExpired:
            logger.error(
                "Claude execution timed out",
                workcell_id=workcell_id,
                timeout=timeout_seconds,
            )
            return self._create_timeout_proof(manifest, started_at)

        except Exception as e:
            logger.error(
                "Claude execution failed",
                workcell_id=workcell_id,
                error=str(e),
            )
            return self._create_error_proof(manifest, started_at, str(e))

    async def execute(
        self,
        manifest: dict,
        workcell_path: Path,
        timeout: timedelta,
    ) -> PatchProof:
        """Execute task asynchronously using Claude CLI."""
        started_at = _utc_now()
        workcell_id = manifest.get("workcell_id", "unknown")

        # Ensure logs directory exists
        logs_dir = workcell_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Build and write prompt
        prompt = self._build_prompt(manifest)
        prompt_file = workcell_path / "prompt.md"
        prompt_file.write_text(prompt)

        # Get configuration
        model = manifest.get("toolchain_config", {}).get("model", self.default_model)

        # Build command
        cmd = self._build_command(prompt_file, model)

        logger.info(
            "Executing Claude (async)",
            workcell_id=workcell_id,
            model=model,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workcell_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout.total_seconds(),
            )

            completed_at = _utc_now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # Save logs
            self._save_logs(logs_dir, stdout.decode(), stderr.decode())

            proof = self._parse_output(
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=process.returncode or 0,
                manifest=manifest,
                workcell_path=workcell_path,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

            # Write proof to file
            proof_path = workcell_path / "proof.json"
            proof_path.write_text(json.dumps(proof.to_dict(), indent=2))

            return proof

        except asyncio.TimeoutError:
            logger.error("Claude execution timed out", workcell_id=workcell_id)
            return self._create_timeout_proof(manifest, started_at)

        except Exception as e:
            logger.error(
                "Claude execution failed", workcell_id=workcell_id, error=str(e)
            )
            return self._create_error_proof(manifest, started_at, str(e))

    async def health_check(self) -> bool:
        """Check if Claude CLI is available."""
        if not self.available:
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    def health_check_sync(self) -> bool:
        """Check if Claude CLI is available (sync version)."""
        if not self.available:
            return False

        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def estimate_cost(self, manifest: dict) -> CostEstimate:
        """Estimate cost for Claude execution."""
        model = manifest.get("toolchain_config", {}).get("model", self.default_model)
        estimated_tokens = manifest.get("issue", {}).get("dk_estimated_tokens", 50000)

        # Cost per 1M tokens (input + output combined estimate)
        cost_per_1m = {
            "claude-sonnet-4-20250514": 9.0,
            "claude-opus-4-20250514": 45.0,
            "claude-3-5-sonnet-20241022": 9.0,
            "claude-3-opus-20240229": 45.0,
            "claude-3-sonnet-20240229": 9.0,
            "claude-3-haiku-20240307": 0.75,
        }.get(model, 9.0)

        estimated_cost = (estimated_tokens / 1_000_000) * cost_per_1m

        return CostEstimate(
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost,
            model=model,
        )

    def _build_command(self, prompt_file: Path, model: str) -> list[str]:
        """Build the claude command."""
        cmd = ["claude"]

        # Add prompt
        cmd.extend(["--print", f"@{prompt_file}"])

        # Add model if specified
        if model:
            cmd.extend(["--model", model])

        # Skip permissions for autonomous mode
        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        return cmd

    def _save_logs(self, logs_dir: Path, stdout: str, stderr: str) -> None:
        """Save stdout and stderr to log files."""
        if stdout:
            (logs_dir / "claude-stdout.log").write_text(stdout)
        if stderr:
            (logs_dir / "claude-stderr.log").write_text(stderr)

    def _parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        manifest: dict,
        workcell_path: Path,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: int,
    ) -> PatchProof:
        """Parse Claude output into PatchProof."""
        workcell_id = manifest.get("workcell_id", "unknown")
        issue_id = manifest.get("issue", {}).get("id", "unknown")

        # Try to extract any JSON from output
        claude_output: dict = {}
        if stdout.strip():
            for line in reversed(stdout.strip().split("\n")):
                try:
                    claude_output = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        # Get git patch info
        patch_info = self._get_patch_info(workcell_path, manifest)

        # Determine status
        if exit_code == 0:
            status = "success"
            confidence = claude_output.get("confidence", 0.8)
        elif exit_code == 1:
            status = "partial"
            confidence = claude_output.get("confidence", 0.5)
        else:
            status = "failed"
            confidence = claude_output.get("confidence", 0.2)

        return PatchProof(
            schema_version="1.0.0",
            workcell_id=workcell_id,
            issue_id=issue_id,
            status=status,
            patch=patch_info,
            verification={
                "gates": {},
                "all_passed": False,
                "blocking_failures": [],
            },
            metadata={
                "toolchain": self.name,
                "toolchain_version": claude_output.get("version", "unknown"),
                "model": manifest.get("toolchain_config", {}).get(
                    "model", self.default_model
                ),
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
                "duration_ms": duration_ms,
                "exit_code": exit_code,
                "tokens_used": claude_output.get("tokens_used"),
                "cost_usd": claude_output.get("cost"),
            },
            commands_executed=[
                {
                    "command": "claude",
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "stdout_path": str(workcell_path / "logs" / "claude-stdout.log"),
                    "stderr_path": str(workcell_path / "logs" / "claude-stderr.log"),
                }
            ],
            confidence=confidence,
            risk_classification=self._classify_risk(patch_info),
        )

    def _get_patch_info(self, workcell_path: Path, manifest: dict) -> dict:
        """Get git patch information."""
        # Get base commit
        base_result = subprocess.run(
            ["git", "merge-base", "main", "HEAD"],
            cwd=workcell_path,
            capture_output=True,
            text=True,
        )
        base_commit = base_result.stdout.strip() if base_result.returncode == 0 else ""

        # Get HEAD commit
        head_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workcell_path,
            capture_output=True,
            text=True,
        )
        head_commit = head_result.stdout.strip() if head_result.returncode == 0 else ""

        # Get diff stats
        stat_result = subprocess.run(
            ["git", "diff", "--stat", "main...HEAD"],
            cwd=workcell_path,
            capture_output=True,
            text=True,
        )

        files_changed, insertions, deletions = self._parse_diff_stats(
            stat_result.stdout
        )

        # Get modified files
        files_result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=workcell_path,
            capture_output=True,
            text=True,
        )
        files_modified = (
            [f for f in files_result.stdout.strip().split("\n") if f]
            if files_result.returncode == 0 and files_result.stdout.strip()
            else []
        )

        # Check forbidden paths
        forbidden = manifest.get("issue", {}).get("forbidden_paths", [])
        violations = self._check_forbidden_paths(files_modified, forbidden)

        return {
            "branch": manifest.get("branch_name", ""),
            "base_commit": base_commit,
            "head_commit": head_commit,
            "diff_stats": {
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions,
            },
            "files_modified": files_modified,
            "forbidden_path_violations": violations,
        }

    def _parse_diff_stats(self, stat_output: str) -> tuple[int, int, int]:
        """Parse git diff --stat output."""
        import re

        if not stat_output:
            return 0, 0, 0

        lines = stat_output.strip().split("\n")
        if not lines:
            return 0, 0, 0

        summary = lines[-1]
        files_match = re.search(r"(\d+) files? changed", summary)
        ins_match = re.search(r"(\d+) insertions?", summary)
        del_match = re.search(r"(\d+) deletions?", summary)

        return (
            int(files_match.group(1)) if files_match else 0,
            int(ins_match.group(1)) if ins_match else 0,
            int(del_match.group(1)) if del_match else 0,
        )

    def _check_forbidden_paths(
        self, files_modified: list[str], forbidden: list[str]
    ) -> list[str]:
        """Check for forbidden path violations."""
        violations = []
        for file in files_modified:
            for pattern in forbidden:
                if pattern.endswith("/"):
                    if file.startswith(pattern):
                        violations.append(file)
                elif pattern.endswith("*"):
                    if file.startswith(pattern[:-1]):
                        violations.append(file)
                else:
                    if file == pattern or file.startswith(pattern + "/"):
                        violations.append(file)
        return violations

    def _classify_risk(self, patch_info: dict) -> str:
        """Classify risk based on changes."""
        if patch_info.get("forbidden_path_violations"):
            return "critical"

        files = patch_info.get("files_modified", [])
        high_risk_patterns = [
            "auth",
            "security",
            "password",
            "secret",
            "key",
            "migration",
            "schema",
            "database",
            "payment",
            "billing",
        ]

        for file in files:
            file_lower = file.lower()
            if any(pattern in file_lower for pattern in high_risk_patterns):
                return "high"

        stats = patch_info.get("diff_stats", {})
        total_changes = stats.get("insertions", 0) + stats.get("deletions", 0)

        if total_changes > 500:
            return "high"
        elif total_changes > 100:
            return "medium"

        return "low"

    def _create_timeout_proof(self, manifest: dict, started_at: datetime) -> PatchProof:
        """Create a proof for timeout case."""
        completed_at = _utc_now()
        return PatchProof(
            schema_version="1.0.0",
            workcell_id=manifest.get("workcell_id", "unknown"),
            issue_id=manifest.get("issue", {}).get("id", "unknown"),
            status="timeout",
            patch={
                "branch": manifest.get("branch_name", ""),
                "base_commit": "",
                "head_commit": "",
                "diff_stats": {"files_changed": 0, "insertions": 0, "deletions": 0},
                "files_modified": [],
                "forbidden_path_violations": [],
            },
            verification={
                "gates": {},
                "all_passed": False,
                "blocking_failures": ["timeout"],
            },
            metadata={
                "toolchain": self.name,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
                "error": "Execution timed out",
            },
            confidence=0,
            risk_classification="high",
        )

    def _create_error_proof(
        self, manifest: dict, started_at: datetime, error: str
    ) -> PatchProof:
        """Create a proof for error case."""
        completed_at = _utc_now()
        return PatchProof(
            schema_version="1.0.0",
            workcell_id=manifest.get("workcell_id", "unknown"),
            issue_id=manifest.get("issue", {}).get("id", "unknown"),
            status="error",
            patch={
                "branch": manifest.get("branch_name", ""),
                "base_commit": "",
                "head_commit": "",
                "diff_stats": {"files_changed": 0, "insertions": 0, "deletions": 0},
                "files_modified": [],
                "forbidden_path_violations": [],
            },
            verification={
                "gates": {},
                "all_passed": False,
                "blocking_failures": ["error"],
            },
            metadata={
                "toolchain": self.name,
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
                "error": error,
            },
            confidence=0,
            risk_classification="high",
        )
