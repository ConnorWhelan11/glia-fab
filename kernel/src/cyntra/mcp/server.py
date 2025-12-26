"""
MCP Server - Expose Cyntra capabilities as MCP tools.

This server exposes the following tools to MCP clients:

Kernel Tools:
- list_issues: List all issues from Beads
- get_issue: Get details of a specific issue
- get_ready: Get issues ready for work
- get_status: Get kernel status
- schedule: Run a scheduling cycle
- dispatch: Dispatch a task to a workcell (dry-run only)
- get_events: Get recent events

ComfyUI Tools (dynamically generated from workflow registry):
- comfyui_health: Check server health
- comfyui_list_workflows: List available workflows
- comfyui_{workflow_id}: Execute specific workflows

RunPod Tools (requires RUNPOD_API_KEY):
- runpod_list_pods: List GPU pods
- runpod_start_pod: Start a stopped pod
- runpod_stop_pod: Stop a running pod
- runpod_create_tunnel: Create SSH tunnel for ComfyUI access

Resources:
- issues: Issue data from Beads
- events: Event log data
- stats: Kernel statistics
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from mcp import Server, types
    from mcp.server import stdio

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None
    types = None
    stdio = None

from cyntra.kernel.config import KernelConfig
from cyntra.kernel.scheduler import Scheduler
from cyntra.state.manager import StateManager
from cyntra.observability.events import EventReader

# Optional ComfyUI and RunPod tools
try:
    from cyntra.mcp.comfyui_tools import ComfyUIToolProvider
    from cyntra.mcp.runpod_tools import RunPodToolProvider
    from cyntra.fab.comfyui_client import ComfyUIConfig
    from cyntra.fab.workflow_registry import WorkflowRegistry
    COMFYUI_AVAILABLE = True
except ImportError:
    COMFYUI_AVAILABLE = False
    ComfyUIToolProvider = None
    RunPodToolProvider = None


class CyntraMCPServer:
    """
    MCP Server for Cyntra.

    Exposes kernel capabilities as tools that can be called
    by MCP-compatible LLM agents.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        workflow_registry_path: Path | None = None,
    ) -> None:
        if not MCP_AVAILABLE:
            raise RuntimeError(
                "MCP package not installed. Install with: pip install mcp"
            )

        self.config_path = config_path or Path(".cyntra/config.yaml")
        self._config: KernelConfig | None = None
        self._state_manager: StateManager | None = None
        self._scheduler: Scheduler | None = None
        self._event_reader: EventReader | None = None

        # ComfyUI and RunPod providers
        self._comfyui_provider: ComfyUIToolProvider | None = None
        self._runpod_provider: RunPodToolProvider | None = None

        # Initialize ComfyUI tools if available
        if COMFYUI_AVAILABLE:
            registry_path = workflow_registry_path or Path(
                "fab/workflows/comfyui/registry.yaml"
            )
            if registry_path.exists():
                try:
                    self._comfyui_provider = ComfyUIToolProvider(registry_path)
                except Exception as e:
                    import structlog
                    structlog.get_logger().warning(
                        "Failed to load ComfyUI tools", error=str(e)
                    )

            # Initialize RunPod tools
            try:
                self._runpod_provider = RunPodToolProvider()
            except Exception as e:
                import structlog
                structlog.get_logger().warning(
                    "Failed to load RunPod tools", error=str(e)
                )

        # Create MCP server
        self.server = Server("cyntra-kernel")
        self._register_tools()
        self._register_resources()

    def _ensure_initialized(self) -> None:
        """Initialize components lazily."""
        if self._config is None:
            self._config = KernelConfig.load(self.config_path)
            self._state_manager = StateManager(self._config)
            self._scheduler = Scheduler(self._config)
            self._event_reader = EventReader(self._config.logs_dir)

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.tool("list_issues")
        async def list_issues() -> list[dict[str, Any]]:
            """List all issues from Beads."""
            self._ensure_initialized()
            graph = self._state_manager.load_graph()
            return [issue.to_dict() for issue in graph.issues]

        @self.server.tool("get_issue")
        async def get_issue(issue_id: str) -> dict[str, Any] | None:
            """Get details of a specific issue."""
            self._ensure_initialized()
            graph = self._state_manager.load_graph()
            issue = graph.get_issue(issue_id)
            return issue.to_dict() if issue else None

        @self.server.tool("get_ready")
        async def get_ready() -> list[dict[str, Any]]:
            """Get issues that are ready to work on."""
            self._ensure_initialized()
            graph = self._state_manager.load_graph()
            result = self._scheduler.schedule(graph)
            return [issue.to_dict() for issue in result.ready_issues]

        @self.server.tool("get_schedule")
        async def get_schedule() -> dict[str, Any]:
            """Get the current scheduling plan."""
            self._ensure_initialized()
            graph = self._state_manager.load_graph()
            result = self._scheduler.schedule(graph)
            return {
                "ready_count": len(result.ready_issues),
                "scheduled_count": len(result.scheduled_lanes),
                "speculate_count": len(result.speculate_issues),
                "critical_path": [i.id for i in result.critical_path],
                "scheduled": [
                    {
                        "id": i.id,
                        "title": i.title,
                        "priority": i.dk_priority,
                        "risk": i.dk_risk,
                        "speculate": i.id in {s.id for s in result.speculate_issues},
                    }
                    for i in result.scheduled_lanes
                ],
            }

        @self.server.tool("get_status")
        async def get_status() -> dict[str, Any]:
            """Get kernel status and statistics."""
            self._ensure_initialized()
            stats = self._event_reader.get_stats()
            graph = self._state_manager.load_graph()

            return {
                "config_path": str(self.config_path),
                "issues_total": len(graph.issues),
                "issues_open": len([i for i in graph.issues if i.status == "open"]),
                "issues_done": len([i for i in graph.issues if i.status == "done"]),
                **stats,
            }

        @self.server.tool("get_events")
        async def get_events(limit: int = 50) -> list[dict[str, Any]]:
            """Get recent events from the log."""
            self._ensure_initialized()
            return self._event_reader.read_recent(limit)

        @self.server.tool("get_issue_events")
        async def get_issue_events(issue_id: str) -> list[dict[str, Any]]:
            """Get all events for a specific issue."""
            self._ensure_initialized()
            return self._event_reader.read_by_issue(issue_id)

        @self.server.tool("update_issue_status")
        async def update_issue_status(issue_id: str, status: str) -> bool:
            """Update the status of an issue."""
            self._ensure_initialized()
            return self._state_manager.update_issue_status(issue_id, status)

        @self.server.tool("create_issue")
        async def create_issue(
            title: str,
            description: str | None = None,
            priority: str = "P2",
            tags: list[str] | None = None,
        ) -> str | None:
            """Create a new issue in Beads."""
            self._ensure_initialized()
            return self._state_manager.create_issue(title, description, priority, tags)

        # Register ComfyUI tools
        self._register_comfyui_tools()

        # Register RunPod tools
        self._register_runpod_tools()

    def _register_comfyui_tools(self) -> None:
        """Register ComfyUI workflow tools."""
        if not self._comfyui_provider:
            return

        for tool_def in self._comfyui_provider.tools.values():
            # Use factory function to properly capture handler for each iteration
            self._register_single_tool(
                tool_def["name"],
                tool_def["description"],
                tool_def["handler"],
            )

    def _register_single_tool(
        self, name: str, description: str, handler: Any
    ) -> None:
        """Register a single tool with proper closure capture.

        This factory pattern ensures each handler is captured correctly,
        avoiding the classic Python closure-in-loop bug where all handlers
        would reference the last value.
        """

        @self.server.tool(name)
        async def tool_handler(**kwargs: Any) -> dict[str, Any]:
            return await handler(**kwargs)

        tool_handler.__doc__ = description

    def _register_runpod_tools(self) -> None:
        """Register RunPod management tools."""
        if not self._runpod_provider or not self._runpod_provider.available:
            return

        for tool_def in self._runpod_provider.tools.values():
            # Reuse the same factory function for proper closure capture
            self._register_single_tool(
                tool_def["name"],
                tool_def["description"],
                tool_def["handler"],
            )

    def _register_resources(self) -> None:
        """Register MCP resources."""

        @self.server.resource("issues")
        async def issues_resource() -> types.Resource:
            """All issues from Beads."""
            self._ensure_initialized()
            graph = self._state_manager.load_graph()
            content = json.dumps([i.to_dict() for i in graph.issues], indent=2)
            return types.Resource(
                uri="cyntra-kernel://issues",
                name="Beads Issues",
                description="All issues from the Beads work graph",
                mimeType="application/json",
                text=content,
            )

        @self.server.resource("events")
        async def events_resource() -> types.Resource:
            """Recent events from the kernel."""
            self._ensure_initialized()
            events = self._event_reader.read_recent(100)
            content = json.dumps(events, indent=2)
            return types.Resource(
                uri="cyntra-kernel://events",
                name="Kernel Events",
                description="Recent events from Cyntra",
                mimeType="application/json",
                text=content,
            )

        @self.server.resource("stats")
        async def stats_resource() -> types.Resource:
            """Kernel statistics."""
            self._ensure_initialized()
            stats = self._event_reader.get_stats()
            content = json.dumps(stats, indent=2)
            return types.Resource(
                uri="cyntra-kernel://stats",
                name="Kernel Statistics",
                description="Statistics from Cyntra",
                mimeType="application/json",
                text=content,
            )

    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def create_server(config_path: Path | None = None) -> CyntraMCPServer:
    """Create an MCP server instance."""
    return CyntraMCPServer(config_path)


async def main() -> None:
    """Entry point for MCP server."""
    import sys

    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    server = create_server(config_path)
    await server.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
