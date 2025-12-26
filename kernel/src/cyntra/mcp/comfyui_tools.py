"""
ComfyUI MCP Tools - Dynamically generated tools from workflow registry.

Provides tools for image generation, material creation, and texture processing
using ComfyUI workflows.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
from pathlib import Path
from typing import Any, Callable

import structlog

from cyntra.fab.comfyui_client import ComfyUIClient, ComfyUIConfig, ComfyUIError
from cyntra.fab.workflow_registry import WorkflowRegistry, Workflow, WorkflowInput

logger = structlog.get_logger()


class ValidationError(Exception):
    """Input validation error for workflow parameters."""

    pass


def validate_workflow_input(inp: WorkflowInput, value: Any) -> Any:
    """Validate and convert a single workflow input.

    Args:
        inp: Workflow input definition with type, min, max constraints
        value: The value to validate

    Returns:
        Validated and converted value

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if inp.required:
            raise ValidationError(f"Required parameter '{inp.name}' is missing")
        return inp.default

    if inp.type == "string":
        if not isinstance(value, str):
            try:
                value = str(value)
            except (ValueError, TypeError):
                raise ValidationError(f"Cannot convert '{inp.name}' to string: {value}")
        return value

    elif inp.type == "int":
        try:
            val = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Cannot convert '{inp.name}' to int: {value}")

        if inp.min is not None and val < int(inp.min):
            raise ValidationError(
                f"'{inp.name}' value {val} is below minimum {int(inp.min)}"
            )
        if inp.max is not None and val > int(inp.max):
            raise ValidationError(
                f"'{inp.name}' value {val} exceeds maximum {int(inp.max)}"
            )
        return val

    elif inp.type == "float":
        try:
            val = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Cannot convert '{inp.name}' to float: {value}")

        if inp.min is not None and val < inp.min:
            raise ValidationError(
                f"'{inp.name}' value {val} is below minimum {inp.min}"
            )
        if inp.max is not None and val > inp.max:
            raise ValidationError(
                f"'{inp.name}' value {val} exceeds maximum {inp.max}"
            )
        return val

    elif inp.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    elif inp.type == "image":
        # Validate image path exists
        if not isinstance(value, str):
            raise ValidationError(f"Image path '{inp.name}' must be a string")
        path = Path(value).expanduser()
        if not path.exists():
            raise ValidationError(f"Image file not found for '{inp.name}': {path}")
        if not path.is_file():
            raise ValidationError(f"Image path '{inp.name}' is not a file: {path}")
        return str(path)

    else:
        # Unknown type, pass through
        return value


def validate_workflow_inputs(
    workflow: Workflow, kwargs: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Validate all inputs for a workflow.

    Args:
        workflow: Workflow definition
        kwargs: Input parameters from the user

    Returns:
        Tuple of (validated_inputs, error_messages)
    """
    validated = {}
    errors = []

    for inp in workflow.inputs:
        value = kwargs.get(inp.name)

        try:
            validated_value = validate_workflow_input(inp, value)
            if validated_value is not None:
                validated[inp.name] = validated_value
        except ValidationError as e:
            errors.append(str(e))

    return validated, errors


def create_comfyui_tools(
    registry: WorkflowRegistry,
    client_config: ComfyUIConfig | None = None,
    output_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Generate MCP tool definitions from workflow registry.

    Args:
        registry: Workflow registry with workflow definitions
        client_config: ComfyUI client configuration
        output_dir: Directory for output files

    Returns:
        Dict mapping tool names to tool definitions
    """
    tools = {}
    client_config = client_config or ComfyUIConfig()
    output_dir = output_dir or Path(tempfile.gettempdir()) / "comfyui_outputs"

    # Add utility tools
    tools["comfyui_health"] = {
        "name": "comfyui_health",
        "description": "Check if ComfyUI server is running and healthy.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "handler": _create_health_handler(client_config),
    }

    tools["comfyui_list_workflows"] = {
        "name": "comfyui_list_workflows",
        "description": "List all available ComfyUI workflows with their descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (material_generation, post_processing, repair, generation)",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag (pbr, texture, upscale, etc.)",
                },
            },
            "required": [],
        },
        "handler": _create_list_handler(registry),
    }

    # Generate tools for each workflow
    for workflow in registry.workflows:
        tool_name = f"comfyui_{workflow.id}"
        tools[tool_name] = {
            "name": tool_name,
            "description": workflow.to_tool_description(),
            "input_schema": workflow.to_json_schema(),
            "handler": _create_workflow_handler(
                workflow, registry, client_config, output_dir
            ),
        }

    return tools


def _create_health_handler(
    config: ComfyUIConfig,
) -> Callable[..., Any]:
    """Create handler for health check tool."""

    async def handler(**kwargs: Any) -> dict[str, Any]:
        async with ComfyUIClient(config) as client:
            healthy = await client.health_check()
            if healthy:
                stats = await client.get_system_stats()
                return {
                    "status": "healthy",
                    "server": f"{config.host}:{config.port}",
                    "system_stats": stats,
                }
            else:
                return {
                    "status": "unhealthy",
                    "server": f"{config.host}:{config.port}",
                    "error": "Server not responding",
                }

    return handler


def _create_list_handler(
    registry: WorkflowRegistry,
) -> Callable[..., Any]:
    """Create handler for list workflows tool."""

    async def handler(category: str | None = None, tag: str | None = None) -> dict[str, Any]:
        workflows = registry.workflows

        if category:
            workflows = [w for w in workflows if w.category == category]

        if tag:
            workflows = [w for w in workflows if tag in w.tags]

        return {
            "workflows": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "category": w.category,
                    "tags": w.tags,
                    "inputs": [
                        {"name": i.name, "type": i.type, "required": i.required}
                        for i in w.inputs
                    ],
                    "outputs": [o.name for o in w.outputs],
                }
                for w in workflows
            ],
            "categories": registry.list_categories(),
            "tags": registry.list_tags(),
        }

    return handler


def _create_workflow_handler(
    workflow: Workflow,
    registry: WorkflowRegistry,
    config: ComfyUIConfig,
    output_dir: Path,
) -> Callable[..., Any]:
    """Create handler for a specific workflow tool."""

    async def handler(**kwargs: Any) -> dict[str, Any]:
        logger.info(
            "Executing ComfyUI workflow",
            workflow_id=workflow.id,
            params=kwargs,
        )

        # Validate inputs before proceeding
        validated_inputs, validation_errors = validate_workflow_inputs(workflow, kwargs)
        if validation_errors:
            return {
                "success": False,
                "error": "Input validation failed",
                "validation_errors": validation_errors,
            }

        # Load workflow JSON
        workflow_path = registry.get_workflow_path(workflow)
        if not workflow_path.exists():
            return {
                "success": False,
                "error": f"Workflow file not found: {workflow_path}",
            }

        try:
            workflow_json = json.loads(workflow_path.read_text())
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid workflow JSON: {e}",
            }

        # Handle seed - use secrets for better randomness
        seed = validated_inputs.pop("seed", None)
        if seed is None or seed == "random":
            seed = secrets.randbits(32)
            logger.debug("Generated random seed", seed=seed)

        # Inject seed
        workflow_json = ComfyUIClient.inject_seed(workflow_json, seed)

        # Inject validated parameters
        for inp in workflow.inputs:
            if inp.name in validated_inputs:
                value = validated_inputs[inp.name]
                node_id = inp.node
                if node_id in workflow_json:
                    node = workflow_json[node_id]
                    inputs = node.get("inputs", {})

                    # Handle field path (e.g., "widgets_values[0]")
                    if "[" in inp.node_field:
                        # Parse array access
                        parts = inp.node_field.replace("]", "").split("[")
                        field_name = parts[0]
                        index = int(parts[1])
                        if field_name in inputs and isinstance(inputs[field_name], list):
                            inputs[field_name][index] = value
                    else:
                        inputs[inp.node_field] = value

        # Create output directory
        run_output_dir = output_dir / workflow.id / str(seed)
        run_output_dir.mkdir(parents=True, exist_ok=True)

        # Execute workflow
        try:
            async with ComfyUIClient(config) as client:
                # Check health first
                if not await client.health_check():
                    return {
                        "success": False,
                        "error": f"ComfyUI server not available at {config.host}:{config.port}",
                    }

                # Queue prompt
                prompt_id = await client.queue_prompt(workflow_json)

                # Wait for completion
                result = await client.wait_for_completion(prompt_id)

                if result.status != "completed":
                    return {
                        "success": False,
                        "error": result.error or "Workflow execution failed",
                        "node_errors": result.node_errors,
                        "execution_time_ms": result.execution_time_ms,
                    }

                # Download outputs
                downloaded = await client.download_outputs(result, run_output_dir)

                # Map outputs to workflow output names
                output_files = {}
                for out in workflow.outputs:
                    node_id = out.node
                    if node_id in downloaded:
                        files = downloaded[node_id]
                        if files:
                            output_files[out.name] = str(files[0])

                return {
                    "success": True,
                    "workflow_id": workflow.id,
                    "seed": seed,
                    "outputs": output_files,
                    "output_dir": str(run_output_dir),
                    "execution_time_ms": result.execution_time_ms,
                }

        except ComfyUIError as e:
            return {
                "success": False,
                "error": str(e),
            }

    return handler


class ComfyUIToolProvider:
    """
    Provider for ComfyUI MCP tools.

    Integrates with the Cyntra MCP server to provide dynamically
    generated tools for all registered workflows.
    """

    def __init__(
        self,
        registry_path: Path | str,
        client_config: ComfyUIConfig | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.registry = WorkflowRegistry.load(registry_path)
        self.client_config = client_config or ComfyUIConfig()
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "comfyui_outputs"
        self._tools: dict[str, dict[str, Any]] | None = None

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        """Get all tool definitions."""
        if self._tools is None:
            self._tools = create_comfyui_tools(
                self.registry,
                self.client_config,
                self.output_dir,
            )
        return self._tools

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get a specific tool by name."""
        return self.tools.get(name)

    async def execute_tool(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with parameters."""
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}

        handler = tool["handler"]
        return await handler(**params)

    def get_tool_names(self) -> list[str]:
        """Get list of all tool names."""
        return list(self.tools.keys())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get JSON schemas for all tools (for MCP registration)."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in self.tools.values()
        ]
