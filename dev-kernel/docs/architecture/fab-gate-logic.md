# Fab Gate Decision Logic

## Overview

The Gate Decision module aggregates critic scores, applies category-specific thresholds, and emits a deterministic verdict (pass/fail/escalate) with structured failure information for repair loops.

## Verdict Types

| Verdict    | Meaning                           | Next Action           |
| ---------- | --------------------------------- | --------------------- |
| `pass`     | Asset meets all criteria          | Merge, close issue    |
| `fail`     | Criteria not met, retryable       | Create repair issue   |
| `escalate` | Unrecoverable or repeated failure | Human review required |

## Hard Fails vs Soft Fails

### Hard Fails (Immediate Rejection)

Hard fails indicate fundamental problems that cannot be fixed by iterative improvement:

| Condition                               | Code                    |
| --------------------------------------- | ----------------------- |
| Export/import failure                   | `IMPORT_*`              |
| Missing files                           | `FILE_NOT_FOUND`        |
| Invalid mesh (can't parse)              | `MESH_INVALID`          |
| No car detection in ≥50% required views | `CAT_NO_CAR_DETECTED`   |
| Scale wildly implausible (>10x off)     | `GEO_SCALE_IMPLAUSIBLE` |
| Triangle count < 1000                   | `GEO_TRI_COUNT_TRIVIAL` |
| Missing textures with broken refs       | `MAT_MISSING_TEXTURES`  |
| Blender crash during render             | `BLENDER_CRASH`         |

### Soft Fails (Score-Based)

Soft fails indicate quality issues that may improve with iteration:

| Condition                        | Code                   |
| -------------------------------- | ---------------------- |
| Prompt alignment below threshold | `ALIGN_*`              |
| Realism/quality below threshold  | `REAL_*`               |
| Geometry priors marginal         | `GEO_*` (non-critical) |
| Low symmetry                     | `GEO_ASYMMETRIC`       |
| Wheel count ambiguous            | `GEO_WHEEL_COUNT_LOW`  |

## Scoring Algorithm

### Weighted Aggregate Score

```python
def compute_overall_score(critic_scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Compute weighted aggregate score.

    S = Σ(w_i × S_i) where Σw_i = 1.0
    """
    total = 0.0
    for critic, score in critic_scores.items():
        weight = weights.get(critic, 0.0)
        total += weight * score
    return total
```

### Default Weights

| Critic    | Weight | Rationale                    |
| --------- | ------ | ---------------------------- |
| Category  | 0.35   | Most important: is it a car? |
| Geometry  | 0.25   | Physical validity            |
| Alignment | 0.20   | Matches prompt intent        |
| Realism   | 0.20   | Visual quality               |

### Subscore Floors

Even with high overall score, individual critics must meet minimums:

```python
def check_subscore_floors(
    critic_scores: Dict[str, float],
    floors: Dict[str, float]
) -> List[str]:
    """Check if any critic is below its floor"""
    violations = []
    for critic, floor in floors.items():
        if critic_scores.get(critic, 0) < floor:
            violations.append(f"{critic.upper()}_BELOW_FLOOR")
    return violations
```

| Critic    | Floor | Purpose                                    |
| --------- | ----- | ------------------------------------------ |
| Category  | 0.70  | Can't pass without being recognized as car |
| Geometry  | 0.60  | Can't pass with broken geometry            |
| Alignment | 0.50  | Some prompt match required                 |
| Realism   | 0.40  | Minimum visual quality                     |

## Gate Decision Flow

```python
class GateDecision:
    def __init__(self, config: GateConfig):
        self.config = config

    def evaluate(
        self,
        critic_results: Dict[str, CriticResult],
        iteration_index: int
    ) -> GateVerdict:
        # Collect all failure codes
        all_hard_fails = []
        all_soft_fails = []

        for critic, result in critic_results.items():
            for code in result.fail_codes:
                if self._is_hard_fail(code):
                    all_hard_fails.append(code)
                else:
                    all_soft_fails.append(code)

        # Check for hard fails (immediate rejection)
        if all_hard_fails:
            return self._create_fail_verdict(
                critic_results,
                hard_fails=all_hard_fails,
                soft_fails=all_soft_fails,
                reason="hard_fail"
            )

        # Compute scores
        scores = {name: r.score for name, r in critic_results.items()}
        overall = compute_overall_score(scores, self.config.weights)

        # Check subscore floors
        floor_violations = check_subscore_floors(scores, self.config.floors)
        if floor_violations:
            all_soft_fails.extend(floor_violations)

        # Check overall threshold
        if overall < self.config.overall_pass_min:
            all_soft_fails.append("OVERALL_SCORE_LOW")

        # Final decision
        if not all_soft_fails and not floor_violations:
            return self._create_pass_verdict(critic_results, scores, overall)

        # Check if we should escalate
        if self._should_escalate(iteration_index, all_hard_fails, all_soft_fails):
            return self._create_escalate_verdict(
                critic_results, scores, overall,
                hard_fails=all_hard_fails,
                soft_fails=all_soft_fails
            )

        # Fail with repair instructions
        return self._create_fail_verdict(
            critic_results, scores, overall,
            hard_fails=all_hard_fails,
            soft_fails=all_soft_fails,
            reason="soft_fail"
        )

    def _should_escalate(
        self,
        iteration_index: int,
        hard_fails: List[str],
        soft_fails: List[str]
    ) -> bool:
        """Determine if we should escalate to human"""
        # Max iterations exceeded
        if iteration_index >= self.config.max_iterations:
            return True

        # Repeated hard fail
        if len(hard_fails) > 0 and iteration_index >= 2:
            return True

        # Suspected adversarial (semantic pass but geometry catastrophic)
        if "CAT_NO_CAR_DETECTED" not in hard_fails and "GEO_TRI_COUNT_TRIVIAL" in hard_fails:
            return True

        return False
```

## Confidence Bands & Speculate+Vote

When the overall score is near the threshold, additional verification can be triggered:

```python
def should_trigger_vote_pack(
    overall_score: float,
    threshold: float,
    uncertainty_band: float = 0.03
) -> bool:
    """Trigger vote pack when score is within uncertainty band"""
    return abs(overall_score - threshold) <= uncertainty_band
```

### Vote Pack Contents

| Additional Check        | Purpose                       |
| ----------------------- | ----------------------------- |
| +12 turntable frames    | More view angles              |
| Alternate HDRI          | Different lighting conditions |
| Second detector model   | Ensemble agreement            |
| Cross-critic validation | Check for critic disagreement |

### Vote Aggregation

```python
def aggregate_vote_pack(results: List[GateVerdict]) -> GateVerdict:
    """Aggregate multiple gate evaluations"""
    pass_count = sum(1 for r in results if r.verdict == "pass")
    fail_count = sum(1 for r in results if r.verdict == "fail")

    # Majority rules
    if pass_count > len(results) / 2:
        return create_pass_from_majority(results)
    elif fail_count > len(results) / 2:
        return create_fail_from_majority(results)
    else:
        return create_escalate("no_clear_majority")
```

## Preventing Goodharting

### Multi-Modal Defense

| Defense               | Implementation                              |
| --------------------- | ------------------------------------------- |
| Multi-render modes    | Beauty + clay + passes                      |
| Geometry-first checks | Mesh analysis independent of textures       |
| Clay view semantics   | Category detection on material-free renders |
| Subscore floors       | Can't trade off one dimension for another   |

### Opacity to Agents

Agents receive:

- ✅ Failure codes + guidance text
- ✅ Key metrics (what's below threshold)
- ❌ Full scoring formula
- ❌ Exact weight values
- ❌ Internal thresholds

### Gate Versioning

```yaml
gate_config_id: "car_realism_v001"
version_history:
  - v001: "2024-01-15 - Initial release"
  - v002: "2024-02-01 - Tightened wheel detection"
regression_set_sha256: "abc123..."
last_calibration: "2024-01-10"
```

Regular gate refreshes with regression testing prevent long-term overfitting.

## Next Actions Generation

### Repair Instructions

```python
REPAIR_PLAYBOOK = {
    "CAT_NO_CAR_DETECTED": {
        "priority": 1,
        "action": "repair",
        "instructions": """
Add recognizable car silhouette:
- Ensure 4 wheels are visible and correctly positioned
- Verify scale matches real car dimensions (3-6m length)
- Re-render clay preview to verify geometry reads as car
"""
    },
    "GEO_WHEEL_COUNT_LOW": {
        "priority": 2,
        "action": "repair",
        "instructions": """
Model or instantiate 4 wheel components:
- Place wheels near corners of vehicle
- Ensure ground contact at z=0
- Wheels should be roughly cylindrical, ~0.3-0.4m radius
"""
    },
    "MAT_MISSING_TEXTURES": {
        "priority": 2,
        "action": "repair",
        "instructions": """
Fix texture references:
- Pack textures into .blend file
- Or embed textures in glTF export
- Avoid external file paths
- Ensure Principled BSDF materials
"""
    },
    "REAL_NOISY_RENDER": {
        "priority": 3,
        "action": "repair",
        "instructions": """
Improve material quality:
- Increase material roughness realism
- Add surface detail/imperfections
- Avoid emissive hacks for lighting
- Check for proper PBR setup
"""
    },
    "ALIGN_MARGIN_LOW": {
        "priority": 3,
        "action": "repair",
        "instructions": """
Better match the prompt:
- Review prompt requirements for color, style, era
- Adjust materials to match described appearance
- Consider adding distinctive features mentioned
"""
    }
}

def generate_next_actions(
    hard_fails: List[str],
    soft_fails: List[str],
    iteration_index: int
) -> List[Dict]:
    """Generate prioritized repair instructions"""
    actions = []

    for code in hard_fails + soft_fails:
        if code in REPAIR_PLAYBOOK:
            playbook_entry = REPAIR_PLAYBOOK[code]
            actions.append({
                "action": playbook_entry["action"],
                "priority": playbook_entry["priority"],
                "instructions": playbook_entry["instructions"],
                "fail_code": code
            })

    # Sort by priority
    actions.sort(key=lambda x: x["priority"])

    # Add escalation if needed
    if iteration_index >= 3:
        actions.append({
            "action": "fallback_to_template",
            "priority": 0,
            "instructions": "Consider starting from a known-good template",
            "suggested_template_ref": "car_template_sedan_v001"
        })

    return actions
```

## Gate Configuration Schema

```yaml
gate_config_id: "car_realism_v001"
category: "car"
lookdev_scene_id: "car_lookdev_v001"
camera_rig_id: "car_camrig_v001"

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
    wheel_clusters_min: 3

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
```

## Flow Diagram

```
Critic Results Collected
          │
          ▼
    ┌───────────┐
    │  Check    │
    │ Hard Fails│
    └───────────┘
          │
     Has Hard ──Yes──► FAIL (immediate)
     Fails?            │
          │            ▼
          No     Create repair issue
          │      with hard fail codes
          ▼
    ┌───────────┐
    │  Compute  │
    │  Scores   │
    └───────────┘
          │
          ▼
    ┌───────────┐
    │  Check    │
    │  Floors   │
    └───────────┘
          │
     Floor ────Yes──► Add to soft fails
     Violations?
          │
          ▼
    ┌───────────┐
    │  Check    │
    │ Overall   │
    └───────────┘
          │
     Below ────Yes──► Add to soft fails
     Threshold?
          │
          ▼
    ┌───────────┐
    │   Any     │
    │Soft Fails?│
    └───────────┘
          │
     Yes  │   No
     ─────┴─────
     │         │
     ▼         ▼
┌─────────┐  ┌──────┐
│ Check   │  │ PASS │
│Escalate?│  └──────┘
└─────────┘
     │
Yes  │   No
─────┴─────
│         │
▼         ▼
┌────────┐  ┌──────────┐
│ESCALATE│  │   FAIL   │
│(human) │  │ (repair) │
└────────┘  └──────────┘
```

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Critics Stack](./fab-critics.md) - How scores are computed
- [Iteration Loop](./fab-iteration-loop.md) - How repairs are executed
- [Fab Schemas](./fab-schemas.md) - Gate verdict JSON schema
