"""
State - Beads integration and state management.

Modules:
    manager     - Atomic read/write to Beads
    beads       - Beads CLI wrapper
    models      - Issue, Dep, and related data models
    transitions - Status state machine transitions
"""

from dev_kernel.state.manager import StateManager

__all__ = ["StateManager"]

