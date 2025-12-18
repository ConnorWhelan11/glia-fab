"""
Adapters - Toolchain integrations.

Modules:
    base        - Base adapter protocol/interface
    codex       - OpenAI Codex CLI adapter
    claude      - Anthropic Claude Code adapter
    crush       - Charmbracelet Crush adapter
    blender     - Blender workcell adapter for asset creation
"""

from dev_kernel.adapters.base import CostEstimate, PatchProof, ToolchainAdapter
from dev_kernel.adapters.codex import CodexAdapter
from dev_kernel.adapters.claude import ClaudeAdapter
from dev_kernel.adapters.crush import CrushAdapter
from dev_kernel.adapters.router import ToolchainRouter, RoutingDecision
from dev_kernel.adapters.blender import (
    BlenderAgentAdapter,
    BlenderAgentConfig,
    BlenderTaskManifest,
    BlenderTaskResult,
    create_blender_adapter,
)
from dev_kernel.adapters.outora import (
    OutoraLibraryAdapter,
    PodPlacement,
    LibraryValidationResult,
    create_outora_adapter,
)

__all__ = [
    # Code adapters
    "ToolchainAdapter",
    "PatchProof",
    "CostEstimate",
    "CodexAdapter",
    "ClaudeAdapter",
    "CrushAdapter",
    "ToolchainRouter",
    "RoutingDecision",
    # Blender adapter
    "BlenderAgentAdapter",
    "BlenderAgentConfig",
    "BlenderTaskManifest",
    "BlenderTaskResult",
    "create_blender_adapter",
    # Outora adapter
    "OutoraLibraryAdapter",
    "PodPlacement",
    "LibraryValidationResult",
    "create_outora_adapter",
]


def get_adapter(name: str, config: dict | None = None) -> ToolchainAdapter | None:
    """
    Get an adapter by name.

    Args:
        name: Adapter name (codex, claude, crush)
        config: Optional adapter configuration

    Returns:
        Adapter instance or None if not found
    """
    adapters: dict[str, type[ToolchainAdapter]] = {
        "codex": CodexAdapter,
        "claude": ClaudeAdapter,
        "crush": CrushAdapter,
    }

    adapter_class = adapters.get(name.lower())
    if adapter_class:
        return adapter_class(config)

    return None


def get_available_adapters() -> list[str]:
    """Get list of available (installed) adapters."""
    available = []

    codex = CodexAdapter()
    if codex.available:
        available.append("codex")

    claude = ClaudeAdapter()
    if claude.available:
        available.append("claude")

    crush = CrushAdapter()
    if crush.available:
        available.append("crush")

    return available
