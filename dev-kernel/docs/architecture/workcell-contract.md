# Workcell Contract: Patch + Proof

## Overview

A **Workcell** is a disposable, isolated execution environment (git worktree) where a single agent toolchain works on exactly one task. Every workcell must produce a standardized **Patch + Proof** artifact.

## Required Inputs: Task Manifest

Each workcell receives a **Task Manifest** JSON file at `.workcells/{workcell_id}/manifest.json`:

```json
{
  "schema_version": "1.0.0",
  "workcell_id": "wc-42-20250115T143022Z",
  "issue": {
    "id": "42",
    "title": "Implement user authentication endpoint",
    "description": "Create POST /api/auth/login endpoint...",
    "acceptance_criteria": [
      "Returns JWT on valid credentials",
      "Returns 401 on invalid credentials",
      "Rate limits to 5 attempts per minute"
    ],
    "context_files": ["src/api/routes.ts", "src/auth/types.ts"],
    "forbidden_paths": ["src/auth/secrets.ts"]
  },
  "toolchain": "codex",
  "toolchain_config": {
    "model": "o3",
    "approval_mode": "full-auto",
    "timeout_minutes": 30
  },
  "quality_gates": {
    "test": "npm test",
    "lint": "npm run lint",
    "typecheck": "npm run typecheck",
    "build": "npm run build"
  },
  "speculate_mode": false,
  "max_diff_lines": 500,
  "branch_name": "wc/42/20250115T143022Z"
}
```

## Required Outputs: Patch + Proof

Every workcell produces a `proof.json` file with this structure:

### Core Fields

| Field            | Type   | Required | Description                              |
| ---------------- | ------ | -------- | ---------------------------------------- |
| `schema_version` | string | ✓        | Always "1.0.0"                           |
| `workcell_id`    | string | ✓        | Unique workcell identifier               |
| `issue_id`       | string | ✓        | Issue this workcell worked on            |
| `status`         | enum   | ✓        | success, partial, failed, timeout, error |
| `patch`          | object | ✓        | Git patch information                    |
| `verification`   | object | ✓        | Quality gate results                     |
| `metadata`       | object | ✓        | Execution metadata                       |

### Patch Object

```json
{
  "branch": "wc/42/20250115T143022Z",
  "base_commit": "a1b2c3d4e5f6...",
  "head_commit": "z9y8x7w6v5u4...",
  "diff_stats": {
    "files_changed": 3,
    "insertions": 127,
    "deletions": 12
  },
  "files_modified": [
    "src/api/auth.ts",
    "src/api/routes.ts",
    "tests/auth.test.ts"
  ],
  "forbidden_path_violations": []
}
```

### Verification Object

```json
{
  "gates": {
    "test": {
      "passed": true,
      "exit_code": 0,
      "duration_ms": 4523,
      "output_path": ".workcells/wc-42-xxx/logs/test.log"
    },
    "lint": {
      "passed": true,
      "exit_code": 0,
      "duration_ms": 1200
    },
    "typecheck": {
      "passed": true,
      "exit_code": 0,
      "duration_ms": 3100
    },
    "build": {
      "passed": true,
      "exit_code": 0,
      "duration_ms": 8900
    }
  },
  "all_passed": true,
  "blocking_failures": []
}
```

### Beads Mutations

Workcells can recommend changes to Beads state:

```json
{
  "beads_mutations": [
    {
      "action": "close",
      "issue_id": "42"
    },
    {
      "action": "create",
      "new_issue": {
        "title": "Add auth rate limiting tests",
        "description": "Discovered during implementation...",
        "priority": "P2"
      }
    },
    {
      "action": "dep_add",
      "dep": {
        "from": "42",
        "to": "NEW",
        "type": "discovered"
      }
    }
  ]
}
```

### Follow-ups

Discovered work that should become new issues:

```json
{
  "follow_ups": [
    {
      "title": "Add auth rate limiting tests for edge cases",
      "description": "Need to test: concurrent requests, IP spoofing...",
      "priority": "P2",
      "discovered_from": "42"
    }
  ]
}
```

### Metadata

```json
{
  "metadata": {
    "toolchain": "codex",
    "toolchain_version": "1.2.3",
    "model": "o3",
    "started_at": "2025-01-15T14:30:22Z",
    "completed_at": "2025-01-15T14:52:18Z",
    "duration_ms": 1316000,
    "tokens_used": 47823,
    "cost_usd": 0.95
  }
}
```

## Complete Example

See [schemas/proof.schema.json](../../schemas/proof.schema.json) for the full JSON Schema.

```json
{
  "schema_version": "1.0.0",
  "workcell_id": "wc-42-20250115T143022Z",
  "issue_id": "42",
  "status": "success",
  "patch": {
    "branch": "wc/42/20250115T143022Z",
    "base_commit": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
    "head_commit": "z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4j3i2h1g0",
    "diff_stats": {
      "files_changed": 3,
      "insertions": 127,
      "deletions": 12
    },
    "files_modified": [
      "src/api/auth.ts",
      "src/api/routes.ts",
      "tests/auth.test.ts"
    ],
    "forbidden_path_violations": []
  },
  "commands_executed": [
    {
      "command": "npm test -- --testPathPattern=auth",
      "exit_code": 0,
      "duration_ms": 4523,
      "stdout_path": ".workcells/wc-42-xxx/logs/test-stdout.log"
    }
  ],
  "verification": {
    "gates": {
      "test": { "passed": true, "exit_code": 0, "duration_ms": 4523 },
      "lint": { "passed": true, "exit_code": 0, "duration_ms": 1200 },
      "typecheck": { "passed": true, "exit_code": 0, "duration_ms": 3100 },
      "build": { "passed": true, "exit_code": 0, "duration_ms": 8900 }
    },
    "all_passed": true,
    "blocking_failures": []
  },
  "artifacts": {
    "logs": [".workcells/wc-42-xxx/logs/"],
    "test_report": ".workcells/wc-42-xxx/test-report.json",
    "agent_transcript": ".workcells/wc-42-xxx/transcript.md"
  },
  "confidence": 0.92,
  "risk_classification": "medium",
  "risk_factors": ["Modifies authentication flow", "Adds new API endpoint"],
  "beads_mutations": [{ "action": "close", "issue_id": "42" }],
  "follow_ups": [],
  "metadata": {
    "toolchain": "codex",
    "toolchain_version": "1.2.3",
    "model": "o3",
    "started_at": "2025-01-15T14:30:22Z",
    "completed_at": "2025-01-15T14:52:18Z",
    "duration_ms": 1316000,
    "tokens_used": 47823,
    "cost_usd": 0.95
  }
}
```

## Workcell Lifecycle

1. **Creation**: Kernel creates git worktree, writes manifest
2. **Execution**: Toolchain adapter runs agent in workcell
3. **Verification**: Gates run against workcell code
4. **Collection**: Kernel reads proof.json
5. **Cleanup**: Workcell archived or deleted

## Workcell Naming Convention

```
.workcells/wc-{issue_id}-{timestamp}/
         │   │          │
         │   │          └── ISO8601 timestamp (YYYYMMDDTHHMMSSz)
         │   └── Beads issue ID
         └── "wc" prefix (workcell)
```

## Branch Naming Convention

```
wc/{issue_id}/{timestamp}
```

Example: `wc/42/20250115T143022Z`
