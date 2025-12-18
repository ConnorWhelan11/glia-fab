"""
WorkcellManager - Creates and manages isolated git worktree execution environments.

Responsibilities:
- Create git worktrees for task isolation
- Manage workcell lifecycle
- Archive logs on cleanup
- Prevent cross-workcell contamination
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from dev_kernel.kernel.config import KernelConfig

logger = structlog.get_logger()


class WorkcellManager:
    """
    Manages isolated git worktree execution environments.
    """

    def __init__(self, config: KernelConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self.workcells_dir = repo_root / ".workcells"
        self.archives_dir = repo_root / ".dev-kernel" / "archives"

        # Ensure directories exist
        self.workcells_dir.mkdir(parents=True, exist_ok=True)
        self.archives_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        issue_id: str,
        speculate_tag: str | None = None,
    ) -> Path:
        """
        Create an isolated workcell (git worktree) for a task.

        Returns the path to the workcell directory.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        workcell_name = f"wc-{issue_id}-{timestamp}"
        branch_name = f"wc/{issue_id}/{timestamp}"
        workcell_path = self.workcells_dir / workcell_name

        logger.info(
            "Creating workcell",
            workcell_id=workcell_name,
            issue_id=issue_id,
            speculate_tag=speculate_tag,
        )

        # Create isolated worktree from main
        result = subprocess.run(
            [
                "git",
                "worktree",
                "add",
                str(workcell_path),
                "-b",
                branch_name,
                "main",
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

        # Remove .beads from workcell (kernel owns it)
        beads_path = workcell_path / ".beads"
        if beads_path.exists():
            shutil.rmtree(beads_path, ignore_errors=True)

        # Remove .dev-kernel from workcell
        dk_path = workcell_path / ".dev-kernel"
        if dk_path.exists():
            shutil.rmtree(dk_path, ignore_errors=True)

        # Create logs directory
        logs_path = workcell_path / "logs"
        logs_path.mkdir(parents=True, exist_ok=True)

        # Create isolation marker
        marker = {
            "id": workcell_name,
            "issue_id": issue_id,
            "created": timestamp,
            "parent_commit": self._get_main_head(),
            "speculate_tag": speculate_tag,
        }
        (workcell_path / ".workcell").write_text(json.dumps(marker, indent=2))

        logger.info(
            "Workcell created", workcell_id=workcell_name, path=str(workcell_path)
        )
        return workcell_path

    def cleanup(self, workcell_path: Path, keep_logs: bool = True) -> None:
        """
        Safely remove a workcell.

        Optionally archives logs before removal.
        """
        workcell_name = workcell_path.name

        logger.info(
            "Cleaning up workcell", workcell_id=workcell_name, keep_logs=keep_logs
        )

        # Archive logs if requested
        if keep_logs:
            self._archive_logs(workcell_path)

        # Get branch name from marker
        branch_name = self._get_branch_for_workcell(workcell_path)

        # Remove worktree
        result = subprocess.run(
            ["git", "worktree", "remove", "--force", str(workcell_path)],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(
                "Failed to remove worktree",
                workcell_id=workcell_name,
                error=result.stderr,
            )

        # Delete branch (best effort)
        if branch_name:
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=self.repo_root,
                capture_output=True,
            )

        logger.info("Workcell cleaned up", workcell_id=workcell_name)

    def list_active(self) -> list[Path]:
        """List all active workcells."""
        if not self.workcells_dir.exists():
            return []

        return [
            p
            for p in self.workcells_dir.iterdir()
            if p.is_dir() and (p / ".workcell").exists()
        ]

    def get_workcell_info(self, workcell_path: Path) -> dict | None:
        """Get metadata for a workcell."""
        marker_path = workcell_path / ".workcell"

        if not marker_path.exists():
            return None

        return json.loads(marker_path.read_text())

    def _get_main_head(self) -> str:
        """Get the current HEAD of main branch."""
        result = subprocess.run(
            ["git", "rev-parse", "main"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return "unknown"

        return result.stdout.strip()

    def _get_branch_for_workcell(self, workcell_path: Path) -> str | None:
        """Get the branch name for a workcell."""
        info = self.get_workcell_info(workcell_path)

        if not info:
            return None

        issue_id = info.get("issue_id")
        created = info.get("created")

        if issue_id and created:
            return f"wc/{issue_id}/{created}"

        return None

    def _archive_logs(self, workcell_path: Path) -> None:
        """
        Archive workcell logs recursively.

        This preserves the full directory structure including nested directories
        like logs/fab/ for render artifacts and critic reports.
        """
        workcell_name = workcell_path.name
        logs_path = workcell_path / "logs"

        if not logs_path.exists():
            return

        archive_path = self.archives_dir / workcell_name
        archive_path.mkdir(parents=True, exist_ok=True)

        # Copy entire logs directory recursively (preserves fab/ subdirectories)
        archive_logs_path = archive_path / "logs"
        if archive_logs_path.exists():
            shutil.rmtree(archive_logs_path)
        shutil.copytree(logs_path, archive_logs_path, dirs_exist_ok=True)

        # Also copy proof.json and manifest.json if they exist
        for filename in ["proof.json", "manifest.json", ".workcell"]:
            src = workcell_path / filename
            if src.exists():
                shutil.copy(src, archive_path)

        # Copy any render output directories that may exist at workcell root
        for dirname in ["renders", "output", "assets"]:
            src_dir = workcell_path / dirname
            if src_dir.exists() and src_dir.is_dir():
                dst_dir = archive_path / dirname
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

        logger.info(
            "Logs archived",
            workcell_id=workcell_name,
            archive=str(archive_path),
            preserved_structure=True,
        )
