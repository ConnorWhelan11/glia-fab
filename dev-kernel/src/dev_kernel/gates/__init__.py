"""
Gates - Quality gate execution and verification.

Modules:
    runner      - Execute quality gates (test, lint, typecheck, build)
    flaky       - Flaky test detection and handling
    diff_check  - Diff-based gates (forbidden paths, max size)
"""

from dev_kernel.gates.runner import GateRunner

__all__ = ["GateRunner"]

