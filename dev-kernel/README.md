# Dev Kernel

**Autonomous Multi-Agent Development Orchestrator**

A local-first, deterministic orchestration system that uses **Beads** as the canonical work graph, schedules and dispatches tasks to isolated **Workcells** (git worktree sandboxes), which produce **Patch + Proof** artifacts through quality gates—with optional "speculate + vote" parallelism for high-risk work.

## Features

- 🎯 **Beads-native**: Uses Beads as the single source of truth for all work items
- 🔒 **Isolated Workcells**: Git worktrees prevent cross-contamination
- 🤖 **Multi-agent**: Supports Codex, Claude Code, and [Crush](https://github.com/charmbracelet/crush)
- ⚡ **Parallel execution**: Multiple workcells run simultaneously
- 🗳️ **Speculate + Vote**: Multiple implementations compete for high-risk tasks
- 🛡️ **Quality gates**: Mandatory test/lint/typecheck before merge
- 🔄 **Self-healing**: Failures automatically create new tracked issues
- 📊 **Observable**: Full event logging, metrics, beads_viewer integration
- 🔌 **MCP Server**: Expose kernel tools to external LLM agents

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Quick Start

```bash
# Initialize in your repo (must have Beads initialized)
dev-kernel init

# Run the kernel loop
dev-kernel run

# Run a single issue
dev-kernel run --once --issue 42

# Dry run (no changes)
dev-kernel run --dry-run

# Watch mode (continuous)
dev-kernel run --watch

# Check status
dev-kernel status

# List active workcells
dev-kernel workcells
```

## Deploy to Your Project

```bash
# Deploy to current project
./scripts/deploy.sh .

# Deploy to another project
./scripts/deploy.sh /path/to/project
```

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Data Model](docs/architecture/data-model.md)
- [Scheduling Algorithm](docs/architecture/scheduling.md)
- [Workcell Contract](docs/architecture/workcell-contract.md)
- [Quality Gates](docs/architecture/quality-gates.md)
- [Security & Safety](docs/architecture/security.md)
- [Configuration Guide](docs/guides/configuration.md)
- [Toolchain Adapters](docs/architecture/toolchain-adapters.md)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DEVELOPER                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DEV KERNEL                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Scheduler   │  │  Dispatcher  │  │   Verifier   │              │
│  │  (priority,  │  │  (adapters,  │  │  (gates,     │              │
│  │  critical    │  │  routing,    │  │  voting)     │              │
│  │  path)       │  │  parallel)   │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                            │                                         │
│                    STATE MANAGER (Beads)                            │
│                    EVENT EMITTER (Observability)                    │
└─────────────────────────────────────────────────────────────────────┘
         │                                              ▲
         │  spawn                                       │ Patch+Proof
         ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      WORKCELL POOL                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Codex CLI  │  │ Claude Code │  │    Crush    │                 │
│  │    (o3)     │  │  (sonnet-4) │  │ (multi-LLM) │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Toolchain Adapters

| Adapter    | CLI      | Features                                           |
| ---------- | -------- | -------------------------------------------------- |
| **Codex**  | `codex`  | OpenAI models (o3, o1, GPT-4)                      |
| **Claude** | `claude` | Anthropic models (Sonnet, Opus)                    |
| **Crush**  | `crush`  | Multi-provider (OpenAI, Anthropic, Bedrock, local) |

### Smart Routing

The kernel automatically routes tasks to the best toolchain based on:

- Task complexity and risk level
- Tag matching (e.g., "auth" → Claude)
- Toolchain availability
- Cost optimization

## CLI Reference

```bash
dev-kernel --help           # Show all commands
dev-kernel init             # Initialize kernel
dev-kernel run              # Run kernel loop
dev-kernel run --once       # Single scheduling cycle
dev-kernel run --dry-run    # Preview without changes
dev-kernel run --speculate  # Force speculate+vote mode
dev-kernel status           # Show status
dev-kernel workcells        # List workcells
dev-kernel history          # Show history
dev-kernel stats            # Show statistics
dev-kernel flaky-tests      # Manage flaky tests
dev-kernel escalate         # Manual escalation
dev-kernel cleanup          # Cleanup workcells
```

## Configuration

Create `.dev-kernel/config.yaml`:

```yaml
max_concurrent_workcells: 3
max_concurrent_tokens: 200000
starvation_threshold_hours: 4.0

toolchain_priority:
  - codex
  - claude
  - crush

toolchains:
  codex:
    enabled: true
    timeout_seconds: 1800
    model: o3
  claude:
    enabled: true
    timeout_seconds: 1800
    model: claude-sonnet-4-20250514
  crush:
    enabled: true
    timeout_seconds: 1800
    provider: anthropic

gates:
  test_command: "pytest"
  typecheck_command: "mypy ."
  lint_command: "ruff check ."
  timeout_seconds: 300

speculation:
  enabled: true
  default_parallelism: 2
  vote_threshold: 0.7
  auto_trigger_on_critical_path: true
  auto_trigger_risk_levels:
    - high
    - critical
```

See [Configuration Guide](docs/guides/configuration.md) for full options.

## MCP Server

Dev Kernel exposes an MCP server for integration with external LLM agents:

```bash
# Run MCP server
python -m dev_kernel.mcp.server

# Or via config
{
  "mcpServers": {
    "dev-kernel": {
      "command": "python",
      "args": ["-m", "dev_kernel.mcp.server"]
    }
  }
}
```

### Exposed Tools

- `list_issues` - List all issues
- `get_issue` - Get issue details
- `get_ready` - Get ready issues
- `get_schedule` - Get scheduling plan
- `get_status` - Get kernel status
- `get_events` - Get recent events
- `update_issue_status` - Update issue status
- `create_issue` - Create new issue

## Development Status

| Phase | Status      | Description                               |
| ----- | ----------- | ----------------------------------------- |
| V0    | ✅ Complete | CLI scaffold, state reader, adapters      |
| V1    | ✅ Complete | Full scheduling loop, parallel execution  |
| V2    | ✅ Complete | Crush adapter, router, observability, MCP |
| V3    | 📋 Planned  | Production hardening, advanced features   |

## Test Coverage

```
84 tests passing

├── tests/unit/           (65 tests)
│   ├── test_adapters.py
│   ├── test_scheduler.py
│   ├── test_dispatcher.py
│   └── test_state_manager.py
│
└── tests/integration/    (19 tests)
    └── test_kernel_e2e.py
```

## License

MIT
