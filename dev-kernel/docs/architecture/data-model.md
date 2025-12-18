# Data Model

## Beads Issue Schema Conventions

All issues in `.beads/issues.jsonl` follow these conventions:

```yaml
# Required fields (Beads native)
id: "42" # Unique issue ID
title: "Implement user auth" # Human-readable title
status: "ready" # State machine status
created: "2025-01-15T10:30:00Z"
updated: "2025-01-15T14:22:00Z"

# Dev Kernel extensions (stored in description or custom fields)
dk_priority: "P1" # P0=critical, P1=high, P2=medium, P3=low
dk_risk: "high" # low, medium, high, critical
dk_size: "M" # XS, S, M, L, XL (t-shirt sizing)
dk_tool_hint: "claude" # Preferred toolchain: codex, claude, opencode, crush, any
dk_speculate: true # Enable speculate+vote for this issue
dk_max_attempts: 3 # Max retry attempts before escalation
dk_forbidden_paths: # Paths this task must not modify
  - "src/auth/secrets.ts"
  - "migrations/"
dk_required_reviewers: 2 # For speculate mode
dk_parent: "40" # Epic/parent issue ID
dk_estimated_tokens: 50000 # Cost estimation hint
```

## Status State Machine

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
    ┌──────┐    ┌───────┐    ┌─────────┐    ┌─────────┐  │
    │ open │───►│ ready │───►│ running │───►│ review  │──┤
    └──────┘    └───────┘    └─────────┘    └─────────┘  │
        │           │             │              │        │
        │           │             │              │        │
        │           │             ▼              ▼        │
        │           │        ┌─────────┐    ┌────────┐   │
        │           │        │ blocked │    │  done  │   │
        │           │        └─────────┘    └────────┘   │
        │           │             │                      │
        │           │             │                      │
        │           └─────────────┼──────────────────────┘
        │                         │
        ▼                         ▼
    ┌──────────┐            ┌───────────┐
    │ wontfix  │            │ escalated │
    └──────────┘            └───────────┘
```

### Status Definitions

| Status      | Meaning                            | Kernel Action                     |
| ----------- | ---------------------------------- | --------------------------------- |
| `open`      | Created but has unmet dependencies | Wait for deps                     |
| `ready`     | All deps met, can be scheduled     | Add to ready set                  |
| `running`   | Workcell is actively working       | Monitor, timeout check            |
| `blocked`   | Failed verification, needs fix     | Create fix issue                  |
| `review`    | Patch produced, awaiting review    | Run vote logic (or human)         |
| `done`      | Merged and verified                | Mark complete, unblock dependents |
| `wontfix`   | Intentionally not doing            | Remove from graph                 |
| `escalated` | Too many failures, needs human     | Alert, stop retrying              |

### Valid Transitions

```python
VALID_TRANSITIONS = {
    "open": ["ready", "wontfix"],
    "ready": ["running", "open", "wontfix"],
    "running": ["review", "blocked", "escalated"],
    "blocked": ["ready", "escalated", "wontfix"],
    "review": ["done", "blocked", "ready"],
    "done": [],  # Terminal
    "wontfix": [],  # Terminal
    "escalated": ["ready", "wontfix"],  # Human can restart
}
```

## Dependency Edge Types

```yaml
# In bd dep add commands
--type blocks        # A blocks B means B cannot start until A is done
--type unblocks      # Inverse relationship (auto-created)
--type discovered    # Runtime discovery: fixing A revealed need for B
--type fix-for       # B is a fix attempt for failed A
--type speculate     # B is a speculative parallel attempt at A's goal
--type review-of     # B is a review task for A's output
```

### Dependency Semantics

- **blocks**: Hard dependency. Issue B cannot transition to `ready` until issue A is `done`.
- **unblocks**: Inverse of blocks (auto-managed by Beads).
- **discovered**: Soft link indicating where a new issue came from. Does not block.
- **fix-for**: Links a fix issue to the original failed issue. The fix blocks the original.
- **speculate**: Links parallel speculative implementations to each other.
- **review-of**: Links a review task to the implementation it's reviewing.

## Tags Convention

```
@kernel:v1           # Kernel version that created/modified
@tool:codex          # Which toolchain worked on this
@attempt:2           # Attempt number (for retries)
@speculate:primary   # Primary speculate candidate
@speculate:alt1      # Alternative speculate candidate
@gate:test-fail      # Which gate failed
@gate:lint-fail
@gate:type-fail
@human-escalated     # Human took over
@auto-merged         # Kernel merged without human review
```

## Size Estimation

T-shirt sizes map to estimated hours:

| Size | Hours | Typical Use                         |
| ---- | ----- | ----------------------------------- |
| XS   | 1     | Trivial fix, typo, config change    |
| S    | 2     | Small feature, simple bug fix       |
| M    | 4     | Medium feature, moderate complexity |
| L    | 8     | Large feature, significant changes  |
| XL   | 16    | Epic-level, multi-file refactor     |

## Priority Levels

| Priority | Meaning  | Scheduling Impact                         |
| -------- | -------- | ----------------------------------------- |
| P0       | Critical | Always scheduled first, blocks other work |
| P1       | High     | Prioritized over medium/low               |
| P2       | Medium   | Normal priority                           |
| P3       | Low      | Scheduled when capacity available         |

## Risk Levels

| Risk     | Meaning                          | Triggers                       |
| -------- | -------------------------------- | ------------------------------ |
| low      | Safe change, well-understood     | Pure additions, tests only     |
| medium   | Some risk, moderate blast radius | Modifies existing code         |
| high     | Significant risk, needs review   | Core logic, security-related   |
| critical | Very high risk                   | Auth, payments, data migration |

High/critical risk triggers speculate+vote mode by default.
