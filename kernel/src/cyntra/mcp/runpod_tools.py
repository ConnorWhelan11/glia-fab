"""
RunPod MCP Tools - GPU pod management for on-demand ComfyUI.

Provides tools for starting, stopping, and managing RunPod GPU instances
for ComfyUI workflow execution.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import structlog

from cyntra.fab.runpod_manager import (
    RunPodManager,
    RunPodConfig,
    RunPodError,
)

logger = structlog.get_logger()


def create_runpod_tools(
    config: RunPodConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Generate MCP tool definitions for RunPod management.

    Args:
        config: RunPod configuration (uses env vars if None)

    Returns:
        Dict mapping tool names to tool definitions
    """
    # Try to create config from env if not provided
    try:
        config = config or RunPodConfig.from_env()
    except ValueError:
        # No API key, return empty tools
        logger.warning("RUNPOD_API_KEY not set, RunPod tools disabled")
        return {}

    tools = {}

    tools["runpod_list_pods"] = {
        "name": "runpod_list_pods",
        "description": """List all RunPod GPU pods in your account.

Shows status (running/stopped), GPU type, uptime, and cost for each pod.
Use this to check which pods are available before starting ComfyUI workflows.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "handler": _create_list_handler(config),
    }

    tools["runpod_get_pod"] = {
        "name": "runpod_get_pod",
        "description": """Get detailed status of a specific pod.

Returns GPU utilization, memory usage, ports, and SSH connection info.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_id": {
                    "type": "string",
                    "description": "The pod ID to check",
                },
            },
            "required": ["pod_id"],
        },
        "handler": _create_get_handler(config),
    }

    tools["runpod_start_pod"] = {
        "name": "runpod_start_pod",
        "description": """Start a stopped RunPod GPU pod.

Starts the pod and waits for it to be running. Returns connection info
including SSH command and ComfyUI URL once ready.

Cost: Charged per hour while running (typically $0.40-0.80/hr for RTX 4090).""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_id": {
                    "type": "string",
                    "description": "The pod ID to start",
                },
            },
            "required": ["pod_id"],
        },
        "handler": _create_start_handler(config),
    }

    tools["runpod_stop_pod"] = {
        "name": "runpod_stop_pod",
        "description": """Stop a running RunPod GPU pod.

Stops the pod to save costs. Data on the volume is preserved.
You only pay for volume storage while stopped (much cheaper than running).

IMPORTANT: Always stop pods when not in use to avoid unnecessary charges!""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_id": {
                    "type": "string",
                    "description": "The pod ID to stop",
                },
            },
            "required": ["pod_id"],
        },
        "handler": _create_stop_handler(config),
    }

    tools["runpod_create_tunnel"] = {
        "name": "runpod_create_tunnel",
        "description": """Create an SSH tunnel to access ComfyUI on a pod.

Sets up port forwarding so ComfyUI is accessible at localhost:8188.
Required before running ComfyUI workflows on remote pods.

The tunnel runs in the background until the pod is stopped or the
tunnel is explicitly closed.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_id": {
                    "type": "string",
                    "description": "The pod ID to tunnel to",
                },
                "local_port": {
                    "type": "integer",
                    "description": "Local port to forward (default: 8188)",
                    "default": 8188,
                },
            },
            "required": ["pod_id"],
        },
        "handler": _create_tunnel_handler(config),
    }

    tools["runpod_available_gpus"] = {
        "name": "runpod_available_gpus",
        "description": """List available GPU types and their current pricing.

Shows GPU memory, on-demand price, spot price, and stock level.
Use this to find the best GPU for your budget and requirements.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "handler": _create_gpus_handler(config),
    }

    tools["runpod_create_pod"] = {
        "name": "runpod_create_pod",
        "description": """Create a new RunPod GPU pod for ComfyUI.

Creates a new pod with the specified GPU and starts it. The pod comes
with PyTorch pre-installed. You'll need to set up ComfyUI after creation.

Default GPU: RTX 4090 (~$0.50/hr)
Default storage: 100GB volume""",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the pod (e.g., 'comfyui-server')",
                },
                "gpu_type": {
                    "type": "string",
                    "description": "GPU type ID (e.g., 'NVIDIA GeForce RTX 4090'). Use runpod_available_gpus to see options.",
                },
                "volume_gb": {
                    "type": "integer",
                    "description": "Volume size in GB (default: 100)",
                    "default": 100,
                },
            },
            "required": ["name"],
        },
        "handler": _create_create_handler(config),
    }

    return tools


def _create_list_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for list pods tool."""

    async def handler(**kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                pods = await manager.list_pods()
                return {
                    "success": True,
                    "pods": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "status": p.status,
                            "gpu_type": p.gpu_type,
                            "gpu_utilization": p.gpu_utilization,
                            "uptime_seconds": p.uptime_seconds,
                            "cost_per_hour": p.cost_per_hour,
                            "ssh_command": p.ssh_command,
                            "comfyui_url": p.comfyui_url,
                        }
                        for p in pods
                    ],
                    "total_running": sum(1 for p in pods if p.is_running),
                    "total_stopped": sum(1 for p in pods if p.is_stopped),
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_get_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for get pod tool."""

    async def handler(pod_id: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                pod = await manager.get_pod(pod_id)
                if not pod:
                    return {"success": False, "error": f"Pod not found: {pod_id}"}

                return {
                    "success": True,
                    "pod": {
                        "id": pod.id,
                        "name": pod.name,
                        "status": pod.status,
                        "gpu_type": pod.gpu_type,
                        "gpu_utilization": pod.gpu_utilization,
                        "memory_utilization": pod.memory_utilization,
                        "uptime_seconds": pod.uptime_seconds,
                        "cost_per_hour": pod.cost_per_hour,
                        "ssh_command": pod.ssh_command,
                        "comfyui_url": pod.comfyui_url,
                        "ports": [
                            {
                                "private": p.private_port,
                                "public": p.public_port,
                                "type": p.port_type,
                                "ip": p.ip,
                            }
                            for p in pod.ports
                        ],
                    },
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_start_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for start pod tool."""

    async def handler(pod_id: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                pod = await manager.start_pod(pod_id)
                return {
                    "success": True,
                    "message": f"Pod {pod_id} is now running",
                    "pod": {
                        "id": pod.id,
                        "name": pod.name,
                        "status": pod.status,
                        "gpu_type": pod.gpu_type,
                        "cost_per_hour": pod.cost_per_hour,
                        "ssh_command": pod.ssh_command,
                        "comfyui_url": pod.comfyui_url,
                    },
                    "next_steps": [
                        "Create SSH tunnel: runpod_create_tunnel",
                        "Check ComfyUI health: comfyui_health",
                        "Remember to stop pod when done: runpod_stop_pod",
                    ],
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_stop_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for stop pod tool."""

    async def handler(pod_id: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                pod = await manager.stop_pod(pod_id)
                return {
                    "success": True,
                    "message": f"Pod {pod_id} has been stopped",
                    "pod": {
                        "id": pod.id,
                        "name": pod.name,
                        "status": pod.status,
                    },
                    "note": "Volume data is preserved. Start the pod again to continue working.",
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_tunnel_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for create tunnel tool."""

    async def handler(pod_id: str, local_port: int = 8188, **kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                tunnel = await manager.create_tunnel(pod_id, local_port=local_port)

                # Note: tunnel process runs in background, manager close won't kill it
                # since we want it to persist

                return {
                    "success": True,
                    "message": "SSH tunnel created successfully",
                    "tunnel": {
                        "local_url": tunnel.local_url,
                        "local_port": tunnel.local_port,
                        "remote_port": tunnel.remote_port,
                        "ssh_host": tunnel.ssh_host,
                        "ssh_port": tunnel.ssh_port,
                    },
                    "comfyui_url": f"http://localhost:{local_port}",
                    "next_steps": [
                        f"ComfyUI is now accessible at http://localhost:{local_port}",
                        "Check health: comfyui_health",
                        "Run workflows: comfyui_chord_pbr, comfyui_txt2img_sdxl, etc.",
                    ],
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_gpus_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for available GPUs tool."""

    async def handler(**kwargs: Any) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                gpus = await manager.get_available_gpus()
                return {
                    "success": True,
                    "gpus": gpus,
                    "recommendation": "RTX 4090 offers best value for ComfyUI workflows",
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


def _create_create_handler(config: RunPodConfig) -> Callable[..., Any]:
    """Create handler for create pod tool."""

    async def handler(
        name: str,
        gpu_type: str | None = None,
        volume_gb: int = 100,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            async with RunPodManager(config) as manager:
                pod = await manager.create_pod(
                    name=name,
                    gpu_type=gpu_type,
                    volume_gb=volume_gb,
                )
                return {
                    "success": True,
                    "message": f"Pod '{name}' created and running",
                    "pod": {
                        "id": pod.id,
                        "name": pod.name,
                        "status": pod.status,
                        "gpu_type": pod.gpu_type,
                        "cost_per_hour": pod.cost_per_hour,
                        "ssh_command": pod.ssh_command,
                    },
                    "next_steps": [
                        "SSH into pod and set up ComfyUI",
                        "Create tunnel: runpod_create_tunnel",
                        "Remember to stop pod when done!",
                    ],
                }
        except RunPodError as e:
            return {"success": False, "error": str(e)}

    return handler


class RunPodToolProvider:
    """
    Provider for RunPod MCP tools.

    Integrates with the Cyntra MCP server to provide GPU pod
    management capabilities.
    """

    def __init__(self, config: RunPodConfig | None = None) -> None:
        try:
            self.config = config or RunPodConfig.from_env()
            self._tools = create_runpod_tools(self.config)
            self.available = True
        except ValueError:
            self.config = None
            self._tools = {}
            self.available = False
            logger.warning("RunPod tools not available (no API key)")

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        """Get all tool definitions."""
        return self._tools

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get a specific tool by name."""
        return self._tools.get(name)

    async def execute_tool(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with parameters."""
        if not self.available:
            return {"success": False, "error": "RunPod not configured (set RUNPOD_API_KEY)"}

        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}

        handler = tool["handler"]
        return await handler(**params)

    def get_tool_names(self) -> list[str]:
        """Get list of all tool names."""
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get JSON schemas for all tools (for MCP registration)."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in self._tools.values()
        ]
