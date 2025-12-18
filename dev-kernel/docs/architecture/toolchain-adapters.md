# Toolchain Adapters

## Overview

Toolchain adapters provide a unified interface for different AI coding agents. The kernel routes tasks to adapters based on configuration rules.

## Adapter Interface

```python
class ToolchainAdapter(Protocol):
    """Common interface for all toolchain adapters"""

    name: str
    supports_mcp: bool
    supports_streaming: bool

    async def execute(
        self,
        manifest: TaskManifest,
        workcell_path: Path,
        timeout: timedelta
    ) -> PatchProof:
        """Execute the task and return Patch+Proof"""
        ...

    async def health_check(self) -> bool:
        """Verify adapter is operational"""
        ...

    def estimate_cost(self, manifest: TaskManifest) -> CostEstimate:
        """Estimate tokens/cost for this task"""
        ...
```

## Supported Toolchains

| Toolchain | MCP Support | Streaming | Best For |
|-----------|-------------|-----------|----------|
| Codex CLI | ✓ | ✓ | General coding, test generation |
| Claude Code | ✓ | ✓ | Large refactors, complex reasoning |
| OpenCode | ✗ | ✓ | Cost-effective tasks |
| Crush | ✓ | ✓ | Terminal-native workflows |

## Codex CLI Adapter

```python
class CodexAdapter(ToolchainAdapter):
    name = "codex"
    supports_mcp = True
    supports_streaming = True

    async def execute(
        self, 
        manifest: TaskManifest, 
        workcell_path: Path, 
        timeout: timedelta
    ) -> PatchProof:
        # Build prompt from manifest
        prompt = self._build_prompt(manifest)

        # Write prompt to file for reproducibility
        prompt_file = workcell_path / "prompt.md"
        prompt_file.write_text(prompt)

        # Execute Codex CLI
        cmd = [
            "codex",
            "--prompt", f"@{prompt_file}",
            "--approval-mode", "full-auto",
            "--model", manifest.toolchain_config.get("model", "o3"),
            "--json"
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

### Codex Configuration

```toml
# ~/.codex/config.toml
[mcp]
servers = ["beads-mcp"]

[defaults]
model = "o3"
approval_mode = "full-auto"
```

## Claude Code Adapter

```python
class ClaudeCodeAdapter(ToolchainAdapter):
    name = "claude"
    supports_mcp = True
    supports_streaming = True

    async def execute(
        self, 
        manifest: TaskManifest, 
        workcell_path: Path, 
        timeout: timedelta
    ) -> PatchProof:
        prompt = self._build_prompt(manifest)
        prompt_file = workcell_path / "prompt.md"
        prompt_file.write_text(prompt)

        cmd = [
            "claude",
            "--print",
            "--output-format", "json",
            "-p", prompt,
            "--allowedTools", "Edit,Write,Bash,Read"
        ]

        # Add MCP config if available
        if (workcell_path / ".mcp.json").exists():
            cmd.extend(["--mcp-config", ".mcp.json"])

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

## OpenCode Adapter

```python
class OpenCodeAdapter(ToolchainAdapter):
    name = "opencode"
    supports_mcp = False
    supports_streaming = True

    async def execute(
        self, 
        manifest: TaskManifest, 
        workcell_path: Path, 
        timeout: timedelta
    ) -> PatchProof:
        prompt = self._build_prompt(manifest)

        cmd = [
            "opencode",
            "--non-interactive",
            "--json-output",
            prompt
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

## Crush Adapter

```python
class CrushAdapter(ToolchainAdapter):
    name = "crush"
    supports_mcp = True
    supports_streaming = True

    async def execute(
        self, 
        manifest: TaskManifest, 
        workcell_path: Path, 
        timeout: timedelta
    ) -> PatchProof:
        prompt = self._build_prompt(manifest)

        cmd = [
            "crush",
            "--non-interactive",
            "--allow", "read,write,execute",
            "--json",
            "-m", prompt
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

## Routing Rules

```yaml
routing:
  rules:
    # Route by task hints
    - match:
        dk_tool_hint: "codex"
      use: codex

    - match:
        dk_tool_hint: "claude"
      use: claude

    # Route by task type
    - match:
        title_pattern: ".*refactor.*"
      use: claude  # Claude good at large refactors

    - match:
        title_pattern: ".*test.*"
      use: codex  # Codex good at test generation

    - match:
        dk_size: ["L", "XL"]
      use: claude  # Claude handles large context well

    # Route by risk
    - match:
        dk_risk: ["high", "critical"]
      speculate: true
      use: [codex, claude, opencode]

    # Default
    - match: {}
      use: codex

  fallbacks:
    codex: [claude, opencode]
    claude: [codex, opencode]
    opencode: [codex, crush]
    crush: [opencode, codex]
```

## Cost & Quality Weights

```yaml
  cost_weights:
    codex: 1.0      # Baseline
    claude: 1.2     # Slightly more expensive
    opencode: 0.8   # Cheaper
    crush: 0.7      # Cheapest

  quality_weights:
    codex: 0.9
    claude: 0.95
    opencode: 0.85
    crush: 0.8

  latency_weights:
    codex: 1.0
    claude: 1.1
    opencode: 0.9
    crush: 0.85
```

## Toolchain Configuration

```yaml
# .dev-kernel/config.yaml
toolchains:
  codex:
    enabled: true
    path: "codex"
    default_model: "o3"
    timeout_minutes: 30
    config:
      approval_mode: "full-auto"

  claude:
    enabled: true
    path: "claude"
    timeout_minutes: 45
    config:
      output_format: "json"
      allowed_tools: ["Edit", "Write", "Bash", "Read"]

  opencode:
    enabled: true
    path: "opencode"
    timeout_minutes: 30
    config:
      non_interactive: true

  crush:
    enabled: false  # Disabled by default
    path: "crush"
    timeout_minutes: 25
```

## Adding Custom Adapters

To add a new toolchain:

1. Create adapter class implementing `ToolchainAdapter`
2. Register in `adapters/__init__.py`
3. Add configuration in `toolchains` section
4. Add routing rules

```python
# dev-kernel/src/dev_kernel/adapters/custom.py
class CustomAdapter(ToolchainAdapter):
    name = "custom"
    supports_mcp = False
    supports_streaming = True

    async def execute(self, manifest, workcell_path, timeout) -> PatchProof:
        # Your implementation
        ...
```

