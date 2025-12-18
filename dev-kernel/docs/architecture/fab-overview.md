# Fab Architecture Overview

## Goal

Extend the Dev Kernel orchestration system to support **Blender asset creation** with a **Realism Gate** that can deterministically prove an agent produced a real-looking asset (not a blob) using canonical headless renders, automated critics, and geometry priors—with iterate-until-pass repair loops.

## Why This Architecture

- **Deterministic Evaluation**: Same asset + config produces identical renders and verdict
- **Blob Rejection**: Multi-signal critics catch deceptive textures on nonsense geometry
- **Auditable**: Full artifact bundle (asset, renders, diagnostics, reports) for every run
- **Agent-Agnostic**: Gate is kernel-owned; agents cannot self-certify
- **Iterate-to-Pass**: Automatic repair loops with failure-code-to-playbook mapping
- **Extensible**: Category-configurable gates (car, furniture, architecture, etc.)

## Scope Boundaries

### Can Guarantee

| Guarantee                | How                                                                |
| ------------------------ | ------------------------------------------------------------------ |
| Deterministic evaluation | Pinned Blender build, CPU rendering, fixed seeds, containerized CI |
| Strong blob rejection    | Multi-view semantics + geometry priors + clay/diagnostic renders   |
| Repeatable pass/fail     | Audit artifacts with full config/hash provenance                   |
| Category correctness     | Multi-view object detection + CLIP classification                  |
| Geometry sanity          | Mesh statistics within plausible bounds                            |

### Cannot Guarantee

| Limitation                               | Mitigation                                                 |
| ---------------------------------------- | ---------------------------------------------------------- |
| Perfect photorealism in arbitrary scenes | Evaluation is harness-relative                             |
| Studio art direction compliance          | Encode in gate configs/priors                              |
| All mesh issues detected                 | Configurable strictness levels                             |
| Adversarial gaming prevention            | Multi-mode renders, subscore floors, periodic gate refresh |

## System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DEV KERNEL                                     │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Scheduler   │  │  Dispatcher  │  │   Verifier   │                  │
│  │              │  │              │  │              │                  │
│  │ - Graph read │  │ - Spawn WC   │  │ - Run gates  │◄─── fab-realism  │
│  │ - Ready set  │  │ - Route tool │  │ - Compare    │     gate         │
│  │ - Fab tags   │  │ - Fab assets │  │ - Vote logic │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│                                              │                           │
│                                              ▼                           │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                       FAB SUBSYSTEM                                │ │
│  │                                                                    │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │ │
│  │  │  Render    │  │  Critics   │  │   Gate     │  │   Repair   │  │ │
│  │  │  Harness   │  │   Stack    │  │  Decision  │  │  Playbook  │  │ │
│  │  │            │  │            │  │            │  │            │  │ │
│  │  │ - Headless │  │ - Category │  │ - Scoring  │  │ - Fail→Fix │  │ │
│  │  │ - Lookdev  │  │ - Align    │  │ - Thresholds│  │ - Templates│  │ │
│  │  │ - Cameras  │  │ - Realism  │  │ - Verdict  │  │ - Context  │  │ │
│  │  │ - Passes   │  │ - Geometry │  │            │  │            │  │ │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
         │                                              ▲
         │  spawn                                       │ Asset+Proof
         ▼                                              │
┌─────────────────────────────────────────────────────────────────────────┐
│                       BLENDER WORKCELL                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Agent (Codex/Claude/etc.)                                       │   │
│  │  ─────────────────────────                                       │   │
│  │  - Generate/repair .blend asset                                  │   │
│  │  - Export canonical .glb                                         │   │
│  │  - Does NOT decide pass/fail                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ARTIFACT STORE                                    │
│                                                                          │
│  fab/runs/<run_id>/                                                      │
│  ├── config/           # Gate configs (verbatim copy)                   │
│  ├── input/            # Prompt, priors, seed                           │
│  ├── asset/            # asset.blend, asset.glb, textures               │
│  ├── render/           # beauty/, clay/, passes/                        │
│  ├── critics/          # Per-critic JSON reports                        │
│  ├── verdict/          # gate_verdict.json                              │
│  ├── logs/             # Blender stdout/stderr, critic logs             │
│  └── manifest.json     # SHA256 for every file + tool versions          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component            | Responsibility                                                           | Interface                              |
| -------------------- | ------------------------------------------------------------------------ | -------------------------------------- |
| **Render Harness**   | Headless Blender rendering with lookdev scene, camera rig, render passes | CLI: `python -m dev_kernel.fab.render` |
| **Critics Stack**    | Multi-signal evaluation (category, alignment, realism, geometry)         | Module: `dev_kernel.fab.critics`       |
| **Gate Decision**    | Aggregate scores, apply thresholds, emit verdict                         | Module: `dev_kernel.fab.gate`          |
| **Repair Playbook**  | Map failure codes to repair instructions                                 | Config: `fab/gates/*.yaml`             |
| **Blender Workcell** | Asset generation/repair by agent                                         | Standard workcell with asset output    |

## Data Flow

```
1. Issue tagged with `asset:car` + `gate:realism` enters ready set
   │
   ├─► Dispatcher creates workcell, writes manifest (includes Fab config)
   │
   ├─► Agent generates/modifies .blend asset in workcell
   │
   ├─► Agent exports canonical .glb
   │
   ├─► Workcell produces Asset+Proof JSON
   │
   ├─► Verifier detects Fab-tagged issue
   │   │
   │   ├─► Invoke Render Harness (beauty + clay + passes)
   │   │
   │   ├─► Invoke Critics Stack (category, alignment, realism, geometry)
   │   │
   │   ├─► Gate Decision aggregates scores → verdict
   │   │
   │   └─► Write gate_verdict.json + critic reports
   │
   ├─► If pass: merge asset, close issue
   │
   ├─► If fail + retries left: create repair issue with failure codes
   │
   ├─► If fail + retries exhausted: escalate to human
   │
   └─► Archive artifacts to fab/runs/<run_id>/
```

## Beads Integration

### Issue Types & Tags

| Tag                | Purpose                               |
| ------------------ | ------------------------------------- |
| `asset:car`        | Asset category (car, furniture, etc.) |
| `gate:realism`     | Invoke Fab realism gate               |
| `render:canonical` | Requires canonical render harness     |
| `critic:category`  | Run category correctness critic       |
| `critic:geometry`  | Run geometry sanity critic            |
| `prior:template`   | Using template-based generation       |
| `prior:scaffold`   | Using procedural scaffold             |

### Extended Issue Fields

```yaml
# Dev Kernel Fab extensions
dk_gate_config_id: "car_realism_v001"
dk_lookdev_scene_id: "car_lookdev_v001"
dk_camera_rig_id: "car_camrig_v001"
dk_iteration_index: 0
dk_parent_run_id: null
dk_last_gate_report_path: null
dk_last_fail_codes: []
```

### Dependency Edges

```
fab.asset.generate → fab.render.canonical → fab.critics.evaluate → fab.gate.verdict
                                                                          │
                                                     On fail: ────────────┘
                                                                          │
                                                                          ▼
                                                              fab.asset.repair
                                                                    │
                                                                    └─► (loops back)
```

## Related Documents

- [Render Harness](./fab-render-harness.md) - Lookdev scene, camera rig, render settings
- [Critics Stack](./fab-critics.md) - Category, alignment, realism, geometry critics
- [Gate Decision Logic](./fab-gate-logic.md) - Scoring, thresholds, verdict emission
- [Iteration Loop](./fab-iteration-loop.md) - Generate → Render → Score → Repair
- [Fab Schemas](./fab-schemas.md) - Asset+Proof, Critic Report, Gate Verdict
- [Priors & Scaffolds](./fab-priors-scaffolds.md) - Templates, procedural rigs, versioning
