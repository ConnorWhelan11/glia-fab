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

        # Execute Codex CLI (non-interactive)
        cmd = [
            "codex",
            "exec",
            "-",  # read prompt from stdin
            "--sandbox", "workspace-write",
            "--ask-for-approval", "never",
            "--model", manifest.toolchain_config.get("model", "gpt-5.2"),
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(input=prompt.encode()),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

### Codex Configuration

```yaml
# .dev-kernel/config.yaml
toolchains:
  codex:
    default_model: gpt-5.2
    config:
      sandbox: workspace-write
      ask_for_approval: never
      # extra_args:
      #   - "-c"
      #   - "reasoning.effort=\"high\""
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
            "--print", f"@{prompt_file}",
            "--model", manifest.toolchain_config.get("model", "opus"),
            "--output-format", "json",
            "--allowedTools", "Edit", "Write", "Bash", "Read",
            "--dangerously-skip-permissions",
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
        prompt_file = workcell_path / "prompt.md"
        prompt_file.write_text(prompt)

        cmd = [
            "opencode",
            "run",
            "--format", "json",
            "--file", str(prompt_file),
            "--model", manifest.toolchain_config.get("model", "openai/gpt-5-nano"),
            "Execute the task described in prompt.md",
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
            "-y",
            "run",
            "--quiet",
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workcell_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            result.communicate(input=prompt.encode()),
            timeout=timeout.total_seconds()
        )

        return self._parse_output(stdout, manifest, workcell_path)
```

## Routing Rules

```yaml
routing:
  rules:
    # Route by task hints
    - match: { dk_tool_hint: "codex" }
      use: [codex]

    - match: { dk_tool_hint: "claude" }
      use: [claude]

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
    - match: { dk_risk: ["high", "critical"] }
      speculate: true
      parallelism: 2
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
