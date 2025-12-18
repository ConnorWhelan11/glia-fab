"""
Base classes for procedural scaffolds.

Scaffolds provide parametric asset generation using:
1. Geometry Nodes (Blender native, recommended)
2. Python-based procedural mesh generation

Each scaffold defines:
- Parameters with ranges and defaults
- Validation rules
- Blender script generation for procedural creation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class ParameterType(Enum):
    """Types of scaffold parameters."""

    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    VECTOR3 = "vector3"
    ENUM = "enum"
    COLOR = "color"


@dataclass
class ScaffoldParameter:
    """Definition of a scaffold parameter."""

    name: str
    param_type: ParameterType
    default: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    enum_values: Optional[List[str]] = None
    description: str = ""
    unit: str = ""  # "m", "deg", "rad", etc.
    affects_geometry: bool = True  # Does this parameter affect mesh topology?

    def validate(self, value: Any) -> Tuple[bool, str]:
        """Validate a parameter value."""
        if self.param_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                return False, f"Expected float, got {type(value).__name__}"
            if self.min_value is not None and value < self.min_value:
                return False, f"Value {value} below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Value {value} above maximum {self.max_value}"

        elif self.param_type == ParameterType.INT:
            if not isinstance(value, int):
                return False, f"Expected int, got {type(value).__name__}"
            if self.min_value is not None and value < self.min_value:
                return False, f"Value {value} below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Value {value} above maximum {self.max_value}"

        elif self.param_type == ParameterType.BOOL:
            if not isinstance(value, bool):
                return False, f"Expected bool, got {type(value).__name__}"

        elif self.param_type == ParameterType.VECTOR3:
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                return False, f"Expected 3-element vector, got {value}"
            for i, v in enumerate(value):
                if not isinstance(v, (int, float)):
                    return False, f"Vector element {i} not numeric"

        elif self.param_type == ParameterType.ENUM:
            if self.enum_values and value not in self.enum_values:
                return False, f"Value {value} not in {self.enum_values}"

        elif self.param_type == ParameterType.COLOR:
            if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
                return False, f"Expected RGB(A) color, got {value}"
            for i, v in enumerate(value):
                if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
                    return False, f"Color component {i} must be in [0, 1]"

        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.param_type.value,
            "default": self.default,
            "min": self.min_value,
            "max": self.max_value,
            "enum_values": self.enum_values,
            "description": self.description,
            "unit": self.unit,
            "affects_geometry": self.affects_geometry,
        }


@dataclass
class ScaffoldResult:
    """Result from scaffold instantiation."""

    success: bool
    scaffold_id: str
    scaffold_version: str
    parameters_used: Dict[str, Any]
    output_path: Optional[Path] = None
    blend_path: Optional[Path] = None
    script_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    geometry_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "scaffold_id": self.scaffold_id,
            "scaffold_version": self.scaffold_version,
            "parameters_used": self.parameters_used,
            "output_path": str(self.output_path) if self.output_path else None,
            "blend_path": str(self.blend_path) if self.blend_path else None,
            "script_path": str(self.script_path) if self.script_path else None,
            "error": self.error,
            "warnings": self.warnings,
            "geometry_stats": self.geometry_stats,
        }


class ScaffoldBase(ABC):
    """Base class for procedural scaffolds."""

    # Subclasses must define these
    SCAFFOLD_ID: str = ""
    SCAFFOLD_VERSION: str = "1.0.0"
    CATEGORY: str = ""

    def __init__(self):
        self._parameters: Dict[str, ScaffoldParameter] = {}
        self._define_parameters()

    @abstractmethod
    def _define_parameters(self) -> None:
        """Define scaffold parameters. Subclasses must implement."""
        pass

    def add_parameter(self, param: ScaffoldParameter) -> None:
        """Add a parameter to the scaffold."""
        self._parameters[param.name] = param

    def get_parameters(self) -> Dict[str, ScaffoldParameter]:
        """Get all parameter definitions."""
        return self._parameters.copy()

    def get_defaults(self) -> Dict[str, Any]:
        """Get default values for all parameters."""
        return {name: param.default for name, param in self._parameters.items()}

    def validate_parameters(self, params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate parameter values.

        Args:
            params: Dictionary of parameter values

        Returns:
            Tuple of (all_valid, list_of_errors)
        """
        errors = []

        for name, value in params.items():
            if name not in self._parameters:
                errors.append(f"Unknown parameter: {name}")
                continue

            valid, error = self._parameters[name].validate(value)
            if not valid:
                errors.append(f"{name}: {error}")

        return len(errors) == 0, errors

    @abstractmethod
    def generate_blender_script(
        self,
        params: Dict[str, Any],
        output_path: Path,
    ) -> str:
        """
        Generate Blender Python script for scaffold creation.

        Args:
            params: Parameter values
            output_path: Where to save the generated asset

        Returns:
            Python script content for Blender
        """
        pass

    @abstractmethod
    def generate_geometry_nodes_setup(self) -> str:
        """
        Generate script to create Geometry Nodes modifier.

        Returns:
            Python script for Geometry Nodes setup
        """
        pass

    def instantiate(
        self,
        params: Optional[Dict[str, Any]] = None,
        output_dir: Path = Path("."),
    ) -> ScaffoldResult:
        """
        Create scaffold instance with given parameters.

        Args:
            params: Parameter overrides (uses defaults if not provided)
            output_dir: Directory for output files

        Returns:
            ScaffoldResult with paths and status
        """
        # Merge with defaults
        final_params = self.get_defaults()
        if params:
            final_params.update(params)

        # Validate
        valid, errors = self.validate_parameters(final_params)
        if not valid:
            return ScaffoldResult(
                success=False,
                scaffold_id=self.SCAFFOLD_ID,
                scaffold_version=self.SCAFFOLD_VERSION,
                parameters_used=final_params,
                error=f"Parameter validation failed: {'; '.join(errors)}",
            )

        try:
            # Generate script
            output_path = (
                output_dir / f"{self.SCAFFOLD_ID}_v{self.SCAFFOLD_VERSION}.glb"
            )
            blend_path = (
                output_dir / f"{self.SCAFFOLD_ID}_v{self.SCAFFOLD_VERSION}.blend"
            )
            script_path = output_dir / f"{self.SCAFFOLD_ID}_generate.py"

            script_content = self.generate_blender_script(final_params, output_path)

            # Write script
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script_content)

            return ScaffoldResult(
                success=True,
                scaffold_id=self.SCAFFOLD_ID,
                scaffold_version=self.SCAFFOLD_VERSION,
                parameters_used=final_params,
                output_path=output_path,
                blend_path=blend_path,
                script_path=script_path,
            )

        except Exception as e:
            return ScaffoldResult(
                success=False,
                scaffold_id=self.SCAFFOLD_ID,
                scaffold_version=self.SCAFFOLD_VERSION,
                parameters_used=final_params,
                error=str(e),
            )

    def to_manifest(self) -> Dict[str, Any]:
        """Generate manifest for scaffold versioning."""
        import hashlib

        # Create deterministic hash of scaffold definition
        params_str = str(sorted(self._parameters.keys()))
        version_str = f"{self.SCAFFOLD_ID}:{self.SCAFFOLD_VERSION}:{params_str}"
        definition_hash = hashlib.sha256(version_str.encode()).hexdigest()[:16]

        return {
            "scaffold_id": self.SCAFFOLD_ID,
            "version": self.SCAFFOLD_VERSION,
            "category": self.CATEGORY,
            "definition_hash": definition_hash,
            "parameters": {
                name: param.to_dict() for name, param in self._parameters.items()
            },
        }
