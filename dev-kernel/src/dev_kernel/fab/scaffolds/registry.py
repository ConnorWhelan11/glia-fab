"""
Scaffold Registry - Central registry for all scaffold types.

Provides:
1. Discovery and registration of scaffolds
2. Version tracking and validation
3. Scaffold lookup by category
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import ScaffoldBase

logger = logging.getLogger(__name__)


class ScaffoldRegistry:
    """
    Central registry for procedural scaffolds.

    Scaffolds are registered by category and ID, with version tracking
    to prevent drift and ensure reproducibility.
    """

    def __init__(self):
        self._scaffolds: Dict[str, Dict[str, Type[ScaffoldBase]]] = {}
        self._manifests: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        scaffold_class: Type[ScaffoldBase],
        replace: bool = False,
    ) -> None:
        """
        Register a scaffold class.

        Args:
            scaffold_class: The scaffold class to register
            replace: If True, replace existing registration
        """
        category = scaffold_class.CATEGORY
        scaffold_id = scaffold_class.SCAFFOLD_ID
        version = scaffold_class.SCAFFOLD_VERSION

        if category not in self._scaffolds:
            self._scaffolds[category] = {}

        key = f"{scaffold_id}:{version}"

        if key in self._scaffolds[category] and not replace:
            raise ValueError(f"Scaffold {key} already registered in {category}")

        self._scaffolds[category][key] = scaffold_class

        # Generate and store manifest
        instance = scaffold_class()
        self._manifests[key] = instance.to_manifest()

        logger.info(f"Registered scaffold: {category}/{scaffold_id} v{version}")

    def get(
        self,
        category: str,
        scaffold_id: str,
        version: Optional[str] = None,
    ) -> Optional[ScaffoldBase]:
        """
        Get a scaffold instance by category and ID.

        Args:
            category: Scaffold category (e.g., "car")
            scaffold_id: Scaffold identifier
            version: Specific version (latest if not specified)

        Returns:
            Scaffold instance or None
        """
        if category not in self._scaffolds:
            return None

        # Find matching scaffold
        if version:
            key = f"{scaffold_id}:{version}"
            if key in self._scaffolds[category]:
                return self._scaffolds[category][key]()
        else:
            # Find latest version
            matching = [
                k for k in self._scaffolds[category] if k.startswith(f"{scaffold_id}:")
            ]
            if matching:
                # Sort by version and get latest
                latest = sorted(matching, key=lambda x: x.split(":")[1])[-1]
                return self._scaffolds[category][latest]()

        return None

    def list_scaffolds(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available scaffolds.

        Args:
            category: Filter by category (all if None)

        Returns:
            List of scaffold info dictionaries
        """
        results = []

        categories = [category] if category else list(self._scaffolds.keys())

        for cat in categories:
            if cat not in self._scaffolds:
                continue
            for key, scaffold_class in self._scaffolds[cat].items():
                results.append(
                    {
                        "category": cat,
                        "scaffold_id": scaffold_class.SCAFFOLD_ID,
                        "version": scaffold_class.SCAFFOLD_VERSION,
                        "key": key,
                    }
                )

        return results

    def get_manifest(self, scaffold_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Get the manifest for a specific scaffold version."""
        key = f"{scaffold_id}:{version}"
        return self._manifests.get(key)

    def verify_scaffold(
        self,
        scaffold_id: str,
        version: str,
        expected_hash: str,
    ) -> bool:
        """
        Verify scaffold definition matches expected hash.

        Used for drift prevention - ensures scaffold hasn't changed.
        """
        manifest = self.get_manifest(scaffold_id, version)
        if not manifest:
            return False

        return manifest.get("definition_hash") == expected_hash

    def export_manifest(self, output_path: Path) -> None:
        """Export all scaffold manifests to JSON file."""
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "scaffolds": self._manifests,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(
            f"Exported {len(self._manifests)} scaffold manifests to {output_path}"
        )


# Global registry instance
_global_registry: Optional[ScaffoldRegistry] = None


def get_registry() -> ScaffoldRegistry:
    """Get the global scaffold registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ScaffoldRegistry()
        _register_builtin_scaffolds(_global_registry)
    return _global_registry


def _register_builtin_scaffolds(registry: ScaffoldRegistry) -> None:
    """Register built-in scaffolds."""
    from .car_scaffold import CarScaffold
    from .sverchok import CarSverchokScaffold
    from .study_pod import StudyPodScaffold

    # Native Geometry Nodes scaffolds
    registry.register(CarScaffold)

    # Sverchok-based scaffolds (advanced)
    registry.register(CarSverchokScaffold)

    # Furniture/interior scaffolds
    registry.register(StudyPodScaffold)


def get_scaffold(
    category: str,
    scaffold_id: str,
    version: Optional[str] = None,
) -> Optional[ScaffoldBase]:
    """
    Get a scaffold by category and ID.

    Convenience wrapper around registry.get().
    """
    return get_registry().get(category, scaffold_id, version)


def list_scaffolds(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List available scaffolds.

    Convenience wrapper around registry.list_scaffolds().
    """
    return get_registry().list_scaffolds(category)
