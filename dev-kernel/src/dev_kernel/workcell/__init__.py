"""
Workcell - Isolated execution environment management.

Modules:
    manager     - Create, cleanup, list workcells (git worktrees)
    isolation   - Sandboxing and security
    cli         - Workcell CLI entry point
    cleanup     - Workcell cleanup logic
    list        - List active workcells
"""

from dev_kernel.workcell.manager import WorkcellManager

__all__ = ["WorkcellManager"]

