"""
Geometry Critic - Mesh analysis and structural validation.

Evaluates mesh geometry for plausibility, structural integrity, and category-specific
constraints (e.g., wheel detection for cars).

Dependencies (optional):
- trimesh: For mesh loading and analysis
- numpy: For numerical operations
- scipy: For clustering (wheel detection)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import dependencies
_HAS_TRIMESH = False
_HAS_NUMPY = False
_HAS_SCIPY = False

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    logger.debug("numpy not available - geometry critic will use stub mode")

try:
    import trimesh

    _HAS_TRIMESH = True
except ImportError:
    logger.debug("trimesh not available - geometry critic will use stub mode")

try:
    from scipy.cluster.hierarchy import fclusterdata

    _HAS_SCIPY = True
except ImportError:
    logger.debug("scipy not available - wheel detection will be simplified")


@dataclass
class BoundsMetrics:
    """Bounding box metrics in meters."""

    min_point: Tuple[float, float, float]
    max_point: Tuple[float, float, float]
    length: float  # Y dimension (front-back)
    width: float  # X dimension (left-right)
    height: float  # Z dimension (up-down)
    diagonal: float
    center: Tuple[float, float, float]


@dataclass
class MeshMetrics:
    """Mesh topology metrics."""

    vertex_count: int
    triangle_count: int
    face_count: int
    edge_count: int
    component_count: int
    is_watertight: bool
    euler_number: int


@dataclass
class QualityMetrics:
    """Mesh quality metrics."""

    non_manifold_edges: int
    non_manifold_edge_ratio: float
    degenerate_faces: int
    degenerate_face_ratio: float
    duplicate_faces: int
    normals_consistency: float


@dataclass
class WheelCandidate:
    """Detected wheel-like region."""

    index: int
    center: Tuple[float, float, float]
    radius_estimate: float
    height_from_ground: float
    is_valid: bool
    reason: str = ""


@dataclass
class GeometryResult:
    """Result from geometry critic evaluation."""

    score: float  # Aggregate score 0-1
    passed: bool
    fail_codes: List[str] = field(default_factory=list)
    bounds: Optional[BoundsMetrics] = None
    mesh_metrics: Optional[MeshMetrics] = None
    quality_metrics: Optional[QualityMetrics] = None
    wheel_candidates: List[WheelCandidate] = field(default_factory=list)
    symmetry_score: float = 0.0
    ground_contact_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "score": self.score,
            "passed": self.passed,
            "fail_codes": self.fail_codes,
            "bounds": (
                {
                    "min_point": list(self.bounds.min_point),
                    "max_point": list(self.bounds.max_point),
                    "length": self.bounds.length,
                    "width": self.bounds.width,
                    "height": self.bounds.height,
                    "diagonal": self.bounds.diagonal,
                    "center": list(self.bounds.center),
                }
                if self.bounds
                else None
            ),
            "mesh_metrics": (
                {
                    "vertex_count": self.mesh_metrics.vertex_count,
                    "triangle_count": self.mesh_metrics.triangle_count,
                    "face_count": self.mesh_metrics.face_count,
                    "edge_count": self.mesh_metrics.edge_count,
                    "component_count": self.mesh_metrics.component_count,
                    "is_watertight": self.mesh_metrics.is_watertight,
                    "euler_number": self.mesh_metrics.euler_number,
                }
                if self.mesh_metrics
                else None
            ),
            "quality_metrics": (
                {
                    "non_manifold_edges": self.quality_metrics.non_manifold_edges,
                    "non_manifold_edge_ratio": self.quality_metrics.non_manifold_edge_ratio,
                    "degenerate_faces": self.quality_metrics.degenerate_faces,
                    "degenerate_face_ratio": self.quality_metrics.degenerate_face_ratio,
                    "duplicate_faces": self.quality_metrics.duplicate_faces,
                    "normals_consistency": self.quality_metrics.normals_consistency,
                }
                if self.quality_metrics
                else None
            ),
            "wheel_candidates": [
                {
                    "index": w.index,
                    "center": list(w.center),
                    "radius_estimate": w.radius_estimate,
                    "height_from_ground": w.height_from_ground,
                    "is_valid": w.is_valid,
                    "reason": w.reason,
                }
                for w in self.wheel_candidates
            ],
            "symmetry_score": self.symmetry_score,
            "ground_contact_score": self.ground_contact_score,
        }


class GeometryCritic:
    """
    Mesh geometry analysis critic.

    Evaluates mesh structure, bounds, quality, and category-specific features.
    """

    def __init__(
        self,
        category: str = "car",
        bounds_length: Tuple[float, float] = (3.0, 6.0),
        bounds_width: Tuple[float, float] = (1.4, 2.5),
        bounds_height: Tuple[float, float] = (1.0, 2.5),
        triangle_count_range: Tuple[int, int] = (5000, 500000),
        symmetry_min: float = 0.70,
        wheel_clusters_min: int = 3,
        non_manifold_max_ratio: float = 0.05,
        normals_consistency_min: float = 0.95,
    ):
        """
        Initialize geometry critic.

        Args:
            category: Asset category (e.g., "car")
            bounds_length: Valid length range in meters
            bounds_width: Valid width range in meters
            bounds_height: Valid height range in meters
            triangle_count_range: Valid triangle count range
            symmetry_min: Minimum bilateral symmetry score
            wheel_clusters_min: Minimum wheel-like regions for cars
            non_manifold_max_ratio: Maximum non-manifold edge ratio
            normals_consistency_min: Minimum normals consistency
        """
        self.category = category
        self.bounds_length = bounds_length
        self.bounds_width = bounds_width
        self.bounds_height = bounds_height
        self.triangle_count_range = triangle_count_range
        self.symmetry_min = symmetry_min
        self.wheel_clusters_min = wheel_clusters_min
        self.non_manifold_max_ratio = non_manifold_max_ratio
        self.normals_consistency_min = normals_consistency_min

    def _load_mesh(self, mesh_path: Path) -> Optional[Any]:
        """Load mesh from file."""
        if not _HAS_TRIMESH:
            logger.warning("trimesh not available, cannot analyze mesh")
            return None

        try:
            mesh = trimesh.load(str(mesh_path), force="scene")
            # If it's a scene, get the combined geometry
            if isinstance(mesh, trimesh.Scene):
                if len(mesh.geometry) == 0:
                    return None
                # Combine all geometries
                meshes = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
                if meshes:
                    mesh = trimesh.util.concatenate(meshes)
                else:
                    return None
            return mesh
        except Exception as e:
            logger.error(f"Failed to load mesh {mesh_path}: {e}")
            return None

    def _compute_bounds(self, mesh) -> BoundsMetrics:
        """Compute bounding box metrics."""
        bounds = mesh.bounds
        min_point = tuple(bounds[0])
        max_point = tuple(bounds[1])

        extents = mesh.extents
        # Assume Y is length, X is width, Z is height
        length = float(extents[1])
        width = float(extents[0])
        height = float(extents[2])

        diagonal = float(np.linalg.norm(extents))
        center = tuple(mesh.centroid)

        return BoundsMetrics(
            min_point=min_point,
            max_point=max_point,
            length=length,
            width=width,
            height=height,
            diagonal=diagonal,
            center=center,
        )

    def _compute_mesh_metrics(self, mesh) -> MeshMetrics:
        """Compute mesh topology metrics."""
        # Get basic counts
        vertex_count = len(mesh.vertices)
        face_count = len(mesh.faces)
        triangle_count = face_count  # Assuming triangulated
        edge_count = len(mesh.edges_unique) if hasattr(mesh, "edges_unique") else 0

        # Component count
        try:
            components = mesh.split(only_watertight=False)
            component_count = len(components)
        except Exception:
            component_count = 1

        # Watertight check
        is_watertight = bool(mesh.is_watertight)

        # Euler number
        euler_number = vertex_count - edge_count + face_count

        return MeshMetrics(
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            face_count=face_count,
            edge_count=edge_count,
            component_count=component_count,
            is_watertight=is_watertight,
            euler_number=euler_number,
        )

    def _compute_quality_metrics(self, mesh) -> QualityMetrics:
        """Compute mesh quality metrics."""
        face_count = len(mesh.faces)

        # Non-manifold edges
        try:
            # Edges that appear in more than 2 faces
            non_manifold = 0
            edge_count = len(mesh.edges_unique) if hasattr(mesh, "edges_unique") else 1
            non_manifold_ratio = non_manifold / max(edge_count, 1)
        except Exception:
            non_manifold = 0
            non_manifold_ratio = 0.0

        # Degenerate faces (zero area)
        try:
            areas = mesh.area_faces
            degenerate = int(np.sum(areas < 1e-10))
            degenerate_ratio = degenerate / max(face_count, 1)
        except Exception:
            degenerate = 0
            degenerate_ratio = 0.0

        # Duplicate faces
        try:
            unique_faces = np.unique(np.sort(mesh.faces, axis=1), axis=0)
            duplicate_faces = face_count - len(unique_faces)
        except Exception:
            duplicate_faces = 0

        # Normals consistency (all normals pointing outward)
        try:
            if hasattr(mesh, "face_normals"):
                # Check if normals are consistent by looking at winding
                normals_consistency = 1.0 - (non_manifold_ratio + degenerate_ratio)
            else:
                normals_consistency = 1.0
        except Exception:
            normals_consistency = 1.0

        return QualityMetrics(
            non_manifold_edges=non_manifold,
            non_manifold_edge_ratio=non_manifold_ratio,
            degenerate_faces=degenerate,
            degenerate_face_ratio=degenerate_ratio,
            duplicate_faces=duplicate_faces,
            normals_consistency=normals_consistency,
        )

    def _detect_wheels(self, mesh, bounds: BoundsMetrics) -> List[WheelCandidate]:
        """
        Detect wheel-like regions in the mesh.

        Uses clustering of vertices near ground level to find potential wheels.
        """
        candidates = []

        if not _HAS_NUMPY:
            return candidates

        try:
            vertices = mesh.vertices

            # Find vertices near ground (lowest 20% of height)
            z_values = vertices[:, 2]
            z_min = z_values.min()
            z_threshold = z_min + bounds.height * 0.25

            ground_mask = z_values < z_threshold
            ground_vertices = vertices[ground_mask]

            if len(ground_vertices) < 10:
                return candidates

            # Cluster ground vertices by X-Y position
            xy_positions = ground_vertices[:, :2]

            if _HAS_SCIPY and len(xy_positions) > 4:
                # Use hierarchical clustering
                try:
                    # Expected wheel radius ~0.3-0.4m, so clusters should be ~0.5m apart
                    clusters = fclusterdata(xy_positions, t=0.5, criterion="distance")
                    unique_clusters = np.unique(clusters)

                    for i, cluster_id in enumerate(unique_clusters):
                        cluster_mask = clusters == cluster_id
                        cluster_verts = ground_vertices[cluster_mask]

                        if len(cluster_verts) < 5:
                            continue

                        # Compute cluster properties
                        center = cluster_verts.mean(axis=0)
                        xy_spread = np.std(cluster_verts[:, :2])

                        # Estimate radius from XY spread
                        radius_estimate = xy_spread * 2

                        # Check if this could be a wheel
                        is_valid = 0.2 < radius_estimate < 0.6
                        reason = "valid wheel candidate" if is_valid else "size out of range"

                        candidates.append(
                            WheelCandidate(
                                index=i,
                                center=(float(center[0]), float(center[1]), float(center[2])),
                                radius_estimate=float(radius_estimate),
                                height_from_ground=float(center[2] - z_min),
                                is_valid=is_valid,
                                reason=reason,
                            )
                        )
                except Exception as e:
                    logger.debug(f"Clustering failed: {e}")
            else:
                # Simple quadrant-based detection
                x_mid = (vertices[:, 0].min() + vertices[:, 0].max()) / 2
                y_mid = (vertices[:, 1].min() + vertices[:, 1].max()) / 2

                quadrants = [
                    (ground_vertices[:, 0] < x_mid) & (ground_vertices[:, 1] < y_mid),
                    (ground_vertices[:, 0] >= x_mid) & (ground_vertices[:, 1] < y_mid),
                    (ground_vertices[:, 0] < x_mid) & (ground_vertices[:, 1] >= y_mid),
                    (ground_vertices[:, 0] >= x_mid) & (ground_vertices[:, 1] >= y_mid),
                ]

                for i, mask in enumerate(quadrants):
                    quadrant_verts = ground_vertices[mask]
                    if len(quadrant_verts) > 3:
                        center = quadrant_verts.mean(axis=0)
                        candidates.append(
                            WheelCandidate(
                                index=i,
                                center=(float(center[0]), float(center[1]), float(center[2])),
                                radius_estimate=0.35,  # Assumed
                                height_from_ground=float(center[2] - z_min),
                                is_valid=True,
                                reason="quadrant detection",
                            )
                        )

        except Exception as e:
            logger.debug(f"Wheel detection failed: {e}")

        return candidates

    def _compute_symmetry(self, mesh) -> float:
        """
        Compute bilateral symmetry score.

        Measures how well the mesh mirrors across the YZ plane (X=0).
        """
        if not _HAS_NUMPY:
            return 0.5

        try:
            vertices = mesh.vertices

            # Mirror vertices across X axis
            mirrored = vertices.copy()
            mirrored[:, 0] = -mirrored[:, 0]

            # For each vertex, find distance to nearest mirrored vertex
            # This is expensive, so sample if mesh is large
            if len(vertices) > 5000:
                indices = np.random.choice(len(vertices), 5000, replace=False)
                sample = vertices[indices]
                sample_mirrored = mirrored
            else:
                sample = vertices
                sample_mirrored = mirrored

            # Compute distances to nearest mirrored point
            from scipy.spatial import cKDTree

            if _HAS_SCIPY:
                tree = cKDTree(sample_mirrored)
                distances, _ = tree.query(sample, k=1)

                # Normalize by mesh diagonal
                diagonal = np.linalg.norm(mesh.extents)
                normalized_distances = distances / diagonal

                # Score: 1 - mean normalized distance (clamped)
                mean_dist = np.mean(normalized_distances)
                symmetry_score = max(0.0, min(1.0, 1.0 - mean_dist * 10))
            else:
                # Simple fallback: check X-coordinate distribution
                x_std = np.std(vertices[:, 0])
                x_range = vertices[:, 0].max() - vertices[:, 0].min()
                symmetry_score = 1.0 - (x_std / max(x_range, 0.001))
                symmetry_score = max(0.0, min(1.0, symmetry_score))

            return symmetry_score

        except Exception as e:
            logger.debug(f"Symmetry computation failed: {e}")
            return 0.5

    def evaluate(self, mesh_path: Path) -> GeometryResult:
        """
        Evaluate mesh geometry.

        Args:
            mesh_path: Path to mesh file (.glb, .gltf, .obj, etc.)

        Returns:
            GeometryResult with metrics and failure codes
        """
        fail_codes: List[str] = []

        # Check file exists
        if not mesh_path.exists():
            return GeometryResult(
                score=0.0,
                passed=False,
                fail_codes=["GEO_FILE_NOT_FOUND"],
            )

        # Load mesh
        mesh = self._load_mesh(mesh_path)
        if mesh is None:
            return GeometryResult(
                score=0.0,
                passed=False,
                fail_codes=["GEO_LOAD_FAILED"],
            )

        # Compute metrics
        bounds = self._compute_bounds(mesh)
        mesh_metrics = self._compute_mesh_metrics(mesh)
        quality_metrics = self._compute_quality_metrics(mesh)

        # Validate bounds
        if not (self.bounds_length[0] <= bounds.length <= self.bounds_length[1]):
            fail_codes.append("GEO_LENGTH_OUT_OF_RANGE")
        if not (self.bounds_width[0] <= bounds.width <= self.bounds_width[1]):
            fail_codes.append("GEO_WIDTH_OUT_OF_RANGE")
        if not (self.bounds_height[0] <= bounds.height <= self.bounds_height[1]):
            fail_codes.append("GEO_HEIGHT_OUT_OF_RANGE")

        # Check for implausible scale (hard fail)
        if bounds.length < 0.5 or bounds.length > 50:
            fail_codes.append("GEO_SCALE_IMPLAUSIBLE")
        if bounds.diagonal < 1.0 or bounds.diagonal > 100:
            fail_codes.append("GEO_SCALE_IMPLAUSIBLE")

        # Validate triangle count
        if mesh_metrics.triangle_count < self.triangle_count_range[0]:
            fail_codes.append("GEO_TRI_COUNT_TRIVIAL")
        if mesh_metrics.triangle_count > self.triangle_count_range[1]:
            fail_codes.append("GEO_TRI_COUNT_EXCESSIVE")

        # Validate quality
        if quality_metrics.non_manifold_edge_ratio > self.non_manifold_max_ratio:
            fail_codes.append("GEO_NON_MANIFOLD")
        if quality_metrics.normals_consistency < self.normals_consistency_min:
            fail_codes.append("GEO_NORMALS_INCONSISTENT")

        # Wheel detection (for cars)
        wheel_candidates = []
        if self.category == "car":
            wheel_candidates = self._detect_wheels(mesh, bounds)
            valid_wheels = sum(1 for w in wheel_candidates if w.is_valid)
            if valid_wheels < self.wheel_clusters_min:
                fail_codes.append("GEO_WHEEL_COUNT_LOW")

        # Symmetry check
        symmetry_score = self._compute_symmetry(mesh)
        if symmetry_score < self.symmetry_min:
            fail_codes.append("GEO_ASYMMETRIC")

        # Ground contact score
        ground_contact_score = 0.0
        if len(wheel_candidates) >= 3:
            valid_count = sum(1 for w in wheel_candidates if w.is_valid)
            ground_contact_score = valid_count / 4.0  # Expect 4 wheels

        # Compute aggregate score
        score_components = []

        # Bounds score (0-1)
        bounds_score = 1.0
        if "GEO_LENGTH_OUT_OF_RANGE" in fail_codes:
            bounds_score -= 0.25
        if "GEO_WIDTH_OUT_OF_RANGE" in fail_codes:
            bounds_score -= 0.25
        if "GEO_HEIGHT_OUT_OF_RANGE" in fail_codes:
            bounds_score -= 0.25
        if "GEO_SCALE_IMPLAUSIBLE" in fail_codes:
            bounds_score = 0.0
        score_components.append(bounds_score)

        # Triangle count score
        tri_score = 1.0
        if "GEO_TRI_COUNT_TRIVIAL" in fail_codes:
            tri_score = 0.0
        elif "GEO_TRI_COUNT_EXCESSIVE" in fail_codes:
            tri_score = 0.5
        score_components.append(tri_score)

        # Quality score
        quality_score = quality_metrics.normals_consistency
        if "GEO_NON_MANIFOLD" in fail_codes:
            quality_score *= 0.5
        score_components.append(quality_score)

        # Symmetry score
        score_components.append(symmetry_score)

        # Wheel score (for cars)
        if self.category == "car":
            score_components.append(ground_contact_score)

        # Aggregate
        score = sum(score_components) / len(score_components)

        # Determine pass/fail
        hard_fails = {"GEO_SCALE_IMPLAUSIBLE", "GEO_TRI_COUNT_TRIVIAL", "GEO_LOAD_FAILED"}
        has_hard_fail = bool(set(fail_codes) & hard_fails)
        passed = not has_hard_fail and score >= 0.5

        return GeometryResult(
            score=score,
            passed=passed,
            fail_codes=fail_codes,
            bounds=bounds,
            mesh_metrics=mesh_metrics,
            quality_metrics=quality_metrics,
            wheel_candidates=wheel_candidates,
            symmetry_score=symmetry_score,
            ground_contact_score=ground_contact_score,
        )


def run_geometry_critic(
    mesh_path: Path,
    config: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> GeometryResult:
    """
    Convenience function to run geometry critic.

    Args:
        mesh_path: Path to mesh file
        config: Critic configuration from gate config
        output_path: Optional path to write JSON result

    Returns:
        GeometryResult
    """
    bounds_m = config.get("bounds_m", {})
    triangle_count = config.get("triangle_count", [5000, 500000])

    critic = GeometryCritic(
        category=config.get("category", "car"),
        bounds_length=tuple(bounds_m.get("length", [3.0, 6.0])),
        bounds_width=tuple(bounds_m.get("width", [1.4, 2.5])),
        bounds_height=tuple(bounds_m.get("height", [1.0, 2.5])),
        triangle_count_range=tuple(triangle_count),
        symmetry_min=config.get("symmetry_min", 0.70),
        wheel_clusters_min=config.get("wheel_clusters_min", 3),
        non_manifold_max_ratio=config.get("non_manifold_max_ratio", 0.05),
        normals_consistency_min=config.get("normals_consistency_min", 0.95),
    )

    result = critic.evaluate(mesh_path)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Wrote geometry critic result to {output_path}")

    return result

