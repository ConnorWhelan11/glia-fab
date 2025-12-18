"""
Stats - Display kernel statistics.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from dev_kernel.kernel.config import KernelConfig

console = Console()


def show_stats(
    config_path: Path,
    show_cost: bool = False,
    show_success_rate: bool = False,
    show_timing: bool = False,
) -> None:
    """Show kernel statistics."""
    config = KernelConfig.load(config_path)
    events = _load_all_events(config)

    if not events:
        console.print("[dim]No statistics available yet[/dim]")
        return

    console.print("\n[bold blue]Dev Kernel Statistics[/bold blue]\n")

    # Overall stats
    total_runs = len([e for e in events if e.get("type") == "cycle_start"])
    total_tasks = len([e for e in events if e.get("type") == "task_complete"])
    total_failures = len([e for e in events if e.get("type") == "task_failed"])

    console.print(f"[dim]Total Runs:[/dim] {total_runs}")
    console.print(f"[dim]Tasks Completed:[/dim] {total_tasks}")
    console.print(f"[dim]Tasks Failed:[/dim] {total_failures}")

    if show_success_rate:
        _show_success_rates(events)

    if show_cost:
        _show_cost_breakdown(events)

    if show_timing:
        _show_timing_analysis(events)


def _load_all_events(config: KernelConfig) -> list[dict]:
    """Load all events from logs."""
    logs_dir = config.repo_root / ".dev-kernel" / "logs"

    if not logs_dir.exists():
        return []

    events = []
    events_file = logs_dir / "events.jsonl"

    if events_file.exists():
        with open(events_file) as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

    return events


def _show_success_rates(events: list[dict]) -> None:
    """Show success rates by toolchain."""
    console.print("\n[bold]Success Rates by Toolchain[/bold]")

    by_toolchain: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})

    for event in events:
        if event.get("type") in ("task_complete", "task_failed"):
            toolchain = event.get("data", {}).get("toolchain", "unknown")
            by_toolchain[toolchain]["total"] += 1
            if event.get("type") == "task_complete":
                by_toolchain[toolchain]["success"] += 1

    table = Table()
    table.add_column("Toolchain", style="cyan")
    table.add_column("Success", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Rate", justify="right")

    for toolchain, stats in sorted(by_toolchain.items()):
        rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        rate_style = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"
        table.add_row(
            toolchain,
            str(stats["success"]),
            str(stats["total"]),
            f"[{rate_style}]{rate:.1f}%[/{rate_style}]",
        )

    console.print(table)


def _show_cost_breakdown(events: list[dict]) -> None:
    """Show token/cost breakdown."""
    console.print("\n[bold]Token Usage[/bold]")

    total_tokens = 0
    by_toolchain: dict[str, int] = defaultdict(int)

    for event in events:
        data = event.get("data", {})
        tokens = data.get("tokens_used", 0)
        if tokens:
            total_tokens += tokens
            toolchain = data.get("toolchain", "unknown")
            by_toolchain[toolchain] += tokens

    console.print(f"[dim]Total Tokens:[/dim] {total_tokens:,}")

    if by_toolchain:
        table = Table()
        table.add_column("Toolchain", style="cyan")
        table.add_column("Tokens", justify="right")
        table.add_column("Est. Cost", justify="right")

        for toolchain, tokens in sorted(by_toolchain.items(), key=lambda x: -x[1]):
            # Rough cost estimate ($0.01 per 1K tokens)
            cost = tokens / 1000 * 0.01
            table.add_row(toolchain, f"{tokens:,}", f"${cost:.2f}")

        console.print(table)


def _show_timing_analysis(events: list[dict]) -> None:
    """Show timing analysis."""
    console.print("\n[bold]Timing Analysis[/bold]")

    durations: list[int] = []
    by_size: dict[str, list[int]] = defaultdict(list)

    for event in events:
        if event.get("type") == "task_complete":
            data = event.get("data", {})
            duration = data.get("duration_ms")
            if duration:
                durations.append(duration)
                size = data.get("size", "M")
                by_size[size].append(duration)

    if durations:
        avg_ms = sum(durations) / len(durations)
        console.print(f"[dim]Average Duration:[/dim] {avg_ms / 1000:.1f}s")
        console.print(f"[dim]Min:[/dim] {min(durations) / 1000:.1f}s")
        console.print(f"[dim]Max:[/dim] {max(durations) / 1000:.1f}s")

        if by_size:
            table = Table()
            table.add_column("Size")
            table.add_column("Avg Duration", justify="right")
            table.add_column("Count", justify="right")

            for size in ["XS", "S", "M", "L", "XL"]:
                if size in by_size:
                    times = by_size[size]
                    avg = sum(times) / len(times)
                    table.add_row(size, f"{avg / 1000:.1f}s", str(len(times)))

            console.print(table)

