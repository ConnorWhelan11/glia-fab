# Configuration Guide

## Overview

Dev Kernel is configured via a YAML file at `.dev-kernel/config.yaml`. This guide covers all configuration options.

## Quick Start

```bash
# Initialize with default config
dev-kernel init

# Use custom config location
dev-kernel --config ./my-config.yaml run
```

## Full Configuration Reference

```yaml
version: "1.0"

# ============================================
# SCHEDULING
# ============================================
scheduling:
  # Maximum parallel workcells
  max_concurrent_workcells: 4

  # Token budget across all concurrent LLM calls
  max_concurrent_tokens: 500000

  # How often to re-evaluate ready set (seconds)
  scheduling_interval_seconds: 30

  # When to boost priority for waiting issues (hours)
  starvation_threshold_hours: 4

# ============================================
# TOOLCHAINS
# ============================================
toolchains:
  codex:
    enabled: true
    path: "codex" # CLI executable path
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
    enabled: false # Disabled by default
    path: "crush"
    timeout_minutes: 25

# ============================================
# ROUTING
# ============================================
routing:
  rules:
    # Match by explicit hint
    - match: { dk_tool_hint: "codex" }
      use: [codex]

    - match: { dk_tool_hint: "claude" }
      use: [claude]

    # Match by task characteristics
    - match:
        title_pattern: ".*refactor.*"
      use: claude

    - match:
        title_pattern: ".*test.*"
      use: codex

    - match:
        dk_size: ["L", "XL"]
      use: claude

    # Match by risk (triggers speculation)
    - match:
        dk_risk: ["high", "critical"]
      speculate: true
      parallelism: 2
      use: [codex, claude, opencode]

    # Default fallback
    - match: {}
      use: codex

  fallbacks:
    codex: [claude, opencode]
    claude: [codex, opencode]
    opencode: [codex, crush]
    crush: [opencode, codex]

  # Cost/quality/latency weights for selection
  cost_weights:
    codex: 1.0
    claude: 1.2
    opencode: 0.8
    crush: 0.7

  quality_weights:
    codex: 0.9
    claude: 0.95
    opencode: 0.85
    crush: 0.8

# ============================================
# QUALITY GATES
# ============================================
quality_gates:
  required:
    - name: test
      command: "npm test"
      timeout: 300
      retries: 2

    - name: typecheck
      command: "npm run typecheck"
      timeout: 120
      retries: 1

    - name: lint
      command: "npm run lint"
      timeout: 60
      retries: 1

    - name: build
      command: "npm run build"
      timeout: 180
      retries: 1

  optional:
    - name: coverage
      command: "npm run test:coverage"
      threshold: 80

    - name: security
      command: "npm audit --audit-level=high"

  custom:
    - name: forbidden-paths
      type: diff-check
      forbidden:
        - "*.env*"
        - "**/secrets/**"
        - "**/migrations/**"

    - name: max-diff-size
      type: diff-check
      max_lines: 500
      max_files: 20

# ============================================
# SPECULATION
# ============================================
speculation:
  enabled: true
  default_parallelism: 2
  max_parallelism: 3
  vote_threshold: 0.7 # 70% score required for auto-select

  auto_trigger:
    on_critical_path: true
    risk_levels: ["high", "critical"]

  adversarial_review:
    enabled: false
    required_approvals: 1

# ============================================
# RETRY POLICIES
# ============================================
retry:
  max_attempts: 3
  backoff_base_seconds: 60
  backoff_multiplier: 2
  max_backoff_seconds: 3600

  by_failure_class:
    test_failure:
      max_attempts: 3
      same_toolchain: true

    type_error:
      max_attempts: 2
      same_toolchain: true

    timeout:
      max_attempts: 2
      increase_timeout: 1.5
      try_different_toolchain: true

    security_violation:
      max_attempts: 1
      escalate_immediately: true

# ============================================
# SECURITY
# ============================================
security:
  forbidden_paths:
    - ".env*"
    - "**/secrets/**"
    - ".git/**"
    - ".beads/**"

  max_diff_lines: 500
  max_diff_files: 20

  secret_detection:
    enabled: true
    escalate_on_detection: true

  command_validation:
    enabled: true
    log_all_commands: true

# ============================================
# OBSERVABILITY
# ============================================
observability:
  log_level: "info"
  event_log_dir: ".dev-kernel/logs"
  archive_dir: ".dev-kernel/archives"
  beads_viewer_integration: true

  retention:
    event_logs_days: 30
    archived_workcells_days: 7

# ============================================
# FAILURE HANDLING
# ============================================
failure_handling:
  auto_create_fix_issues: true

  escalation:
    max_attempts: 3
    notify_webhook: null # Optional: webhook URL

  self_healing:
    try_different_toolchain_on_failure: true
    add_context_on_low_confidence: true
```

## Environment Variables

Some settings can be overridden via environment:

```bash
DEV_KERNEL_CONFIG=/path/to/config.yaml
DEV_KERNEL_LOG_LEVEL=debug
DEV_KERNEL_MAX_CONCURRENT=2
```

## Project-Specific Overrides

Create `.dev-kernel/config.local.yaml` for local overrides (git-ignored):

```yaml
# Local overrides (not committed)
scheduling:
  max_concurrent_workcells: 2 # Lower for my machine

toolchains:
  codex:
    default_model: "gpt-4" # Use different model locally
```

## Config Validation

```bash
# Validate config file
dev-kernel config validate

# Show effective config (merged with defaults)
dev-kernel config show
```

## Minimal Config

For a minimal setup, only specify what differs from defaults:

```yaml
version: "1.0"

quality_gates:
  required:
    - name: test
      command: "pytest"
    - name: lint
      command: "ruff check ."
    - name: typecheck
      command: "mypy ."
```
