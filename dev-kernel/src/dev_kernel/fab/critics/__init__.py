"""
Fab Critics - Multi-signal evaluation for 3D assets.

Critics analyze renders and mesh data to produce structured scores and failure codes.
Each critic is deterministic, versioned, and produces auditable results.

Available Critics:
- CategoryCritic: Multi-view semantic classification (is it a car?)
- AlignmentCritic: Text-to-image similarity (does it match the prompt?)
- RealismCritic: Image quality and visual plausibility
- GeometryCritic: Mesh analysis and structural validation
"""

from .alignment import AlignmentCritic, AlignmentResult
from .category import CategoryCritic, CategoryResult
from .geometry import GeometryCritic, GeometryResult
from .realism import RealismCritic, RealismResult

__all__ = [
    # Category
    "CategoryCritic",
    "CategoryResult",
    # Alignment
    "AlignmentCritic",
    "AlignmentResult",
    # Realism
    "RealismCritic",
    "RealismResult",
    # Geometry
    "GeometryCritic",
    "GeometryResult",
]
