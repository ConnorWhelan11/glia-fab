Goal: build a deterministic, auditable “Realism Gate” that can prove a Blender agent
produced a real-looking car (not a blob) using canonical headless renders + automated
critics + geometry priors, and drive iterate-until-pass repair loops.

———

## 1) Executive Summary

Glia Fab’s next phase adds a Realism Gate pipeline to the Dev Kernel + Workcells system,
extending beyond code into Blender asset creation (and later Godot assembly). The gate is
kernel-owned (agents cannot self-certify), and evaluates assets only via:

- Canonical headless renders from a versioned lookdev scene + camera rig (no viewport
  screenshots),
- Multi-signal critics (semantic category, prompt alignment, realism/quality, geometry
  sanity),
- Optional priors/scaffolds (template meshes or procedural rigs) to constrain search.

Every run emits a fully replayable artifact bundle (asset, renders, diagnostics, logs,
configs) plus structured JSON reports and a versioned gate verdict. The kernel then
iterates: generate → render → score → repair until pass, cap, or human escalation.

———

## 2) Definitions

### 2.1 What “real-looking car” means (operational)

An asset is a “real-looking car” if and only if it passes a category-specific gate
configuration (gate_config_id) that enforces:

1. Semantic correctness: rendered views consistently classify as “car” (not “blob/other
   object”).
2. Prompt alignment: images match the prompt better than decoys (margin-based).
3. Visual plausibility: no-reference image quality + realism heuristics exceed thresholds
   across views and render modes (beauty + clay/diagnostic).
4. Geometry sanity: mesh statistics and structural priors fall within plausible bounds for
   cars (scale, symmetry, ground contact, wheel-likeness, manifold-ish constraints,
   material validity).

“Real-looking” is defined relative to a fixed lookdev harness; it is not an artistic
judgment and does not guarantee production readiness.

### 2.2 Scope boundaries (what the gate can/can’t guarantee)

Can guarantee (within the harness):

- Deterministic evaluation given pinned versions/configs.
- Strong blob rejection via multi-view semantics + geometry priors + clay/diagnostic
  renders.
- Repeatable pass/fail outcomes with audit artifacts.

Cannot guarantee:

- Perfect photorealism in arbitrary lighting/scenes.
- Compliance with a studio’s art direction unless encoded into configs/priors.
- Absence of all mesh issues (e.g., minor non-manifold edges) unless strictly required.
- That an adversarial agent can’t optimize to the gate over time (mitigations reduce this).

———

## 3) System Architecture

### 3.1 Components

Dev Kernel (source of truth)

- Orchestrates bead graph execution.
- Owns gate configs, thresholds, versions.
- Collects artifacts, runs critics, produces gate verdicts.
- Generates repair tasks from failure codes (agent instructions).

Blender Workcell

- Generates/repairs assets (freeform or template/scaffold).
- Exports canonical asset formats (.blend + .glb).
- Does not decide pass/fail.

Render Harness (Blender headless, kernel-invoked)

- Loads versioned lookdev scene.
- Imports asset, normalizes scale/orientation deterministically.
- Renders canonical views and diagnostic passes to artifact store.

Critic Workcell(s)

- Run deterministic analyses over:
  - Canonical beauty renders,
  - Canonical clay/diagnostic renders,
  - Render passes (mask/depth/normal),
  - Mesh file (.glb or converted .obj/.ply).
- Emit structured JSON with scores + failure reasons.

(Later) Godot Workcell

- Imports passing assets into a canonical Godot test scene.
- Verifies import sanity (scale, material count, draw calls budgets).
- Produces separate “engine integration” gate (not part of realism gate V0).

### 3.2 Artifact store layout (run-addressable, immutable)

fab/runs/<run_id>/

- config/ (all configs used, copied verbatim)
- input/ (prompt, priors/template refs, seed/material policies)
- asset/ (asset.blend, asset.glb, optional textures)
- render/
  - beauty/ (png/exr)
  - clay/
  - passes/ (mask/, depth/, normal/)
- critics/ (per-critic JSON + any derived images)
- verdict/ (gate_verdict.json, summary.md optional)
- logs/ (blender stdout/stderr, critic logs)
- manifest.json (sha256 for every file + tool versions)

### 3.3 Beads as canonical work graph

Treat each stage as an immutable bead producing typed outputs:

- fab.asset.generate → outputs Blender Workcell “Asset + Proof”
- fab.render.canonical → outputs canonical renders + manifest
- fab.critics.evaluate → outputs critic report
- fab.gate.verdict → outputs gate verdict (pass/fail + next action bead)
- fab.asset.repair → loops to fab.render.canonical

———

## 4) Canonical Render Harness

### 4.1 Lookdev scene spec (versioned)

Store as .blend with strict invariants:

- World: single HDRI (pinned file + rotation), plus optional key/fill/rim area lights.
- Ground: shadow catcher plane at z=0, neutral gray, subtle roughness; optional curved
  backdrop.
- Color management: pinned (Filmic or Standard), fixed exposure/contrast.
- Render layers/passes:
  - Beauty (RGBA)
  - Object mask (Cryptomatte or Object Index)
  - Depth (linear)
  - Normal (world or camera space)

Include a clay override collection/view layer where all materials are overridden by a
neutral Principled material (matte gray), to expose geometry independent of textures.

### 4.2 Camera rig spec (required views + turntable)

Versioned rig definition (stored as JSON + embedded cameras/empties in .blend):

- Fixed cameras (minimum set):
  - front_3q (front three-quarter, eye height)
  - rear_3q
  - side_left
  - front
  - top (slightly forward)
  - close_wheel_front (macro-ish)
- Turntable:
  - Rotate object around vertical axis (z), N frames (e.g., 12 frames at 30° increments).
  - Render both beauty and clay at these frames.

Deterministic placement rules:

- Asset origin is normalized to center; lowest vertex touches ground plane.
- Camera distances derived from bounding box diagonal to keep consistent framing across
  assets.

### 4.3 Render settings (determinism-first defaults)

Initial defaults (tunable via config, but pinned per gate version):

- Engine: CYCLES
- Device: CPU-only (for determinism baseline)
- Resolution: 768x512 (V0), scalable to 1024x768 (V1)
- Samples: 128 (no adaptive sampling in V0)
- Seed: fixed integer from run config (e.g., seed=1337)
- Denoiser: off in V0 (avoid nondeterministic denoise variance)
- Film: transparent off (we want ground/shadows), consistent exposure
- Output: PNG (16-bit where available) for beauty/clay; EXR optional for depth/normal if
  needed
- Threads: fixed count (optionally 1 for maximal determinism; or pinned N)

### 4.4 Headless invocation strategy + stability

Kernel runs Blender in a controlled mode:

- --background (-b), --factory-startup, --noaudio
- Explicitly set:
  - Blender version (pinned binary)
  - Render config hash
  - Environment vars for determinism (PYTHONHASHSEED, pinned thread counts)
- Output all logs to fab/runs/<run_id>/logs/

Stability considerations:

- Prefer containerized Linux for CI repeatability (pinned OS libs).
- On local macOS/Windows, determinism is “best effort” unless running the same container.

———

## 5) Critics Stack Design

All critics must be:

- Deterministic (CPU inference, fixed seeds, deterministic ops),
- Versioned (model name + weight hash),
- Auditable (inputs/outputs recorded, per-view results).

Each critic emits:

- score in [0,1] (or structured metrics normalized),
- fail_codes[] (stable identifiers),
- evidence (per-view details, bounding boxes, key metrics).

### 5.1 Category correctness (car / not-car across views)

Purpose: reject blobs and wrong categories even if “pretty” renders exist.

Inputs:

- Beauty renders (fixed + turntable)
- Clay renders (same views)
- Mask pass (optional, for sanity)

Method (recommended ensemble):

1. Object detector with COCO “car” class over beauty views (robust to pose):
   - Options: YOLOv8/YOLOv5, DETR (torchvision), Faster R-CNN.
2. Zero-shot classifier on both beauty and clay using OpenCLIP:
   - Compare logits for: ["a photo of a car", "a blob", "a chair", "a truck", ...].
   - Require car to win with margin.

Why it catches blobs:

- Blobs fail detector confidence and/or produce unstable detections across turntable
  frames.
- Clay views remove texture cheating; blob geometry is exposed.

Outputs (per view):

- car_detect_conf
- bbox_area_ratio
- clip_car_margin
- pass_view: bool

Failure modes:

- Stylized cars may score low (mitigate via category configs: “stylized_car” vs
  “realistic_car”).
- Unusual camera framing (mitigate via fixed rig + normalization).

Selection criteria for models:

- Permissive license, offline weights, CPU feasibility, stable inference.
- Proven performance on natural images of cars.

### 5.2 Prompt alignment (text ↔ image similarity)

Purpose: ensure the asset matches the run’s prompt (e.g., “red 1990s sedan with silver
rims”).

Inputs:

- Beauty fixed views (subset, e.g., 6)
- Prompt string + optional negative prompt + decoy prompts

Method:

- Compute OpenCLIP embeddings for images and text.
- Score:
  - sim(prompt, image) averaged across views
  - Margin vs decoys: sim(prompt) - max(sim(decoy_i))
- Optional attribute probes for color/style via specialized text probes (e.g., “red car”,
  “blue car”).

Why it catches blobs:

- Even if category critic is weak, blobs typically have low semantic alignment and low
  margins.

Failure modes:

- Prompts describing subtle details (interior trim) may not be visible in canonical views
  (mitigate by prompt-to-view mapping or adding close-ups).

### 5.3 Realism / image quality scoring (multi-view)

Purpose: penalize obviously synthetic/low-quality outputs and common failure patterns
(noise, flat shading, missing textures).

Inputs:

- Beauty renders (fixed + limited turntable)
- Optional: material metadata from Blender export

Signals (multi-signal, not one metric):

- Aesthetic/realism predictor (e.g., LAION aesthetic head on CLIP embeddings) →
  aesthetic_score.
- No-reference quality (e.g., BRISQUE/NIQE from piq/OpenCV) → quality_score.
- Artifact checks:
  - Noise estimate (variance in flat regions)
  - Saturation/clipping %
  - “Pink/missing texture” detection (magenta pixel heuristic)
  - Low texture entropy (overly uniform materials)

Why it catches blobs:

- Blobs often render as smooth, low-detail shapes with abnormal entropy/edge complexity;
  combined with semantic critics it becomes decisive.

Failure modes:

- High-quality stylized renders could pass realism metrics (mitigate with category config
  for “photorealistic_car” requiring stricter geometry priors).

### 5.4 Geometry sanity checks (wheels, symmetry, proportions, manifold-ish)

Purpose: reject “car-looking textures on nonsense geometry” and catch 3D-unusable meshes.

Inputs:

- Mesh file (.glb preferred, deterministic export)
- Mask/depth/normal passes (optional cross-check)

Geometry metrics (car defaults):

- Scale plausibility (meters):
  - length in [3.0, 6.0], width [1.4, 2.5], height [1.0, 2.5] (configurable)
- Triangle/vertex counts:
  - min triangles (e.g., > 5k) to reject trivial blobs
  - max triangles budget (e.g., < 500k) for practicality
- Connected components:
  - expect multiple components (body + 4 wheels often separate), but allow fused meshes
    with wheel-like subregions
- Symmetry:
  - approximate bilateral symmetry score across longitudinal plane (configurable
    tolerance)
- Ground contact:
  - lowest points should form ~4 clusters (wheels) rather than one continuous smear
- Wheel-likeness heuristic (configurable strictness):
  - detect 4 wheel candidates near corners using component clustering + aspect ratios
    (cylindrical bounding boxes)
- Manifold-ish constraints:
  - % non-manifold edges below threshold
  - % degenerate faces below threshold
  - normals consistency above threshold
- Material sanity:
  - no missing textures references
  - Principled-like PBR parameters present
  - UVs exist (if textures used)

Recommended open-source libs:

- Mesh: trimesh, meshio, pymeshfix (repair suggestions), open3d (clustering)
- Image: open_clip, torchvision detectors or ultralytics (detector), piq for quality
  metrics

Criteria for choosing libs/models:

- Offline, reproducible CPU inference; stable APIs; permissive licensing; widely used/
  maintained.

———

## 6) Priors & Scaffolds

### 6.1 Template-first (base asset library)

Idea: start from vetted base cars that already pass the gate; agents modify parameters/
materials rather than inventing topology.

- fab/templates/car/<template_id>/<version>/asset.blend + asset.glb
- Each template ships with:
  - Named parts (Body, Wheel_FL, Wheel_FR, …)
  - Correct scale/orientation/pivot
  - Baseline PBR materials

Benefits: massively reduces blob risk; faster convergence.

### 6.2 Procedural scaffold (Geometry Nodes / param rigs)

Idea: a versioned parametric rig that outputs a car-like scaffold: wheel placement, body
volume envelope, basic proportions.

- Agents edit parameters (wheelbase, track width, roofline, fender radius) plus optional
  mesh refinement.
- Gate can enforce “scaffold adherence” early (V1): wheel count/placement becomes reliable.

Tooling note: Geometry Nodes is generally more stable than external graph add-ons; Sverchok
is powerful but can be brittle across versions—use only if pinned tightly.

### 6.3 Agent interaction model

- Preferred path: parameter edits + constrained mesh edits on templates/scaffolds.
- Freeform path: allowed, but must pass stricter geometry sanity + clay-view semantic
  checks.

### 6.4 Versioning & drift prevention

- Templates/scaffolds are immutable once published; changes require new semantic version.
- Gate config references exact template/scaffold version + sha256.
- Add “golden render tests” for each template (render + critic snapshot) so template
  updates can’t silently degrade.

———

## 7) Gate Decision Logic

### 7.1 Hard fails vs soft fails

Hard fails (immediate reject):

- Export/import failure, missing files, invalid meshes
- No “car” detection in required minimum views
- Scale wildly implausible
- Extreme poly counts (too low/high)
- Missing textures/material errors (configurable severity)

Soft fails (score-based):

- Prompt alignment below threshold
- Realism/quality below threshold
- Geometry priors marginal (symmetry low, wheels ambiguous, etc.)

### 7.2 Aggregation

Define per-category gate_config:

- Per-critic required minimums
- Weighted aggregate score:
  - S = w_cat*S_cat + w_align*S_align + w_real*S_real + w_geo*S_geo
- Require:
  - no hard fails
  - S >= pass_threshold
  - and key sub-scores above floors (prevents “one metric carries all”)

### 7.3 Confidence bands & “speculate + vote”

If S is within a narrow band of the threshold or critics disagree:

- Run a deterministic “vote pack”:
  - additional turntable frames (e.g., +12)
  - one alternate HDRI (versioned, fixed)
  - second detector model (ensemble)
- Aggregate via fixed rules (median/majority), recorded in the report.

### 7.4 Preventing Goodharting

- Use multiple render modes (beauty + clay + passes) so textures can’t hide geometry.
- Enforce both semantic and geometry constraints.
- Keep some checks opaque to the agent (agents receive failure codes + guidance, not full
  scoring formula).
- Periodically update gate versions with regression sets (good/bad assets) to reduce
  overfitting.

———

## 8) Iteration Loop: Generate → Render → Score → Repair

### 8.1 State machine (exact transitions)

Pseudocode:

state INIT -> GENERATE
state GENERATE -> EXPORT
state EXPORT -> RENDER
state RENDER -> CRITIC
state CRITIC -> VERDICT

state VERDICT:
if pass: DONE
else if hard_fail and retries_left: REPAIR(hard_fail_codes)
else if soft_fail and retries_left: REPAIR(top_soft_fail_reasons)
else: ESCALATE(human_review)

state REPAIR -> GENERATE // repair happens in Blender workcell
state ESCALATE -> DONE // terminal with "needs human"

### 8.2 Translating critic feedback into repair instructions

Maintain a deterministic mapping from fail_code → repair_playbook entries, e.g.:

- CAT_NO_CAR_DETECTED → “Add recognizable car silhouette; ensure 4 wheels; verify scale;
  re-render clay preview.”
- GEO_WHEEL_COUNT_LOW → “Model/instantiate 4 wheel components; place near corners; ensure
  ground contact at z=0.”
- MAT_MISSING_TEXTURES → “Pack textures or embed into glTF; avoid external paths; ensure
  Principled BSDF.”
- REAL_NOISY_RENDER → “Increase material roughness realism; add surface detail; avoid
  emissive hacks.”

The kernel composes a repair task with:

- failing views thumbnails (from canonical renders),
- key metrics,
- recommended template/scaffold fallback if repeated failures.

### 8.3 Retry caps, escalation, human review triggers

Defaults (configurable):

- Max iterations: 5
- Escalate immediately if:
  - repeated hard fail same code ≥ 2 times,
  - mesh import crashes Blender,
  - critic inconsistency persists after vote pack,
  - suspected adversarial behavior (e.g., semantic pass but geometry catastrophically
    fails).

———

## 9) Beads Integration

### 9.1 Issue types/tags/fields (Fab)

Suggested bead tags/fields:

- Tags: asset:car, gate:realism, render:canonical, critic:category, critic:geometry,
  prior:template, prior:scaffold
- Fields:
  - run_id, asset_id, category
  - gate_config_id, lookdev_scene_id, camera_rig_id
  - iteration_index, parent_run_id
  - artifact_root (path/URI)
  - verdict (pass/fail/escalate)

### 9.2 Dependency edges

- fab.asset.generate → fab.render.canonical → fab.critics.evaluate → fab.gate.verdict
- On fail: fab.gate.verdict → fab.asset.repair (edge includes failure codes)

### 9.3 Logging back to Beads

Each bead stores:

- Hashes of inputs/outputs
- Links to:
  - fab/runs/<run_id>/manifest.json
  - fab/runs/<run_id>/verdict/gate_verdict.json
  - Render previews (beauty/clay)

———

## 10) Workcell Contracts (JSON Schemas)

Use JSON Schema draft 2020-12; all objects additionalProperties: false.

### 10.1 Blender workcell output (“Asset + Proof”)

{
"$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "fab.schema.blender_asset_output.v1",
"type": "object",
"additionalProperties": false,
"required": ["schema_version", "run_id", "asset_id", "category", "files", "metadata"],
"properties": {
"schema_version": { "type": "string", "const": "1.0" },
"run_id": { "type": "string" },
"asset_id": { "type": "string" },
"category": { "type": "string" },
"source": {
"type": "object",
"additionalProperties": false,
"required": ["agent_id", "timestamp_utc"],
"properties": {
"agent_id": { "type": "string" },
"timestamp_utc": { "type": "string", "format": "date-time" },
"template_ref": { "type": "string" },
"scaffold_ref": { "type": "string" }
}
},
"files": {
"type": "object",
"additionalProperties": false,
"required": ["blend_path", "glb_path", "manifest_sha256"],
"properties": {
"blend_path": { "type": "string" },
"glb_path": { "type": "string" },
"textures_dir": { "type": "string" },
"manifest_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
}
},
"metadata": {
"type": "object",
"additionalProperties": false,
"required": ["blender_version", "exporter", "geometry_stats", "material_stats"],
"properties": {
"blender_version": { "type": "string" },
"exporter": {
"type": "object",
"additionalProperties": false,
"required": ["format", "settings_hash"],
"properties": {
"format": { "type": "string", "enum": ["glb"] },
"settings_hash": { "type": "string" }
}
},
"geometry_stats": {
"type": "object",
"additionalProperties": false,
"required": ["triangle_count", "vertex_count", "bounds_m"],
"properties": {
"triangle_count": { "type": "integer", "minimum": 0 },
"vertex_count": { "type": "integer", "minimum": 0 },
"bounds_m": {
"type": "object",
"additionalProperties": false,
"required": ["x", "y", "z"],
"properties": {
"x": { "type": "number" },
"y": { "type": "number" },
"z": { "type": "number" }
}
}
}
},
"material_stats": {
"type": "object",
"additionalProperties": false,
"required": ["material_count", "uses_textures"],
"properties": {
"material_count": { "type": "integer", "minimum": 0 },
"uses_textures": { "type": "boolean" }
}
}
}
}
}
}

### 10.2 Critic workcell report

{
"$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "fab.schema.critic_report.v1",
"type": "object",
"additionalProperties": false,
"required": ["schema_version", "run_id", "asset_id", "gate_config_id", "models", "views",
"scores", "failures"],
"properties": {
"schema_version": { "type": "string", "const": "1.0" },
"run_id": { "type": "string" },
"asset_id": { "type": "string" },
"gate_config_id": { "type": "string" },
"determinism": {
"type": "object",
"additionalProperties": false,
"required": ["cpu_only", "seeds", "framework_versions"],
"properties": {
"cpu_only": { "type": "boolean" },
"seeds": {
"type": "object",
"additionalProperties": false,
"required": ["global_seed"],
"properties": { "global_seed": { "type": "integer" } }
},
"framework_versions": {
"type": "object",
"additionalProperties": { "type": "string" }
}
}
},
"models": {
"type": "array",
"items": {
"type": "object",
"additionalProperties": false,
"required": ["name", "version", "weights_sha256"],
"properties": {
"name": { "type": "string" },
"version": { "type": "string" },
"weights_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
}
}
},
"views": {
"type": "array",
"items": {
"type": "object",
"additionalProperties": false,
"required": ["view_id", "mode", "image_path", "per_critic"],
"properties": {
"view_id": { "type": "string" },
"mode": { "type": "string", "enum": ["beauty", "clay"] },
"image_path": { "type": "string" },
"per_critic": {
"type": "object",
"additionalProperties": {
"type": "object",
"additionalProperties": false,
"required": ["score", "fail_codes"],
"properties": {
"score": { "type": "number", "minimum": 0, "maximum": 1 },
"fail_codes": { "type": "array", "items": { "type": "string" } },
"metrics": { "type": "object", "additionalProperties": true }
}
}
}
}
}
},
"scores": {
"type": "object",
"additionalProperties": false,
"required": ["category", "alignment", "realism", "geometry", "overall"],
"properties": {
"category": { "type": "number", "minimum": 0, "maximum": 1 },
"alignment": { "type": "number", "minimum": 0, "maximum": 1 },
"realism": { "type": "number", "minimum": 0, "maximum": 1 },
"geometry": { "type": "number", "minimum": 0, "maximum": 1 },
"overall": { "type": "number", "minimum": 0, "maximum": 1 }
}
},
"failures": {
"type": "object",
"additionalProperties": false,
"required": ["hard", "soft"],
"properties": {
"hard": { "type": "array", "items": { "type": "string" } },
"soft": { "type": "array", "items": { "type": "string" } }
}
}
}
}

### 10.3 Kernel gate verdict object

{
"$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "fab.schema.gate_verdict.v1",
"type": "object",
"additionalProperties": false,
"required": ["schema_version", "run_id", "asset_id", "gate_config_id", "verdict",
"scores", "failures", "next_actions"],
"properties": {
"schema_version": { "type": "string", "const": "1.0" },
"run_id": { "type": "string" },
"asset_id": { "type": "string" },
"gate_config_id": { "type": "string" },
"verdict": { "type": "string", "enum": ["pass", "fail", "escalate"] },
"scores": {
"type": "object",
"additionalProperties": false,
"required": ["overall", "by_critic"],
"properties": {
"overall": { "type": "number", "minimum": 0, "maximum": 1 },
"by_critic": {
"type": "object",
"additionalProperties": { "type": "number", "minimum": 0, "maximum": 1 }
}
}
},
"failures": {
"type": "object",
"additionalProperties": false,
"required": ["hard", "soft"],
"properties": {
"hard": { "type": "array", "items": { "type": "string" } },
"soft": { "type": "array", "items": { "type": "string" } }
}
},
"next_actions": {
"type": "array",
"items": {
"type": "object",
"additionalProperties": false,
"required": ["action", "priority", "instructions"],
"properties": {
"action": { "type": "string", "enum": ["repair", "rerender_vote_pack",
"fallback_to_template", "human_review"] },
"priority": { "type": "integer", "minimum": 1, "maximum": 5 },
"instructions": { "type": "string" },
"suggested_template_ref": { "type": "string" }
}
}
}
}
}

———

## 11) Repo Layout & Config

### 11.1 Proposed folder structure

- fab/lookdev/
  - scenes/ (e.g., car_lookdev_v001.blend)
  - rigs/ (e.g., car_camrig_v001.json)
  - hdris/ (pinned assets + hashes)
- fab/critics/
  - configs/ (critic stack configs)
  - models/ (weights stored offline with sha256 manifest)
  - schemas/ (JSON schemas above)
- fab/templates/
  - car/<template_id>/<semver>/...
- fab/gates/
  - car_realism_v001.yaml (thresholds + weights)
- fab/runs/<run_id>/... (artifact store, as specified)

### 11.2 Example gate config (YAML)

gate_config_id: car_realism_v001
category: car
lookdev_scene_id: car_lookdev_v001
camera_rig_id: car_camrig_v001
render:
engine: CYCLES
device: CPU
resolution: [768, 512]
samples: 128
seed: 1337
denoise: false
critics:
category:
min_views_passing: 10
per_view_car_conf_min: 0.60
require_clay_agreement: true
alignment:
clip_model: "openclip_vit_l14"
margin_min: 0.08
realism:
aesthetic_min: 0.55
niqe_max: 6.0
geometry:
bounds_m:
length: [3.0, 6.0]
width: [1.4, 2.5]
height: [1.0, 2.5]
triangle_count: [5000, 500000]
symmetry_min: 0.70
wheel_clusters_min: 3 # allow partial detection early; tighten in v2
decision:
weights:
category: 0.35
alignment: 0.20
realism: 0.20
geometry: 0.25
overall_pass_min: 0.75
subscore_floors:
category: 0.70
geometry: 0.60
iteration:
max_iters: 5
vote_pack_on_uncertainty: true
uncertainty_band: 0.03

Naming conventions:

- Runs: run*<UTCISO>*<shortsha> (or kernel UUID)
- Views: <mode>\_<view_id>.<ext>, turntable: <mode>\_turntable_f<frame>.png
- Reports: critics/report.json, verdict/gate_verdict.json, manifest.json

———

## 12) Phased Delivery Plan

### V0 (local-first, deterministic core)

Deliverables

- Canonical headless render harness (beauty + clay, fixed views)
- One critic: category correctness (multi-view) + basic geometry stats
- Artifact store + manifest + JSON reports + gate verdict

Acceptance criteria

- Same input asset + config produces identical artifact structure and stable verdict
  locally.
- Obvious blob assets reliably fail with clear failure codes.

### V1 (full critics + priors + iteration loop)

Deliverables

- Full critics stack (category + alignment + realism + geometry sanity)
- Template/scaffold support + version pinning
- Kernel-driven iterate-until-pass repair loop with retry caps

Acceptance criteria

- From a template baseline, agent can iteratively reach pass for a range of car prompts.
- Reports are actionable (repair playbook produces measurable improvements).

### V2 (robustness + scale)

Deliverables

- Speculate+vote pack (ensembles + alternate harness variants)
- Multiple asset categories (config-driven)
- CI hooks (containerized Blender + offline weights cache), regression dataset

Acceptance criteria

- Gate is stable in CI (pinned container) and catches regressions via golden assets.
- Reduced false pass rate on adversarial “texture-only car” attempts due to clay + geometry
  checks.

———

## 13) Risks & Mitigations

- Render nondeterminism: pin Blender build + CPU rendering + fixed seeds + containerize CI;
  store full config + hashes.
- Model false positives/negatives: ensemble critics; calibrate thresholds on a curated
  good/bad dataset; add vote pack near boundary.
- Domain mismatch (stylized vs realistic): separate gate configs per style; avoid one-size
  thresholds.
- Compute cost: tiered evaluation (cheap hard-fail checks first); small default resolution;
  only run vote pack on uncertainty.
- Metric gaming: multi-mode renders (beauty+clay+passes), geometry priors, subscore floors,
  periodic gate version refresh with regression sets.

———

## 14) Immediate Next Steps (executor-ready)

1. Define car_lookdev_v001.blend invariants + export a locked file into fab/lookdev/
   scenes/.
2. Write car_camrig_v001.json (views + turntable frames) and embed matching cameras in the
   lookdev scene.
3. Specify manifest.json format (sha256 + tool versions) and require it for every run
   directory.
4. Implement headless render harness CLI contract (inputs: asset.glb + config; outputs:
   render/ tree + logs).
5. Implement V0 category critic (multi-view car detection + clay agreement) and output
   critic_report.json.
6. Implement V0 geometry stats extractor (bounds, tri count, component count) and hard-fail
   rules.
7. Implement kernel gate aggregation + gate_verdict.json emission (versioned thresholds).
8. Implement failure-code → repair-playbook mapping and feed it into fab.asset.repair
   tasks.
9. Add template packaging + version pinning rules (sha256 + semver) and a single baseline
   car template.
10. Build a small calibration set (e.g., 50 good cars, 50 blobs) and tune V0/V1 thresholds
    with recorded reports.
