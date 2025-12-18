"""
History - Display run history and events.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from dev_kernel.kernel.config import KernelConfig

console = Console()


def show_history(
    config_path: Path,
    run_id: str | None = None,
    issue_id: str | None = None,
    limit: int = 50,
    json_output: bool = False,
) -> None:
    """Show run history."""
    config = KernelConfig.load(config_path)
    events = _load_events(config, run_id=run_id, issue_id=issue_id, limit=limit)

    if json_output:
        console.print(json.dumps(events, indent=2))
        return

    if not events:
        console.print("[dim]No history found[/dim]")
        return

    table = Table(title="Run History")
    table.add_column("Time", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Issue")
    table.add_column("Details")

    for event in events:
        timestamp = event.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp = dt.strftime("%m-%d %H:%M")
            except ValueError:
                pass

        event_type = event.get("type", "unknown")
        issue = event.get("issue_id", "-")
        details = _format_details(event.get("data", {}))

        table.add_row(timestamp, event_type, f"#{issue}" if issue != "-" else "-", details)

    console.print(table)


def _load_events(
    config: KernelConfig,
    run_id: str | None = None,
    issue_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Load events from log files."""
    logs_dir = config.repo_root / ".dev-kernel" / "logs"

    if not logs_dir.exists():
        return []

    events = []

    # Load from events.jsonl
    events_file = logs_dir / "events.jsonl"
    if events_file.exists():
        with open(events_file) as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    events.append(event)
                except json.JSONDecodeError:
                    continue

    # Filter
    if run_id:
        events = [e for e in events if e.get("run_id") == run_id]
    if issue_id:
        events = [e for e in events if e.get("issue_id") == issue_id]

    # Sort by timestamp (newest first) and limit
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events[:limit]


def _format_details(data: dict) -> str:
    """Format event data for display."""
    if not data:
        return "-"

    # Pick interesting fields
    parts = []
    for key in ["status", "reason", "toolchain", "duration_ms"]:
        if key in data:
            parts.append(f"{key}={data[key]}")

    return ", ".join(parts) if parts else str(data)[:40]

