"""
Fab - Asset Creation & Realism Gate Subsystem

This module provides deterministic asset evaluation through:
- Canonical headless renders via Blender
- Multi-signal critics (category, alignment, realism, geometry)
- Gate decision logic with iterate-until-pass repair loops
"""

from pathlib import Path

__version__ = "0.1.0"

# Module paths
FAB_ROOT = Path(__file__).parent
SCHEMAS_ROOT = FAB_ROOT.parent.parent.parent / "schemas" / "fab"

# Lazy imports for main components
from .config import GateConfig, load_gate_config, find_gate_config
from .gate import run_gate, GateResult
from .render import run_render_harness, RenderResult
from .templates import (
    TemplateRegistry,
    TemplateManifest,
    TemplateChecker,
    TemplateAdherenceResult,
    get_template_registry,
    check_template_adherence,
)
from .iteration import (
    IterationManager,
    IterationState,
    RepairIssue,
    should_create_repair_issue,
    create_repair_context,
)
from .vote_pack import (
    VotePackRunner,
    VotePackConfig,
    VotePackResult,
    run_vote_pack_if_needed,
)
from .multi_category import (
    MultiCategoryGateRouter,
    route_to_gate,
    list_supported_categories,
    detect_category_from_tags,
)

# Critics (optional - require ML dependencies)
try:
    from .critics import (
        CategoryCritic,
        CategoryResult,
        AlignmentCritic,
        AlignmentResult,
        RealismCritic,
        RealismResult,
        GeometryCritic,
        GeometryResult,
    )

    _HAS_CRITICS = True
except ImportError:
    _HAS_CRITICS = False
    CategoryCritic = None  # type: ignore
    CategoryResult = None  # type: ignore
    AlignmentCritic = None  # type: ignore
    AlignmentResult = None  # type: ignore
    RealismCritic = None  # type: ignore
    RealismResult = None  # type: ignore
    GeometryCritic = None  # type: ignore
    GeometryResult = None  # type: ignore

__all__ = [
    "__version__",
    "FAB_ROOT",
    "SCHEMAS_ROOT",
    # Config
    "GateConfig",
    "load_gate_config",
    "find_gate_config",
    # Gate
    "run_gate",
    "GateResult",
    # Render
    "run_render_harness",
    "RenderResult",
    # Templates
    "TemplateRegistry",
    "TemplateManifest",
    "TemplateChecker",
    "TemplateAdherenceResult",
    "get_template_registry",
    "check_template_adherence",
    # Iteration
    "IterationManager",
    "IterationState",
    "RepairIssue",
    "should_create_repair_issue",
    "create_repair_context",
    # Vote Pack
    "VotePackRunner",
    "VotePackConfig",
    "VotePackResult",
    "run_vote_pack_if_needed",
    # Multi-category
    "MultiCategoryGateRouter",
    "route_to_gate",
    "list_supported_categories",
    "detect_category_from_tags",
    # Critics
    "CategoryCritic",
    "CategoryResult",
    "AlignmentCritic",
    "AlignmentResult",
    "RealismCritic",
    "RealismResult",
    "GeometryCritic",
    "GeometryResult",
]
