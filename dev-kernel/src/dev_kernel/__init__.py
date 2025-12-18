"""
Dev Kernel: Autonomous Multi-Agent Development Orchestrator

A local-first, deterministic orchestration system that:
- Uses Beads as the canonical work graph
- Schedules and dispatches tasks to isolated Workcells
- Produces Patch + Proof artifacts through quality gates
- Supports speculate + vote parallelism for high-risk work
"""

__version__ = "0.1.0"

from dev_kernel.kernel.scheduler import Scheduler
from dev_kernel.kernel.dispatcher import Dispatcher
from dev_kernel.kernel.verifier import Verifier
from dev_kernel.state.manager import StateManager
from dev_kernel.workcell.manager import WorkcellManager

__all__ = [
    "Scheduler",
    "Dispatcher",
    "Verifier",
    "StateManager",
    "WorkcellManager",
]

