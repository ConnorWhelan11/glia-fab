"""
Multi-Category Gate Support

Provides automatic detection and routing to appropriate gate configs
based on asset category, tags, or explicit specification.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CategoryConfig:
    """Configuration for a supported category."""

    category: str
    gate_config_id: str
    gate_config_path: Path
    lookdev_scene_id: str
    camera_rig_id: str
    description: str = ""


# Supported categories and their default configs
SUPPORTED_CATEGORIES: Dict[str, CategoryConfig] = {
    "car": CategoryConfig(
        category="car",
        gate_config_id="car_realism_v001",
        gate_config_path=Path("fab/gates/car_realism_v001.yaml"),
        lookdev_scene_id="car_lookdev_v001",
        camera_rig_id="car_camrig_v001",
        description="Vehicles: cars, trucks, motorcycles",
    ),
    "furniture": CategoryConfig(
        category="furniture",
        gate_config_id="furniture_realism_v001",
        gate_config_path=Path("fab/gates/furniture_realism_v001.yaml"),
        lookdev_scene_id="furniture_lookdev_v001",
        camera_rig_id="furniture_camrig_v001",
        description="Furniture: chairs, tables, sofas, desks",
    ),
    "architecture": CategoryConfig(
        category="architecture",
        gate_config_id="architecture_realism_v001",
        gate_config_path=Path("fab/gates/architecture_realism_v001.yaml"),
        lookdev_scene_id="architecture_lookdev_v001",
        camera_rig_id="architecture_camrig_v001",
        description="Buildings and structures",
    ),
}

# Tag patterns that map to categories
TAG_CATEGORY_MAPPING: Dict[str, str] = {
    "asset:car": "car",
    "asset:vehicle": "car",
    "asset:furniture": "furniture",
    "asset:chair": "furniture",
    "asset:table": "furniture",
    "asset:architecture": "architecture",
    "asset:building": "architecture",
    "asset:house": "architecture",
}


def detect_category_from_tags(tags: List[str]) -> Optional[str]:
    """
    Detect asset category from issue tags.

    Args:
        tags: List of issue tags

    Returns:
        Category string or None if not detected
    """
    for tag in tags:
        # Direct mapping
        if tag in TAG_CATEGORY_MAPPING:
            return TAG_CATEGORY_MAPPING[tag]

        # Pattern matching: asset:* extracts category
        if tag.startswith("asset:"):
            asset_type = tag.split(":")[1]
            if asset_type in SUPPORTED_CATEGORIES:
                return asset_type

    return None


def get_gate_config_for_category(
    category: str,
    base_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Load gate configuration for a category.

    Args:
        category: Asset category
        base_path: Base path for config files

    Returns:
        Gate configuration dictionary or None
    """
    if category not in SUPPORTED_CATEGORIES:
        logger.warning(f"Unknown category: {category}")
        return None

    cat_config = SUPPORTED_CATEGORIES[category]
    config_path = cat_config.gate_config_path

    if base_path:
        config_path = base_path / config_path

    if not config_path.exists():
        logger.warning(f"Gate config not found: {config_path}")
        return None

    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load gate config: {e}")
        return None


def get_category_config(category: str) -> Optional[CategoryConfig]:
    """Get category configuration."""
    return SUPPORTED_CATEGORIES.get(category)


def list_supported_categories() -> List[Dict[str, str]]:
    """List all supported categories with descriptions."""
    return [
        {
            "category": cat,
            "gate_config_id": config.gate_config_id,
            "description": config.description,
        }
        for cat, config in SUPPORTED_CATEGORIES.items()
    ]


def route_to_gate(
    tags: List[str],
    explicit_category: Optional[str] = None,
    explicit_gate_config: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Determine which gate to use based on tags and explicit settings.

    Args:
        tags: Issue tags
        explicit_category: Explicitly specified category
        explicit_gate_config: Explicitly specified gate config ID

    Returns:
        Tuple of (category, gate_config_id)

    Raises:
        ValueError: If no category can be determined
    """
    # Explicit gate config takes precedence
    if explicit_gate_config:
        # Find category for this gate config
        for cat, config in SUPPORTED_CATEGORIES.items():
            if config.gate_config_id == explicit_gate_config:
                return cat, explicit_gate_config
        # Unknown gate config, assume custom
        return "custom", explicit_gate_config

    # Explicit category
    if explicit_category:
        if explicit_category in SUPPORTED_CATEGORIES:
            return (
                explicit_category,
                SUPPORTED_CATEGORIES[explicit_category].gate_config_id,
            )
        raise ValueError(f"Unknown category: {explicit_category}")

    # Detect from tags
    detected = detect_category_from_tags(tags)
    if detected:
        return detected, SUPPORTED_CATEGORIES[detected].gate_config_id

    # Default to car (most common)
    logger.info("No category detected, defaulting to 'car'")
    return "car", SUPPORTED_CATEGORIES["car"].gate_config_id


class MultiCategoryGateRouter:
    """
    Router for directing assets to appropriate category-specific gates.

    Handles:
    1. Category detection from tags
    2. Gate config loading
    3. Lookdev/camera rig selection
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize router.

        Args:
            base_path: Base path for finding config files
        """
        self.base_path = base_path or Path(".")
        self._config_cache: Dict[str, Dict[str, Any]] = {}

    def get_gate_config(
        self,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        gate_config_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Get appropriate gate configuration.

        Args:
            tags: Issue tags for category detection
            category: Explicit category
            gate_config_id: Explicit gate config ID

        Returns:
            Tuple of (category, gate_config_dict)
        """
        # Determine category and gate config
        detected_category, config_id = route_to_gate(
            tags=tags or [],
            explicit_category=category,
            explicit_gate_config=gate_config_id,
        )

        # Check cache
        if config_id in self._config_cache:
            return detected_category, self._config_cache[config_id]

        # Load config
        config = get_gate_config_for_category(detected_category, self.base_path)
        if config is None:
            raise ValueError(f"Failed to load config for category: {detected_category}")

        self._config_cache[config_id] = config
        return detected_category, config

    def get_scene_refs(
        self, category: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get lookdev scene and camera rig IDs for a category.

        Returns:
            Tuple of (lookdev_scene_id, camera_rig_id)
        """
        cat_config = get_category_config(category)
        if cat_config:
            return cat_config.lookdev_scene_id, cat_config.camera_rig_id
        return None, None

    def validate_category_support(self, category: str) -> bool:
        """Check if a category is supported."""
        return category in SUPPORTED_CATEGORIES

    def get_all_categories(self) -> List[str]:
        """Get list of all supported categories."""
        return list(SUPPORTED_CATEGORIES.keys())

