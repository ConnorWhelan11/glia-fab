# Architecture Overview

## Goal

Build a local, deterministic orchestration system where **Beads** is the canonical work graph, a **Dev Kernel** schedules and dispatches tasks to isolated **Workcells** (git worktree sandboxes running agent toolchains), which produce **Patch + Proof** artifacts that pass quality gates before merging—with optional "speculate + vote" parallelism for high-risk work.

## Why This Architecture

- **Deterministic**: Every decision is logged; humans can replay/audit any run
- **Safe**: Worktrees provide blast-radius containment; no agent can corrupt main
- **Parallel**: Multiple workcells run simultaneously on independent tasks
- **Agent-Agnostic**: Toolchain adapters abstract over Codex/Claude/OpenCode/Crush
- **Self-Healing**: Failures automatically become new tracked issues with dependency edges
- **Inspectable**: beads_viewer surfaces everything; nothing is hidden

## Core Principles

| #   | Principle                                 | Rationale                                                           |
| --- | ----------------------------------------- | ------------------------------------------------------------------- |
| 1   | **Beads is the single source of truth**   | All work state lives in `.beads/`; no shadow state elsewhere        |
| 2   | **Workcells are disposable and isolated** | Git worktrees prevent cross-contamination; always deletable         |
| 3   | **Patch + Proof or nothing**              | Every workcell produces a standardized artifact or fails explicitly |
| 4   | **Quality gates are mandatory**           | No merge without passing tests/lint/typecheck                       |
| 5   | **Failures create issues, not silence**   | Every failure becomes a tracked Beads issue with dependency edges   |
| 6   | **Human can always intervene**            | `--dry-run`, manual approval modes, easy abort                      |
| 7   | **Deterministic scheduling**              | Same graph state → same scheduling decisions                        |
| 8   | **Defense in depth**                      | Assume agents can be wrong/malicious; multiple verification layers  |
| 9   | **Local-first, network-optional**         | Core functionality works offline (except LLM API calls)             |
| 10  | **Git is the transport**                  | All coordination happens via git commits/branches                   |

## System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DEVELOPER                                  │
│                    (human, IDE, terminal)                           │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DEV KERNEL                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Scheduler   │  │  Dispatcher  │  │   Verifier   │              │
│  │              │  │              │  │              │              │
│  │ - Graph read │  │ - Spawn WC   │  │ - Run gates  │              │
│  │ - Ready set  │  │ - Route tool │  │ - Compare    │              │
│  │ - Crit path  │  │ - Monitor    │  │ - Vote logic │              │
│  │ - Lane pack  │  │ - Collect    │  │ - Select     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    STATE MANAGER                              │  │
│  │  - Read/write Beads atomically                               │  │
│  │  - Status transitions                                         │  │
│  │  - Create failure issues                                      │  │
│  │  - Update dep edges                                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │                                              ▲
         │  spawn                                       │ Patch+Proof
         ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      WORKCELL POOL                                   │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Workcell   │  │  Workcell   │  │  Workcell   │                 │
│  │  (worktree) │  │  (worktree) │  │  (worktree) │                 │
│  │             │  │             │  │             │                 │
│  │  Codex CLI  │  │ Claude Code │  │  OpenCode   │                 │
│  │  ─────────  │  │  ─────────  │  │  ─────────  │                 │
│  │  Task: #42  │  │  Task: #43  │  │  Task: #42  │ ← speculate     │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
         │                                              │
         │                    ▼                         │
         │    ┌─────────────────────────────┐          │
         └───►│      GIT REPOSITORY         │◄─────────┘
              │                             │
              │  main branch                │
              │  .beads/ (source of truth)  │
              │  workcell branches          │
              └─────────────────────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │       BEADS_VIEWER          │
              │                             │
              │  - Graph visualization      │
              │  - Robot endpoints          │
              │  - Agent Mail (optional)    │
              │  - Run history              │
              └─────────────────────────────┘
```

## Component Responsibilities

| Component              | Responsibility                                            | Interface                                      |
| ---------------------- | --------------------------------------------------------- | ---------------------------------------------- |
| **Dev Kernel**         | Orchestration, scheduling, verification, state management | CLI: `dev-kernel run`, config YAML             |
| **Scheduler**          | Compute ready set, critical path, lane packing            | Internal module                                |
| **Dispatcher**         | Spawn workcells, route to toolchains, monitor             | Internal module                                |
| **Verifier**           | Run quality gates, compare candidates, vote selection     | Internal module                                |
| **State Manager**      | Atomic Beads read/write, status transitions               | Wraps `bd` CLI                                 |
| **Workcell**           | Isolated execution environment                            | CLI: `workcell run`, produces Patch+Proof JSON |
| **Toolchain Adapters** | Abstract over Codex/Claude/OpenCode/Crush                 | Plugin interface                               |
| **beads_viewer**       | Observability, graph intelligence, robot outputs          | HTTP + CLI                                     |

## Data Flow

```
1. Dev Kernel starts
   │
   ├─► Read Beads graph: `bd list --json`
   │
   ├─► Query beads_viewer: `bv --robot-plan`
   │
   ├─► Scheduler computes ready set + priority
   │
   ├─► For each ready task (up to concurrency limit):
   │   │
   │   ├─► Dispatcher creates worktree
   │   │   └─► `git worktree add .workcells/wc-{issue_id}-{ts} -b wc/{issue_id}/{ts}`
   │   │
   │   ├─► Dispatcher writes task manifest to workcell
   │   │
   │   ├─► Dispatcher invokes toolchain adapter
   │   │   └─► e.g., `codex --prompt @.workcells/wc-42-xxx/task.md --approval-mode full-auto`
   │   │
   │   ├─► Workcell produces Patch+Proof JSON
   │   │
   │   └─► Verifier runs quality gates on workcell
   │
   ├─► If speculate mode: wait for all candidates, run voting
   │
   ├─► Winning patch: merge to integration branch
   │
   ├─► Update Beads: close issue, update deps
   │
   ├─► On failure: create fix issue with dep edge
   │
   └─► Loop until graph empty or human abort
```

## Related Documents

### Core Kernel

- [Data Model](./data-model.md) - Beads schema, status states, dependency edges
- [Scheduling Algorithm](./scheduling.md) - Ready set, critical path, lane packing
- [Workcell Contract](./workcell-contract.md) - Patch + Proof schema
- [Quality Gates](./quality-gates.md) - Verification and gates
- [Security & Safety](./security.md) - Sandboxing, guardrails
- [Failure Handling](./failure-handling.md) - Self-healing, escalation

### Fab (Asset Creation & Realism Gate)

- [Fab Overview](./fab-overview.md) - High-level Fab/Realism Gate architecture
- [Render Harness](./fab-render-harness.md) - Lookdev scene, camera rig, render settings
- [Critics Stack](./fab-critics.md) - Category, alignment, realism, geometry critics
- [Gate Decision Logic](./fab-gate-logic.md) - Scoring, thresholds, verdict emission
- [Iteration Loop](./fab-iteration-loop.md) - Generate → Render → Score → Repair
- [Fab Schemas](./fab-schemas.md) - Asset+Proof, Critic Report, Gate Verdict
- [Priors & Scaffolds](./fab-priors-scaffolds.md) - Templates, procedural rigs, versioning
