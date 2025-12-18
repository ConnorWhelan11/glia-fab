"""
Fab Template Support - Asset templates and scaffolds.

Provides functionality for:
- Loading template manifests
- Validating template adherence
- Checking modification constraints
- Finding templates by category/ID
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TemplateConstraints:
    """Constraints for template-based modifications."""

    required_parts: List[str] = field(default_factory=list)
    scale_tolerance: float = 0.1
    max_modification_ratio: float = 0.5
    preserve_wheel_positions: bool = True
    allow_part_addition: bool = True
    allow_part_deletion: bool = False
    bounds_m: Optional[Dict[str, Tuple[float, float]]] = None


@dataclass
class TemplateManifest:
    """Template manifest data."""

    template_id: str
    category: str
    version: str
    description: str
    path: Path
    constraints: TemplateConstraints
    golden_scores: Dict[str, float] = field(default_factory=dict)
    parts: List[Dict[str, Any]] = field(default_factory=list)
    materials: List[Dict[str, Any]] = field(default_factory=list)
    checksums: Dict[str, Optional[str]] = field(default_factory=dict)
    status: str = "placeholder"


@dataclass
class TemplateAdherenceResult:
    """Result of checking template adherence."""

    passed: bool
    score: float
    fail_codes: List[str] = field(default_factory=list)
    missing_parts: List[str] = field(default_factory=list)
    scale_deviation: float = 0.0
    modification_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "fail_codes": self.fail_codes,
            "missing_parts": self.missing_parts,
            "scale_deviation": self.scale_deviation,
            "modification_ratio": self.modification_ratio,
        }


class TemplateRegistry:
    """
    Registry for available templates.

    Loads templates from the fab/templates/ directory structure.
    """

    def __init__(self, templates_root: Optional[Path] = None):
        """
        Initialize template registry.

        Args:
            templates_root: Root path for templates (default: fab/templates/)
        """
        if templates_root is None:
            # Default to fab/templates/ relative to repo root
            # Try to find it relative to package
            pkg_root = Path(__file__).parent.parent.parent.parent.parent
            templates_root = pkg_root / "fab" / "templates"

        self.templates_root = templates_root
        self._templates: Dict[str, TemplateManifest] = {}
        self._registry_data: Optional[Dict[str, Any]] = None

    def _load_registry(self) -> None:
        """Load the templates registry.json."""
        registry_path = self.templates_root / "registry.json"

        if not registry_path.exists():
            logger.warning(f"Template registry not found: {registry_path}")
            self._registry_data = {"templates": []}
            return

        try:
            with open(registry_path) as f:
                self._registry_data = json.load(f)
            logger.info(f"Loaded template registry with {len(self._registry_data.get('templates', []))} templates")
        except Exception as e:
            logger.error(f"Failed to load template registry: {e}")
            self._registry_data = {"templates": []}

    def list_templates(self, category: Optional[str] = None) -> List[str]:
        """
        List available template IDs.

        Args:
            category: Optional category filter

        Returns:
            List of template IDs
        """
        if self._registry_data is None:
            self._load_registry()

        templates = self._registry_data.get("templates", [])

        if category:
            templates = [t for t in templates if t.get("category") == category]

        return [t.get("template_id") for t in templates if t.get("template_id")]

    def get_template(self, template_id: str) -> Optional[TemplateManifest]:
        """
        Get template manifest by ID.

        Args:
            template_id: Template identifier

        Returns:
            TemplateManifest or None if not found
        """
        # Check cache
        if template_id in self._templates:
            return self._templates[template_id]

        # Load registry if needed
        if self._registry_data is None:
            self._load_registry()

        # Find template in registry
        for entry in self._registry_data.get("templates", []):
            if entry.get("template_id") == template_id:
                manifest = self._load_template_manifest(entry)
                if manifest:
                    self._templates[template_id] = manifest
                return manifest

        return None

    def _load_template_manifest(self, registry_entry: Dict[str, Any]) -> Optional[TemplateManifest]:
        """Load full template manifest from registry entry."""
        template_path = registry_entry.get("path", "")
        if not template_path:
            return None

        manifest_path = self.templates_root / template_path / "manifest.json"

        # Parse constraints
        constraints_data = registry_entry.get("constraints", {})
        bounds_data = constraints_data.get("bounds_m", {})

        constraints = TemplateConstraints(
            required_parts=constraints_data.get("required_parts", []),
            scale_tolerance=constraints_data.get("scale_tolerance", 0.1),
            max_modification_ratio=constraints_data.get("max_modification_ratio", 0.5),
            bounds_m={
                k: tuple(v) for k, v in bounds_data.items()
            } if bounds_data else None,
        )

        # Load full manifest if available
        parts = []
        materials = []
        checksums = {}

        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    full_manifest = json.load(f)
                parts = full_manifest.get("parts", [])
                materials = full_manifest.get("materials", [])
                checksums = full_manifest.get("checksums", {})

                # Override constraints from full manifest if present
                if "constraints" in full_manifest:
                    c = full_manifest["constraints"]
                    constraints.required_parts = c.get("required_parts", constraints.required_parts)
                    constraints.allow_part_addition = c.get("allow_part_addition", True)
                    constraints.allow_part_deletion = c.get("allow_part_deletion", False)
                    constraints.preserve_wheel_positions = c.get("preserve_wheel_positions", True)
            except Exception as e:
                logger.warning(f"Failed to load full manifest {manifest_path}: {e}")

        return TemplateManifest(
            template_id=registry_entry.get("template_id", "unknown"),
            category=registry_entry.get("category", "unknown"),
            version=registry_entry.get("version", "1.0.0"),
            description=registry_entry.get("description", ""),
            path=self.templates_root / template_path,
            constraints=constraints,
            golden_scores=registry_entry.get("golden_scores", {}),
            parts=parts,
            materials=materials,
            checksums=checksums,
            status=registry_entry.get("status", "active"),
        )

    def find_template_for_category(self, category: str) -> Optional[TemplateManifest]:
        """Find the default template for a category."""
        templates = self.list_templates(category)
        if templates:
            return self.get_template(templates[0])
        return None


class TemplateChecker:
    """
    Checks asset adherence to template constraints.

    Validates that a modified asset still meets the template's requirements.
    """

    def __init__(self, template: TemplateManifest):
        self.template = template

    def check_adherence(
        self,
        asset_bounds: Optional[Dict[str, float]] = None,
        asset_parts: Optional[List[str]] = None,
        asset_triangle_count: int = 0,
        template_triangle_count: int = 0,
    ) -> TemplateAdherenceResult:
        """
        Check if an asset adheres to template constraints.

        Args:
            asset_bounds: Asset bounding box {length, width, height}
            asset_parts: List of part names in the asset
            asset_triangle_count: Number of triangles in modified asset
            template_triangle_count: Number of triangles in template

        Returns:
            TemplateAdherenceResult
        """
        fail_codes: List[str] = []
        missing_parts: List[str] = []
        scale_deviation = 0.0
        modification_ratio = 0.0

        # Check required parts
        if asset_parts is not None:
            for required in self.template.constraints.required_parts:
                if required not in asset_parts:
                    missing_parts.append(required)

            if missing_parts:
                fail_codes.append("TEMPLATE_MISSING_PARTS")

        # Check scale/bounds
        if asset_bounds and self.template.constraints.bounds_m:
            for dim in ["length", "width", "height"]:
                if dim in asset_bounds and dim in self.template.constraints.bounds_m:
                    expected_range = self.template.constraints.bounds_m[dim]
                    actual = asset_bounds[dim]

                    if actual < expected_range[0] or actual > expected_range[1]:
                        # Calculate deviation as percentage of tolerance
                        mid = (expected_range[0] + expected_range[1]) / 2
                        range_size = expected_range[1] - expected_range[0]
                        deviation = abs(actual - mid) / (range_size / 2) if range_size > 0 else 0
                        scale_deviation = max(scale_deviation, deviation)

            if scale_deviation > 1.0 + self.template.constraints.scale_tolerance:
                fail_codes.append("TEMPLATE_SCALE_EXCEEDED")

        # Check modification ratio
        if template_triangle_count > 0 and asset_triangle_count > 0:
            change = abs(asset_triangle_count - template_triangle_count)
            modification_ratio = change / template_triangle_count

            if modification_ratio > self.template.constraints.max_modification_ratio:
                fail_codes.append("TEMPLATE_MODIFICATION_EXCESSIVE")

        # Calculate score
        score = 1.0
        if missing_parts:
            score -= 0.2 * len(missing_parts)
        if scale_deviation > 0:
            score -= min(0.3, scale_deviation * 0.1)
        if modification_ratio > self.template.constraints.max_modification_ratio:
            score -= 0.2

        score = max(0.0, score)
        passed = len(fail_codes) == 0 and score >= 0.7

        return TemplateAdherenceResult(
            passed=passed,
            score=score,
            fail_codes=fail_codes,
            missing_parts=missing_parts,
            scale_deviation=scale_deviation,
            modification_ratio=modification_ratio,
        )


def get_template_registry(templates_root: Optional[Path] = None) -> TemplateRegistry:
    """Get template registry instance."""
    return TemplateRegistry(templates_root)


def check_template_adherence(
    template_id: str,
    asset_bounds: Optional[Dict[str, float]] = None,
    asset_parts: Optional[List[str]] = None,
    asset_triangle_count: int = 0,
    templates_root: Optional[Path] = None,
) -> Optional[TemplateAdherenceResult]:
    """
    Check if an asset adheres to a template.

    Args:
        template_id: Template identifier
        asset_bounds: Asset bounding box
        asset_parts: List of part names in asset
        asset_triangle_count: Number of triangles
        templates_root: Custom templates root path

    Returns:
        TemplateAdherenceResult or None if template not found
    """
    registry = get_template_registry(templates_root)
    template = registry.get_template(template_id)

    if not template:
        return None

    checker = TemplateChecker(template)
    return checker.check_adherence(
        asset_bounds=asset_bounds,
        asset_parts=asset_parts,
        asset_triangle_count=asset_triangle_count,
        template_triangle_count=template.golden_scores.get("triangle_count", 0),
    )

