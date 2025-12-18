"""
Dev Kernel CLI - Main entry point for the orchestrator.

Commands:
    init        Initialize kernel in repo
    run         Run the kernel loop
    status      Show kernel status
    workcells   List active workcells
    history     Show run history
    stats       Show statistics
    flaky-tests Manage flaky tests
    escalate    Manual escalation
    cleanup     Cleanup workcells
"""

import click
from pathlib import Path
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option("--config", "-c", type=Path, help="Path to config file")
@click.pass_context
def main(ctx: click.Context, config: Path | None) -> None:
    """Dev Kernel - Autonomous Multi-Agent Development Orchestrator"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config or Path(".dev-kernel/config.yaml")


@main.command()
@click.option("--config", type=Path, help="Path to config file (default: .dev-kernel/config.yaml)")
@click.pass_context
def init(ctx: click.Context, config: Path | None) -> None:
    """Initialize kernel in repo."""
    from dev_kernel.kernel.init import initialize_kernel
    
    config_path = config or ctx.obj["config_path"]
    initialize_kernel(config_path)
    console.print("[green]✓[/green] Dev Kernel initialized")


@main.command()
@click.option("--once", is_flag=True, help="Process one cycle and exit")
@click.option("--issue", type=str, help="Run specific issue only")
@click.option("--max-concurrent", type=int, help="Override max concurrent workcells")
@click.option("--speculate", is_flag=True, help="Force speculate mode")
@click.option("--dry-run", is_flag=True, help="Show what would happen without executing")
@click.option("--watch", is_flag=True, help="Continuous mode (re-run on Beads changes)")
@click.pass_context
def run(
    ctx: click.Context,
    once: bool,
    issue: str | None,
    max_concurrent: int | None,
    speculate: bool,
    dry_run: bool,
    watch: bool,
) -> None:
    """Run the kernel loop."""
    from dev_kernel.kernel.runner import KernelRunner
    
    runner = KernelRunner(
        config_path=ctx.obj["config_path"],
        single_cycle=once,
        target_issue=issue,
        max_concurrent=max_concurrent,
        force_speculate=speculate,
        dry_run=dry_run,
        watch_mode=watch,
    )
    runner.run()


@main.command()
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.option("--verbose", "-v", is_flag=True, help="Include workcell details")
@click.pass_context
def status(ctx: click.Context, as_json: bool, verbose: bool) -> None:
    """Show kernel status."""
    from dev_kernel.kernel.status import show_status
    
    show_status(ctx.obj["config_path"], json_output=as_json, verbose=verbose)


@main.command()
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.option("--all", "show_all", is_flag=True, help="Include completed/archived")
@click.pass_context
def workcells(ctx: click.Context, as_json: bool, show_all: bool) -> None:
    """List active workcells."""
    from dev_kernel.workcell.list import list_workcells
    
    list_workcells(ctx.obj["config_path"], json_output=as_json, include_archived=show_all)


@main.command()
@click.option("--run", "run_id", type=str, help="Specific run")
@click.option("--issue", type=str, help="Specific issue")
@click.option("--limit", type=int, default=50, help="Last N events")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.pass_context
def history(
    ctx: click.Context,
    run_id: str | None,
    issue: str | None,
    limit: int,
    as_json: bool,
) -> None:
    """Show run history."""
    from dev_kernel.observability.history import show_history
    
    show_history(
        ctx.obj["config_path"],
        run_id=run_id,
        issue_id=issue,
        limit=limit,
        json_output=as_json,
    )


@main.command()
@click.option("--cost", is_flag=True, help="Token/cost breakdown")
@click.option("--success-rate", is_flag=True, help="Per-toolchain success rates")
@click.option("--time", "timing", is_flag=True, help="Timing analysis")
@click.pass_context
def stats(ctx: click.Context, cost: bool, success_rate: bool, timing: bool) -> None:
    """Show statistics."""
    from dev_kernel.observability.stats import show_stats
    
    show_stats(
        ctx.obj["config_path"],
        show_cost=cost,
        show_success_rate=success_rate,
        show_timing=timing,
    )


@main.group()
def flaky_tests() -> None:
    """Manage flaky tests."""
    pass


@flaky_tests.command(name="list")
@click.pass_context
def flaky_list(ctx: click.Context) -> None:
    """List known flaky tests."""
    from dev_kernel.gates.flaky import list_flaky_tests
    
    list_flaky_tests(ctx.obj["config_path"])


@flaky_tests.command(name="ignore")
@click.argument("test_name")
@click.pass_context
def flaky_ignore(ctx: click.Context, test_name: str) -> None:
    """Ignore a flaky test."""
    from dev_kernel.gates.flaky import ignore_flaky_test
    
    ignore_flaky_test(ctx.obj["config_path"], test_name)


@flaky_tests.command(name="clear")
@click.pass_context
def flaky_clear(ctx: click.Context) -> None:
    """Clear flaky test data."""
    from dev_kernel.gates.flaky import clear_flaky_tests
    
    clear_flaky_tests(ctx.obj["config_path"])


@main.command()
@click.argument("issue_id")
@click.option("--reason", required=True, help="Reason for escalation")
@click.pass_context
def escalate(ctx: click.Context, issue_id: str, reason: str) -> None:
    """Manual escalation of an issue."""
    from dev_kernel.kernel.escalation import manual_escalate
    
    manual_escalate(ctx.obj["config_path"], issue_id, reason)
    console.print(f"[yellow]⚠[/yellow] Issue {issue_id} escalated: {reason}")


@main.command()
@click.option("--all", "remove_all", is_flag=True, help="Remove all workcells")
@click.option("--older-than", type=int, help="Remove workcells older than N days")
@click.option("--keep-logs", is_flag=True, help="Keep log archives")
@click.pass_context
def cleanup(
    ctx: click.Context,
    remove_all: bool,
    older_than: int | None,
    keep_logs: bool,
) -> None:
    """Cleanup workcells."""
    from dev_kernel.workcell.cleanup import cleanup_workcells
    
    count = cleanup_workcells(
        ctx.obj["config_path"],
        remove_all=remove_all,
        older_than_days=older_than,
        keep_logs=keep_logs,
    )
    console.print(f"[green]✓[/green] Cleaned up {count} workcells")


if __name__ == "__main__":
    main()

