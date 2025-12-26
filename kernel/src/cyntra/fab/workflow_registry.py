"""
ComfyUI Workflow Registry - Load and query workflow metadata.

This module provides a structured way to discover and understand
available ComfyUI workflows for MCP tool generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
import structlog

logger = structlog.get_logger()


@dataclass
class WorkflowInput:
    """Definition of a workflow input parameter."""

    name: str
    type: str  # string, int, float, image, bool
    required: bool
    description: str
    node: str  # Node ID in workflow
    node_field: str = "text"  # Field name in node inputs
    default: Any = None
    min: float | None = None
    max: float | None = None
    examples: list[str] = field(default_factory=list)
    upload: bool = False  # Whether this input requires file upload

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema property definition."""
        schema: dict[str, Any] = {"description": self.description}

        if self.type == "string":
            schema["type"] = "string"
            if self.examples:
                schema["examples"] = self.examples
        elif self.type == "int":
            schema["type"] = "integer"
            if self.min is not None:
                schema["minimum"] = int(self.min)
            if self.max is not None:
                schema["maximum"] = int(self.max)
        elif self.type == "float":
            schema["type"] = "number"
            if self.min is not None:
                schema["minimum"] = self.min
            if self.max is not None:
                schema["maximum"] = self.max
        elif self.type == "image":
            schema["type"] = "string"
            schema["description"] += " (file path)"
        elif self.type == "bool":
            schema["type"] = "boolean"

        if self.default is not None and self.default != "random":
            schema["default"] = self.default

        return schema


@dataclass
class WorkflowOutput:
    """Definition of a workflow output."""

    name: str
    node: str
    description: str
    format: str = "png"


@dataclass
class WorkflowModel:
    """Required model for a workflow."""

    name: str
    type: str  # checkpoint, upscale_model, text_encoder, diffusion_model, vae
    url: str
    size: str = "unknown"
    gated: bool = False
    license: str | None = None


@dataclass
class WorkflowCustomNode:
    """Required custom node for a workflow."""

    name: str
    url: str


@dataclass
class WorkflowPerformance:
    """Performance estimates for a workflow."""

    rtx_4090: str | None = None
    rtx_3090: str | None = None
    a100: str | None = None
    vram_required: str | None = None
    output_resolution: str | None = None
    scale_factor: int | None = None


@dataclass
class Workflow:
    """Complete workflow definition with metadata."""

    id: str
    file: str
    name: str
    description: str
    when_to_use: str
    tags: list[str]
    category: str
    inputs: list[WorkflowInput]
    outputs: list[WorkflowOutput]
    performance: WorkflowPerformance
    required_models: list[WorkflowModel]
    required_custom_nodes: list[WorkflowCustomNode]

    def to_json_schema(self) -> dict[str, Any]:
        """Generate JSON Schema for this workflow's inputs."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for inp in self.inputs:
            properties[inp.name] = inp.to_json_schema()
            if inp.required:
                required.append(inp.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_tool_description(self) -> str:
        """Generate a description for MCP tool."""
        lines = [
            self.description,
            "",
            "When to use:",
            self.when_to_use.strip(),
        ]

        if self.performance.rtx_4090:
            lines.append(f"\nPerformance (RTX 4090): {self.performance.rtx_4090}")
        if self.performance.vram_required:
            lines.append(f"VRAM Required: {self.performance.vram_required}")

        return "\n".join(lines)

    def has_image_inputs(self) -> bool:
        """Check if workflow requires image file inputs."""
        return any(inp.type == "image" for inp in self.inputs)


@dataclass
class WorkflowRegistry:
    """Registry of all available ComfyUI workflows."""

    version: int
    workflows: list[Workflow]
    registry_path: Path
    _parse_errors: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @property
    def has_errors(self) -> bool:
        """Check if there were any parse errors during loading."""
        return len(self._parse_errors) > 0

    @property
    def parse_errors(self) -> list[dict[str, Any]]:
        """Get list of parse errors from loading."""
        return self._parse_errors.copy()

    @classmethod
    def load(cls, registry_path: Path | str) -> "WorkflowRegistry":
        """
        Load workflow registry from YAML file.

        Args:
            registry_path: Path to registry.yaml

        Returns:
            Loaded WorkflowRegistry

        Raises:
            FileNotFoundError: If registry file doesn't exist
            ValueError: If registry format is invalid
        """
        registry_path = Path(registry_path)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {registry_path}")

        content = registry_path.read_text()
        data = yaml.safe_load(content)

        if not isinstance(data, dict):
            raise ValueError("Registry must be a YAML object")

        version = data.get("version", 1)
        workflow_data = data.get("workflows", [])

        workflows = []
        parse_errors: list[dict[str, Any]] = []

        for wf in workflow_data:
            workflow_id = wf.get("id", "unknown")
            try:
                workflow = cls._parse_workflow(wf)
                workflows.append(workflow)
            except KeyError as e:
                # Missing required field
                error_info = {
                    "workflow_id": workflow_id,
                    "error_type": "missing_field",
                    "field": str(e),
                    "message": f"Required field missing: {e}",
                }
                parse_errors.append(error_info)
                logger.error(
                    "Workflow missing required field",
                    workflow_id=workflow_id,
                    field=str(e),
                )
            except (ValueError, TypeError) as e:
                # Type or value error
                error_info = {
                    "workflow_id": workflow_id,
                    "error_type": "invalid_value",
                    "message": str(e),
                }
                parse_errors.append(error_info)
                logger.error(
                    "Workflow has invalid value",
                    workflow_id=workflow_id,
                    error=str(e),
                )
            except Exception as e:
                # Unexpected error
                error_info = {
                    "workflow_id": workflow_id,
                    "error_type": "parse_error",
                    "message": str(e),
                }
                parse_errors.append(error_info)
                logger.error(
                    "Failed to parse workflow",
                    workflow_id=workflow_id,
                    error=str(e),
                    exc_info=True,
                )

        # Log summary
        if parse_errors:
            logger.warning(
                "Workflow registry loaded with errors",
                path=str(registry_path),
                version=version,
                valid_count=len(workflows),
                error_count=len(parse_errors),
                failed_workflows=[e["workflow_id"] for e in parse_errors],
            )
        else:
            logger.info(
                "Loaded workflow registry",
                path=str(registry_path),
                version=version,
                workflow_count=len(workflows),
            )

        return cls(
            version=version,
            workflows=workflows,
            registry_path=registry_path,
            _parse_errors=parse_errors,
        )

    @staticmethod
    def _parse_workflow(data: dict[str, Any]) -> Workflow:
        """Parse a workflow entry from registry YAML."""
        # Parse inputs
        inputs = []
        for inp_data in data.get("inputs", []):
            inputs.append(
                WorkflowInput(
                    name=inp_data["name"],
                    type=inp_data.get("type", "string"),
                    required=inp_data.get("required", False),
                    description=inp_data.get("description", ""),
                    node=str(inp_data.get("node", "")),
                    node_field=inp_data.get("field", "text"),
                    default=inp_data.get("default"),
                    min=inp_data.get("min"),
                    max=inp_data.get("max"),
                    examples=inp_data.get("examples", []),
                    upload=inp_data.get("upload", False),
                )
            )

        # Parse outputs
        outputs = []
        for out_data in data.get("outputs", []):
            outputs.append(
                WorkflowOutput(
                    name=out_data["name"],
                    node=str(out_data.get("node", "")),
                    description=out_data.get("description", ""),
                    format=out_data.get("format", "png"),
                )
            )

        # Parse performance
        perf_data = data.get("performance", {})
        performance = WorkflowPerformance(
            rtx_4090=perf_data.get("rtx_4090"),
            rtx_3090=perf_data.get("rtx_3090"),
            a100=perf_data.get("a100"),
            vram_required=perf_data.get("vram_required"),
            output_resolution=perf_data.get("output_resolution"),
            scale_factor=perf_data.get("scale_factor"),
        )

        # Parse required models
        models = []
        for model_data in data.get("required_models", []):
            models.append(
                WorkflowModel(
                    name=model_data["name"],
                    type=model_data.get("type", "unknown"),
                    url=model_data.get("url", ""),
                    size=model_data.get("size", "unknown"),
                    gated=model_data.get("gated", False),
                    license=model_data.get("license"),
                )
            )

        # Parse required custom nodes
        custom_nodes = []
        for node_data in data.get("required_custom_nodes", []):
            custom_nodes.append(
                WorkflowCustomNode(
                    name=node_data["name"],
                    url=node_data.get("url", ""),
                )
            )

        return Workflow(
            id=data["id"],
            file=data["file"],
            name=data["name"],
            description=data.get("description", ""),
            when_to_use=data.get("when_to_use", ""),
            tags=data.get("tags", []),
            category=data.get("category", "other"),
            inputs=inputs,
            outputs=outputs,
            performance=performance,
            required_models=models,
            required_custom_nodes=custom_nodes,
        )

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get a workflow by ID."""
        for wf in self.workflows:
            if wf.id == workflow_id:
                return wf
        return None

    def get_by_category(self, category: str) -> list[Workflow]:
        """Get all workflows in a category."""
        return [wf for wf in self.workflows if wf.category == category]

    def get_by_tag(self, tag: str) -> list[Workflow]:
        """Get all workflows with a specific tag."""
        return [wf for wf in self.workflows if tag in wf.tags]

    def search(self, query: str) -> list[Workflow]:
        """Search workflows by name, description, or tags."""
        query = query.lower()
        results = []
        for wf in self.workflows:
            if (
                query in wf.name.lower()
                or query in wf.description.lower()
                or any(query in tag.lower() for tag in wf.tags)
            ):
                results.append(wf)
        return results

    def list_categories(self) -> list[str]:
        """List all unique categories."""
        return list(set(wf.category for wf in self.workflows))

    def list_tags(self) -> list[str]:
        """List all unique tags."""
        tags = set()
        for wf in self.workflows:
            tags.update(wf.tags)
        return sorted(tags)

    def get_workflow_path(self, workflow: Workflow) -> Path:
        """Get the full path to a workflow JSON file."""
        return self.registry_path.parent / workflow.file

    def to_summary(self) -> dict[str, Any]:
        """Generate a summary of the registry for agent context."""
        return {
            "version": self.version,
            "workflow_count": len(self.workflows),
            "categories": self.list_categories(),
            "tags": self.list_tags(),
            "workflows": [
                {
                    "id": wf.id,
                    "name": wf.name,
                    "description": wf.description[:100] + "..."
                    if len(wf.description) > 100
                    else wf.description,
                    "category": wf.category,
                    "tags": wf.tags,
                }
                for wf in self.workflows
            ],
        }
