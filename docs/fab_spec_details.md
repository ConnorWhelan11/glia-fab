Repo scan results:

  ## 1) Codebase Inventory

  Top-level

  - dev-kernel/ — Python “Dev Kernel” orchestrator (this is the real product code).
  - docs/fab_spec_0.md — prior Fab/Realism Gate design spec (doc-only; no implementation).
  - READEME.md — empty placeholder (typo’d README).
  - No .beads/ in this repo root (Dev Kernel expects Beads in the target project repo).

  Dev Kernel (Python package)

  - Core orchestration loop (the “kernel”)
      - dev-kernel/src/dev_kernel/kernel/runner.py — main loop: schedule → dispatch → verify
        → update Beads → cleanup.
      - dev-kernel/src/dev_kernel/kernel/scheduler.py — ready set + critical path + lane
        packing; uses Issue.dk_attempts/dk_max_attempts.
      - dev-kernel/src/dev_kernel/kernel/dispatcher.py — creates workcells + writes
        manifest.json + invokes adapters + merges to main.
      - dev-kernel/src/dev_kernel/kernel/verifier.py — runs “quality gates” and decides pass/
        fail; currently hardwired to test/typecheck/lint.
  - Workcell isolation + lifecycle
      - dev-kernel/src/dev_kernel/workcell/manager.py — git worktrees + archives logs (note:
        archives only files in logs/, not subdirs).
      - dev-kernel/src/dev_kernel/workcell/cli.py — CLI for inside-workcell helpers (log/
        event/gate check stubs).
  - Beads integration (already usable for Glia Fab)
      - dev-kernel/src/dev_kernel/state/manager.py — reads/writes Beads via bd CLI or .beads/
        *.jsonl fallback.
      - dev-kernel/src/dev_kernel/state/models.py — Issue, Dep, BeadsGraph with dk_* fields
        (tags, risk, attempts, forbidden paths, etc).
  - Quality gate runner (reusable for “Realism Gate” if treated as a gate command)
      - dev-kernel/src/dev_kernel/gates/runner.py — runs shell commands + logs; suitable
        wrapper for invoking Blender headless + critics script.
  - Observability
      - dev-kernel/src/dev_kernel/observability/events.py — event schema + reader; kernel
        currently logs events via StateManager.add_event() (dev-kernel/src/dev_kernel/state/
        manager.py).
  - Toolchain adapters (agent execution)
      - dev-kernel/src/dev_kernel/adapters/*.py — Codex/Claude/Crush adapters; compute diffs
        + forbidden path violations deterministically.
  - Schemas (existing)
      - dev-kernel/schemas/manifest.schema.json — workcell input manifest schema (draft-07).
      - dev-kernel/schemas/proof.schema.json — Patch+Proof output schema (draft-07).

  Config state (important mismatch)

  - Code parses a flat config model: dev-kernel/src/dev_kernel/kernel/config.py.
  - Docs/examples describe a richer nested config (quality_gates:, routing:, etc) but code
    does not implement that:
      - dev-kernel/docs/guides/configuration.md
      - dev-kernel/examples/config.yaml, dev-kernel/examples/config-python.yaml, dev-kernel/
        examples/config-minimal.yaml

  3D / Blender / Godot hooks

  - ❌ None found in code. No bpy, no Blender scripts, no .blend, no Godot project files.

  ## 2) Gap Analysis

  Requirement area → status and repo grounding:

  - Canonical headless render harness (Blender)
      - ❌ Missing (no Blender invocation code anywhere under dev-kernel/src/dev_kernel/).
  - Critics stack (category/prompt/realism/geometry)
      - ❌ Missing (no image/mesh critics, no ML deps, no model handling).
  - Priors/templates/scaffolds
      - ❌ Missing (no fab/templates/, no param rigs, no asset library layout).
  - Determinism + audit artifacts + structured JSON reports
      - 🟨 Partially exists:
          - Deterministic orchestration + logging exists (dev-kernel/src/dev_kernel/kernel/
            *.py, dev-kernel/src/dev_kernel/state/manager.py).
          - Workcell archiving exists but won’t preserve render trees unless changed (dev-
            kernel/src/dev_kernel/workcell/manager.py only copies files, not subdirectories).
          - Proof/manifest schemas exist but don’t cover “asset + renders + critic report” as
            first-class objects.
  - Gate decision logic (kernel-owned pass/fail)
      - 🟨 Partially exists:
          - Verifier exists (dev-kernel/src/dev_kernel/kernel/verifier.py) but only runs code
            gates (test/typecheck/lint) and doesn’t know about asset gates.
  - Iteration loop (generate → render → score → repair)
      - 🟨 Partially exists:
          - Attempts counters exist (Issue.dk_attempts/dk_max_attempts in dev-kernel/src/
            dev_kernel/state/models.py, and scheduler checks them in dev-kernel/src/
            dev_kernel/kernel/scheduler.py).
          - But kernel failure path sets status to "blocked" (dev-kernel/src/dev_kernel/
            kernel/runner.py), and scheduler only re-runs "open"/"ready" issues → no
            automatic retry loop today.
  - Beads integration and work graph logging
      - ✅ Exists (dev-kernel/src/dev_kernel/state/manager.py, dev-kernel/src/dev_kernel/
        state/models.py).
  - Workcell contracts / schemas
      - ✅ Exists for code tasks (dev-kernel/schemas/manifest.schema.json, dev-kernel/
        schemas/proof.schema.json)
      - ❌ Missing for Fab-specific outputs (asset proof, critic report, gate verdict).

  ## 3) Delta Architecture

  Text diagram showing how Fab/Realism Gate fits into current Dev Kernel:

  Beads (.beads/*)  <-- already supported by StateManager
     |
     v
  KernelRunner (dev-kernel/src/dev_kernel/kernel/runner.py)
     |
     +--> Scheduler (scheduler.py)  [unchanged]
     |
     +--> Dispatcher (dispatcher.py)
     |      - creates git worktree workcell (WorkcellManager)
     |      - writes manifest.json
     |      - runs agent adapter (Codex/Claude) in workcell
     |
     +--> Verifier (verifier.py)  [needs extension]
            - runs GateRunner commands
            - NEW: run `fab-realism` gate for asset-tagged issues
                  -> Blender headless render harness (NEW module)
                  -> Critics (NEW module)
                  -> JSON report + verdict (NEW schemas)
     |
     +--> StateManager updates issue status + writes events.jsonl
     |
     +--> WorkcellManager archives logs (needs recursive copy for render artifacts)

  New modules/data to introduce (minimal for V0):

  - Data/config: fab/lookdev/, fab/gates/
  - Code: dev-kernel/src/dev_kernel/fab/ (render harness + critic(s) + gate runner)
  - Schemas: dev-kernel/schemas/fab/

  ## 4) Concrete Implementation Plan (V0 → V1)

  ### V0: deterministic render harness + one critic + JSON report (smallest viable path)

  1. Add Fab data/config scaffold

  - Owner: Kernel (repo data)
  - Targets:
      - Create fab/lookdev/ (scene/rig descriptors)
      - Create fab/gates/ (versioned thresholds, e.g. car_realism_v001.yaml)
  - Acceptance:
      - Gate config file is versioned and hashable; stored in repo; referenced by ID.
  - Blast radius/risk: Low (new files only).

  2. Add “fab-realism” gate executable (kernel-owned)

  - Owner: Kernel
  - Targets (new):
      - dev-kernel/src/dev_kernel/fab/gate.py (entry point: run render harness + critic(s) +
        emit report JSON + exit 0/1)
      - dev-kernel/src/dev_kernel/fab/config.py (loads gate config + lookdev paths)
  - Acceptance:
      - Running the gate produces:
          - canonical renders (beauty + clay at minimum),
          - report.json with deterministic metadata (gate_config_id, blender version, seed,
            file hashes),
          - stable exit code semantics (0 pass, nonzero fail).
  - Blast radius/risk: Medium (new module + introduces Blender dependency externally).

  3. Integrate gate selection into existing kernel verification

  - Owner: Kernel
  - Targets (edit):
      - dev-kernel/src/dev_kernel/kernel/dispatcher.py — include issue tags in manifest.json
        (currently tags are not included), and add/override quality_gates when tags include
        asset:* / gate:realism.
      - dev-kernel/src/dev_kernel/kernel/verifier.py — stop hardwiring gates to test/
        typecheck/lint; read workcell_path/manifest.json["quality_gates"] and run those via
        GateRunner.
  - Acceptance:
      - Code tasks keep working (manifest includes standard gates).
      - Asset-tagged tasks run fab-realism gate instead of (or in addition to) code gates.
  - Blast radius/risk: High (touches core dispatch/verify path for all tasks).

  4. Fix artifact retention for render outputs

  - Owner: Kernel
  - Targets (edit):
      - dev-kernel/src/dev_kernel/workcell/manager.py — archive logs/ recursively (today it
        only copies files in logs/, so logs/fab/* directories would be lost).
  - Acceptance:
      - Canonical renders + report JSON survive cleanup under .dev-kernel/archives/
        <workcell_id>/.
  - Blast radius/risk: Medium (affects archive size; but localized).

  5. Make verification auditable in proof artifacts

  - Owner: Kernel
  - Targets (edit):
      - dev-kernel/src/dev_kernel/kernel/verifier.py and/or dev-kernel/src/dev_kernel/kernel/
        runner.py — persist updated proof.verification back to workcell_path/proof.json
        before cleanup (today it only mutates the in-memory object).
  - Acceptance:
      - Archived proof.json reflects actual gate results (including fab-realism pass/fail +
        paths to report artifacts).
  - Blast radius/risk: Medium (changes audit behavior).

  ### V1: full critics + priors + iterate loop

  6. Expand critics stack

  - Owner: CriticCell (implemented as kernel-run critics initially; later separable)
  - Targets (new):
      - dev-kernel/src/dev_kernel/fab/critics/ (category/alignment/realism/geometry)
      - Optional: fab/critics/models/manifest.json (offline weights registry + sha256)
  - Acceptance:
      - Multi-view scoring + failure codes in report JSON; “blob” rejection improves via clay
        + geometry + category checks.
  - Blast radius/risk: High (dependencies, model weight distribution, performance).

  7. Add priors/templates

  - Owner: BlenderCell (agent-assisted) + Kernel (versioning)
  - Targets (new):
      - fab/templates/ (immutable template versions)
      - fab/scaffolds/ (Geometry Nodes rigs, versioned)
  - Acceptance:
      - Gate can enforce “template/scaffold adherence” rules; agents can converge faster.
  - Blast radius/risk: Medium–High (binary assets, drift/versioning).

  8. Enable automatic iterate-until-pass for asset issues

  - Owner: Kernel
  - Targets (edit):
      - dev-kernel/src/dev_kernel/kernel/runner.py failure path: avoid permanent "blocked"
        for retryable gate failures; either re-open the issue or create a child “repair”
        issue with dependency edges.
      - dev-kernel/src/dev_kernel/state/manager.py updates: add fields like
        dk_last_gate_report_path, dk_last_fail_codes.
  - Acceptance:
      - Asset issues retry up to dk_max_attempts automatically, with critic feedback injected
        into the next manifest/issue description.
  - Blast radius/risk: High (core scheduling semantics change).

  ## 5) Interfaces & Schemas (final)

  Where schemas should live

  - Keep consistency with existing draft-07 schemas in dev-kernel/schemas/:
      - dev-kernel/schemas/fab/asset-proof.schema.json
      - dev-kernel/schemas/fab/critic-report.schema.json
      - dev-kernel/schemas/fab/gate-verdict.schema.json

  Versioning

  - Follow existing schema_version: "1.0.0" pattern (see dev-kernel/schemas/
    proof.schema.json).
  - Version filenames by semantic suffix if you expect parallel support, e.g. critic-
    report.schema.v1.json.

  Consumption

  - Kernel validates reports using existing dependency jsonschema (dev-kernel/pyproject.toml)
    before accepting pass/fail.
  - Gate runner writes report.json + verdict.json; Verifier records paths in proof.artifacts
    and/or proof.verification.gates["fab-realism"].

  ## 6) Immediate Next Steps (first 5 commits worth)

  1. Commit: “Add Fab folder scaffold + gate config v001”

  - Files:
      - fab/gates/car_realism_v001.yaml
      - fab/lookdev/README.md (spec + invariants)
  - Validates:
      - python -c "import yaml; yaml.safe_load(open('fab/gates/car_realism_v001.yaml'))"

  2. Commit: “Introduce Fab schemas (draft-07) + report conventions”

  - Files:
      - dev-kernel/schemas/fab/critic-report.schema.json
      - dev-kernel/schemas/fab/gate-verdict.schema.json
  - Validates:
      - python -c "import json; json.load(open('dev-kernel/schemas/fab/gate-
        verdict.schema.json'))"

  3. Commit: “Add fab-realism gate entrypoint (no Blender yet) + deterministic report
     skeleton”

  - Files:
      - dev-kernel/src/dev_kernel/fab/gate.py
      - dev-kernel/src/dev_kernel/fab/config.py
  - Validates:
      - python -m dev_kernel.fab.gate --help
      - python -m dev_kernel.fab.gate --dry-run --out logs/fab (should emit report JSON
        deterministically)

  4. Commit: “Wire manifest-driven gates + asset-tag routing”

  - Files:
      - dev-kernel/src/dev_kernel/kernel/dispatcher.py (include issue.tags; set quality_gates
        based on tags)
      - dev-kernel/src/dev_kernel/kernel/verifier.py (run gates from
        manifest.json["quality_gates"])
  - Validates:
      - pytest -q under dev-kernel/ (existing integration/unit tests)

  5. Commit: “Archive render trees + persist verified proof.json”

  - Files:
      - dev-kernel/src/dev_kernel/workcell/manager.py (recursive logs archiving)
      - dev-kernel/src/dev_kernel/kernel/verifier.py (write updated proof back to disk)
  - Validates:
      - Run a mocked workcell flow (existing tests) and confirm .dev-kernel/archives/
        <workcell_id>/ contains nested logs/ artifacts and updated proof.json.
