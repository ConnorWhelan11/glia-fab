"""
Optional dependency helpers for Fab critics.

Some optional dependencies (notably `torch`) can hard-crash in constrained sandboxes
instead of raising ImportError. To keep the critics usable in "stub mode", we detect
importability via a subprocess before importing in-process.
"""

from __future__ import annotations

import functools
import importlib.util
import os
import subprocess
import sys
from typing import Any


def _module_declared(module_name: str) -> bool:
    """Return True if the module is discoverable (without importing it)."""
    return importlib.util.find_spec(module_name) is not None


@functools.lru_cache(maxsize=1)
def torch_usable() -> bool:
    """
    Return True if `import torch` works in a subprocess.

    This avoids crashing the current interpreter when `torch` aborts due to
    OpenMP/shared-memory restrictions in sandboxed environments.
    """
    if os.getenv("DEV_KERNEL_FAB_DISABLE_TORCH") == "1":
        return False
    if not _module_declared("torch"):
        return False

    result = subprocess.run(
        [sys.executable, "-c", "import torch"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return result.returncode == 0


@functools.lru_cache(maxsize=1)
def open_clip_usable() -> bool:
    """Return True if `import open_clip` works in a subprocess."""
    if os.getenv("DEV_KERNEL_FAB_DISABLE_OPEN_CLIP") == "1":
        return False
    if not _module_declared("open_clip"):
        return False
    if not torch_usable():
        return False

    result = subprocess.run(
        [sys.executable, "-c", "import open_clip"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return result.returncode == 0


@functools.lru_cache(maxsize=1)
def safe_import_torch() -> Any | None:
    """Import torch if usable; otherwise return None."""
    if not torch_usable():
        return None
    import torch  # type: ignore

    return torch


@functools.lru_cache(maxsize=1)
def safe_import_open_clip() -> Any | None:
    """Import open_clip if usable; otherwise return None."""
    if not open_clip_usable():
        return None
    import open_clip  # type: ignore

    return open_clip

