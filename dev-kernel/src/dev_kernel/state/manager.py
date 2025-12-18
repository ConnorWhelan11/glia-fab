"""
StateManager - Atomic read/write operations for Beads state.

Responsibilities:
- Read issues and dependencies from Beads
- Update issue status atomically
- Create new issues (e.g., fix issues)
- Add dependency edges
- Log events for observability

Supports two modes:
1. bd CLI (preferred) - uses Beads CLI commands
2. Direct file parsing (fallback) - reads .beads/*.jsonl files directly
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

from dev_kernel.state.models import BeadsGraph, Dep, Issue

if TYPE_CHECKING:
    from dev_kernel.kernel.config import KernelConfig

logger = structlog.get_logger()


class StateManager:
    """
    Manages Beads state with atomic operations.

    Supports both bd CLI and direct file access modes.
    """

    def __init__(
        self,
        config: KernelConfig | None = None,
        repo_root: Path | None = None,
    ) -> None:
        if config:
            self.repo_root = config.repo_root
            self.config = config
        elif repo_root:
            self.repo_root = repo_root
            self.config = None
        else:
            self.repo_root = Path.cwd()
            self.config = None

        self.beads_dir = self.repo_root / ".beads"
        self.logs_dir = self.repo_root / ".dev-kernel" / "logs"
        self._bd_available: bool | None = None

    @property
    def bd_available(self) -> bool:
        """Check if bd CLI is available."""
        if self._bd_available is None:
            self._bd_available = shutil.which("bd") is not None
        return self._bd_available

    def load_graph(self) -> BeadsGraph:
        """
        Load the full Beads work graph.

        Tries bd CLI first, falls back to direct file parsing.
        """
        issues = self._load_issues()
        deps = self._load_deps()

        logger.info(
            "Loaded Beads graph",
            issues=len(issues),
            deps=len(deps),
            mode="cli" if self.bd_available else "file",
        )

        return BeadsGraph(issues=issues, deps=deps)

    def get_ready_issues(self) -> list[Issue]:
        """
        Get issues that are ready to work on.

        An issue is ready when:
        - status is 'open' or 'ready'
        - all blocking dependencies are 'done'
        """
        if self.bd_available:
            result = subprocess.run(
                ["bd", "ready", "--json"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    return [Issue.from_dict(item) for item in data]
                except json.JSONDecodeError:
                    pass

        # Fallback: compute ready set from graph
        graph = self.load_graph()
        ready: list[Issue] = []

        for issue in graph.issues:
            if issue.status not in ("open", "ready"):
                continue

            blockers = graph.get_blocking_deps(issue.id)
            if all(b.status == "done" for b in blockers):
                ready.append(issue)

        return ready

    def update_issue(
        self,
        issue_id: str,
        status: str | None = None,
        tags: list[str] | None = None,
        **fields: str,
    ) -> bool:
        """
        Update an issue atomically.

        Uses bd CLI if available, otherwise updates file directly.
        """
        if self.bd_available:
            return self._update_issue_via_cli(issue_id, status, tags, **fields)

        return self._update_issue_via_file(issue_id, status, tags, **fields)

    def create_issue(
        self,
        title: str,
        description: str | None = None,
        priority: str = "P2",
        tags: list[str] | None = None,
    ) -> str | None:
        """
        Create a new issue.

        Returns the new issue ID or None on failure.
        """
        if self.bd_available:
            return self._create_issue_via_cli(title, description, priority, tags)

        return self._create_issue_via_file(title, description, priority, tags)

    def close_issue(self, issue_id: str) -> bool:
        """Close an issue."""
        return self.update_issue(issue_id, status="done")

    def add_dep(
        self,
        from_id: str,
        to_id: str,
        dep_type: str = "blocks",
    ) -> bool:
        """
        Add a dependency edge between issues.
        """
        if self.bd_available:
            return self._add_dep_via_cli(from_id, to_id, dep_type)

        return self._add_dep_via_file(from_id, to_id, dep_type)

    # ===== Issue Loading =====

    def _load_issues(self) -> list[Issue]:
        """Load all issues from Beads."""
        # Try bd CLI first
        if self.bd_available:
            issues = self._load_issues_via_cli()
            if issues:
                return issues

        # Fall back to direct file parsing
        return self._load_issues_from_files()

    def _load_issues_via_cli(self) -> list[Issue]:
        """Load issues via bd CLI."""
        result = subprocess.run(
            ["bd", "list", "--json"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.debug("bd list failed", error=result.stderr)
            return []

        try:
            data = json.loads(result.stdout)
            return [Issue.from_dict(item) for item in data]
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse bd list output", error=str(e))
            return []

    def _load_issues_from_files(self) -> list[Issue]:
        """Load issues directly from .beads files."""
        issues: list[Issue] = []

        # Try issues.jsonl (JSON Lines format)
        jsonl_file = self.beads_dir / "issues.jsonl"
        if jsonl_file.exists():
            issues.extend(self._parse_jsonl_file(jsonl_file, Issue.from_dict))
            if issues:
                return issues

        # Try issues.yaml / issues.yml
        for ext in ("yaml", "yml"):
            yaml_file = self.beads_dir / f"issues.{ext}"
            if yaml_file.exists():
                issues.extend(self._parse_yaml_file(yaml_file, Issue.from_dict))
                if issues:
                    return issues

        # Try individual issue files in issues/ directory
        issues_dir = self.beads_dir / "issues"
        if issues_dir.exists() and issues_dir.is_dir():
            for path in issues_dir.iterdir():
                if path.suffix in (".json", ".yaml", ".yml"):
                    issue = self._parse_single_issue_file(path)
                    if issue:
                        issues.append(issue)

        return issues

    def _parse_jsonl_file(self, path: Path, factory: callable) -> list:
        """Parse a JSON Lines file."""
        items = []

        try:
            with open(path) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        data = json.loads(line)
                        items.append(factory(data))
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Invalid JSON line",
                            file=str(path),
                            line=line_num,
                            error=str(e),
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to parse item",
                            file=str(path),
                            line=line_num,
                            error=str(e),
                        )
        except OSError as e:
            logger.warning("Failed to read file", file=str(path), error=str(e))

        return items

    def _parse_yaml_file(self, path: Path, factory: callable) -> list:
        """Parse a YAML file containing a list of items."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if isinstance(data, list):
                return [factory(item) for item in data if isinstance(item, dict)]
            elif isinstance(data, dict) and "issues" in data:
                return [factory(item) for item in data["issues"] if isinstance(item, dict)]

        except yaml.YAMLError as e:
            logger.warning("Invalid YAML", file=str(path), error=str(e))
        except OSError as e:
            logger.warning("Failed to read file", file=str(path), error=str(e))

        return []

    def _parse_single_issue_file(self, path: Path) -> Issue | None:
        """Parse a single issue file (JSON or YAML)."""
        try:
            with open(path) as f:
                if path.suffix == ".json":
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)

            if isinstance(data, dict):
                # Use filename (without extension) as ID if not present
                if "id" not in data:
                    data["id"] = path.stem
                return Issue.from_dict(data)

        except (json.JSONDecodeError, yaml.YAMLError) as e:
            logger.warning("Invalid issue file", file=str(path), error=str(e))
        except OSError as e:
            logger.warning("Failed to read file", file=str(path), error=str(e))

        return None

    # ===== Dependency Loading =====

    def _load_deps(self) -> list[Dep]:
        """Load dependencies from Beads."""
        deps: list[Dep] = []

        # Try deps.jsonl
        jsonl_file = self.beads_dir / "deps.jsonl"
        if jsonl_file.exists():
            deps = self._parse_jsonl_file(jsonl_file, Dep.from_dict)
            if deps:
                return deps

        # Try deps.yaml / deps.yml
        for ext in ("yaml", "yml"):
            yaml_file = self.beads_dir / f"deps.{ext}"
            if yaml_file.exists():
                deps = self._parse_deps_yaml(yaml_file)
                if deps:
                    return deps

        return deps

    def _parse_deps_yaml(self, path: Path) -> list[Dep]:
        """Parse a deps YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if isinstance(data, list):
                return [Dep.from_dict(item) for item in data if isinstance(item, dict)]
            elif isinstance(data, dict) and "deps" in data:
                return [Dep.from_dict(item) for item in data["deps"] if isinstance(item, dict)]

        except yaml.YAMLError as e:
            logger.warning("Invalid deps YAML", file=str(path), error=str(e))
        except OSError as e:
            logger.warning("Failed to read deps file", file=str(path), error=str(e))

        return []

    # ===== CLI-based Operations =====

    def _update_issue_via_cli(
        self,
        issue_id: str,
        status: str | None = None,
        tags: list[str] | None = None,
        **fields: str,
    ) -> bool:
        """Update issue via bd CLI."""
        cmd = ["bd", "update", issue_id]

        if status:
            cmd.extend(["--status", status])

        if tags:
            for tag in tags:
                cmd.extend(["--tag", tag])

        for key, value in fields.items():
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

        cmd.append("--json")

        result = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("Failed to update issue", issue_id=issue_id, error=result.stderr)
            return False

        logger.info("Issue updated", issue_id=issue_id, status=status)
        return True

    def _create_issue_via_cli(
        self,
        title: str,
        description: str | None = None,
        priority: str = "P2",
        tags: list[str] | None = None,
    ) -> str | None:
        """Create issue via bd CLI."""
        cmd = ["bd", "create", title]

        if description:
            cmd.extend(["--description", description])

        cmd.extend(["--priority", priority])

        if tags:
            for tag in tags:
                cmd.extend(["--tag", tag])

        cmd.append("--json")

        result = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("Failed to create issue", title=title, error=result.stderr)
            return None

        try:
            data = json.loads(result.stdout)
            issue_id = data.get("id")
            logger.info("Issue created", issue_id=issue_id, title=title)
            return issue_id
        except json.JSONDecodeError:
            logger.warning("Failed to parse create issue response")
            return None

    def _add_dep_via_cli(self, from_id: str, to_id: str, dep_type: str) -> bool:
        """Add dependency via bd CLI."""
        cmd = ["bd", "dep", "add", from_id, to_id, "--type", dep_type, "--json"]

        result = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(
                "Failed to add dependency",
                from_id=from_id,
                to_id=to_id,
                error=result.stderr,
            )
            return False

        logger.info("Dependency added", from_id=from_id, to_id=to_id, type=dep_type)
        return True

    # ===== File-based Operations =====

    def _update_issue_via_file(
        self,
        issue_id: str,
        status: str | None = None,
        tags: list[str] | None = None,
        **fields: str,
    ) -> bool:
        """Update issue directly in file."""
        jsonl_file = self.beads_dir / "issues.jsonl"

        if not jsonl_file.exists():
            logger.error("issues.jsonl not found", path=str(jsonl_file))
            return False

        # Read all issues
        issues_data: list[dict] = []
        found = False

        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == issue_id:
                        found = True
                        if status:
                            data["status"] = status
                        if tags:
                            data["tags"] = list(set(data.get("tags", []) + tags))
                        for key, value in fields.items():
                            data[key] = value
                        data["updated"] = _utc_now().isoformat().replace("+00:00", "Z")
                    issues_data.append(data)
                except json.JSONDecodeError:
                    continue

        if not found:
            logger.error("Issue not found", issue_id=issue_id)
            return False

        # Write back atomically
        tmp_file = jsonl_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            for data in issues_data:
                f.write(json.dumps(data) + "\n")

        tmp_file.rename(jsonl_file)
        logger.info("Issue updated via file", issue_id=issue_id, status=status)
        return True

    def _create_issue_via_file(
        self,
        title: str,
        description: str | None = None,
        priority: str = "P2",
        tags: list[str] | None = None,
    ) -> str | None:
        """Create issue directly in file."""
        self.beads_dir.mkdir(parents=True, exist_ok=True)
        jsonl_file = self.beads_dir / "issues.jsonl"

        # Generate ID
        existing_ids = set()
        if jsonl_file.exists():
            with open(jsonl_file) as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if "id" in data:
                            existing_ids.add(data["id"])
                    except json.JSONDecodeError:
                        continue

        # Find next available ID
        issue_id = "1"
        counter = 1
        while issue_id in existing_ids:
            counter += 1
            issue_id = str(counter)

        # Create issue data
        now = _utc_now().isoformat().replace("+00:00", "Z")
        issue_data = {
            "id": issue_id,
            "title": title,
            "status": "open",
            "created": now,
            "updated": now,
            "dk_priority": priority,
        }

        if description:
            issue_data["description"] = description

        if tags:
            issue_data["tags"] = tags

        # Append to file
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(issue_data) + "\n")

        logger.info("Issue created via file", issue_id=issue_id, title=title)
        return issue_id

    def _add_dep_via_file(self, from_id: str, to_id: str, dep_type: str) -> bool:
        """Add dependency directly to file."""
        self.beads_dir.mkdir(parents=True, exist_ok=True)
        deps_file = self.beads_dir / "deps.jsonl"

        now = _utc_now().isoformat().replace("+00:00", "Z")
        dep_data = {
            "from": from_id,
            "to": to_id,
            "type": dep_type,
            "created": now,
        }

        with open(deps_file, "a") as f:
            f.write(json.dumps(dep_data) + "\n")

        logger.info("Dependency added via file", from_id=from_id, to_id=to_id, type=dep_type)
        return True

    # ===== Alias Methods =====

    def load_beads_graph(self) -> BeadsGraph:
        """Alias for load_graph - used by runner."""
        return self.load_graph()

    def update_issue_status(self, issue_id: str, status: str) -> bool:
        """Update just the status of an issue."""
        return self.update_issue(issue_id, status=status)

    def increment_attempts(self, issue_id: str) -> int:
        """
        Increment the attempt counter for an issue.

        Returns the new attempt count.
        """
        graph = self.load_graph()
        issue = graph.get_issue(issue_id)

        if not issue:
            return 0

        new_attempts = issue.dk_attempts + 1
        self.update_issue(issue_id, dk_attempts=str(new_attempts))
        return new_attempts

    def add_event(
        self,
        issue_id: str | None,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to the event log."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        events_file = self.logs_dir / "events.jsonl"

        event = {
            "type": event_type,
            "timestamp": _utc_now().isoformat().replace("+00:00", "Z"),
            "issue_id": issue_id,
            "data": data or {},
        }

        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        logger.debug("Event logged", event_type=event_type, issue_id=issue_id)
