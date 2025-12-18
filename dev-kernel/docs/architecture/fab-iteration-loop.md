# Fab Iteration Loop

## Overview

The iteration loop implements a **generate → render → score → repair** cycle that continues until the asset passes the gate, reaches the retry cap, or triggers human escalation.

## State Machine

```
              ┌─────────────────────────────────────────────┐
              │                                             │
              ▼                                             │
┌──────┐   ┌──────────┐   ┌────────┐   ┌────────┐   ┌───────────┐
│ INIT │──►│ GENERATE │──►│ EXPORT │──►│ RENDER │──►│  CRITIC   │
└──────┘   └──────────┘   └────────┘   └────────┘   └───────────┘
                                                          │
                                                          ▼
                                                    ┌───────────┐
                                                    │  VERDICT  │
                                                    └───────────┘
                                                          │
                                    ┌─────────────────────┼─────────────────────┐
                                    │                     │                     │
                                    ▼                     ▼                     ▼
                              ┌──────────┐          ┌──────────┐          ┌──────────┐
                              │   DONE   │          │  REPAIR  │          │ ESCALATE │
                              │  (pass)  │          │  (fail)  │          │ (human)  │
                              └──────────┘          └──────────┘          └──────────┘
                                                          │
                                                          │
                                                          └─────► GENERATE (loop)
```

### State Definitions

| State      | Description                              | Transitions                |
| ---------- | ---------------------------------------- | -------------------------- |
| `INIT`     | Issue enters Fab pipeline                | → GENERATE                 |
| `GENERATE` | Blender workcell creates/modifies asset  | → EXPORT                   |
| `EXPORT`   | Asset exported to canonical formats      | → RENDER                   |
| `RENDER`   | Render harness produces canonical images | → CRITIC                   |
| `CRITIC`   | Critics evaluate renders + mesh          | → VERDICT                  |
| `VERDICT`  | Gate decision computed                   | → DONE / REPAIR / ESCALATE |
| `DONE`     | Asset passed, issue closed               | Terminal                   |
| `REPAIR`   | Repair issue created with feedback       | → GENERATE                 |
| `ESCALATE` | Human review required                    | Terminal                   |

## Verdict Decision Logic

```python
def process_verdict(
    verdict: GateVerdict,
    issue: Issue,
    config: IterationConfig
) -> IterationAction:
    """Determine next action based on verdict"""

    if verdict.verdict == "pass":
        return IterationAction(
            type="DONE",
            close_issue=True,
            merge_asset=True
        )

    if verdict.verdict == "escalate":
        return IterationAction(
            type="ESCALATE",
            escalate_reason=verdict.escalate_reason,
            notify_human=True
        )

    # verdict == "fail"
    iteration_index = issue.dk_iteration_index or 0

    # Check retry limits
    if iteration_index >= config.max_iterations:
        return IterationAction(
            type="ESCALATE",
            escalate_reason="max_iterations_exceeded",
            notify_human=True
        )

    # Check for repeated hard fails
    if _has_repeated_hard_fail(issue, verdict):
        return IterationAction(
            type="ESCALATE",
            escalate_reason="repeated_hard_fail",
            notify_human=True
        )

    # Create repair issue
    return IterationAction(
        type="REPAIR",
        create_repair_issue=True,
        repair_context=_build_repair_context(verdict, issue)
    )
```

## Repair Issue Creation

### Repair Context Structure

```python
@dataclass
class RepairContext:
    original_issue_id: str
    iteration_index: int
    gate_config_id: str

    # Failure information
    hard_fails: List[str]
    soft_fails: List[str]
    fail_scores: Dict[str, float]

    # Repair guidance
    prioritized_instructions: List[RepairInstruction]

    # Artifacts for reference
    render_paths: Dict[str, str]  # View thumbnails
    report_path: str

    # Template fallback suggestion
    suggested_template: Optional[str]
```

### Repair Issue Template

```python
def create_repair_issue(
    original: Issue,
    context: RepairContext,
    verdict: GateVerdict
) -> Issue:
    """Create a repair issue with structured feedback"""

    description = f"""
## Repair Task for: {original.title}

### Iteration: {context.iteration_index + 1} of {config.max_iterations}

### Gate Verdict: FAIL

### Failures to Address

**Hard Fails (must fix):**
{_format_fail_list(context.hard_fails)}

**Soft Fails (improve):**
{_format_fail_list(context.soft_fails)}

### Scores
| Critic | Score | Floor | Status |
|--------|-------|-------|--------|
{_format_score_table(context.fail_scores)}

### Repair Instructions

{_format_instructions(context.prioritized_instructions)}

### Reference Renders
See `{context.render_paths['beauty_front_3q']}` and other views in the render/ directory.

### Full Report
See `{context.report_path}` for detailed critic analysis.

{_maybe_template_suggestion(context)}
"""

    return Issue(
        title=f"[REPAIR] {original.title} (iter {context.iteration_index + 1})",
        description=description,
        priority=_escalate_priority(original.dk_priority),
        tags=[
            f"@attempt:{context.iteration_index + 1}",
            "@auto-generated",
            f"@gate:fab-realism",
            *[f"@fail:{code}" for code in context.hard_fails[:3]]
        ],
        dk_parent_run_id=original.dk_current_run_id,
        dk_iteration_index=context.iteration_index + 1,
        dk_gate_config_id=context.gate_config_id,
        dk_last_fail_codes=context.hard_fails + context.soft_fails
    )
```

### Dependency Edge Creation

```python
def link_repair_to_original(repair_issue: Issue, original_issue: Issue):
    """Create dependency edge from repair to original"""
    bd_dep_add(
        from_id=repair_issue.id,
        to_id=original_issue.id,
        type="fix-for"
    )

    # Block original until repair completes
    bd_update(
        issue_id=original_issue.id,
        status="blocked"
    )
```

## Failure Code → Repair Instruction Mapping

### Priority Levels

| Priority | Meaning                   | Examples                        |
| -------- | ------------------------- | ------------------------------- |
| 1        | Critical - must fix first | No car detected, import failed  |
| 2        | High - structural issues  | Wheel count, scale problems     |
| 3        | Medium - quality issues   | Alignment, realism scores       |
| 4        | Low - polish              | Minor symmetry, texture quality |

### Repair Playbook Entries

```yaml
repair_playbook:
  # Hard fails (Priority 1)
  CAT_NO_CAR_DETECTED:
    priority: 1
    action: repair
    instructions: |
      The asset is not recognized as a car in multiple views.

      Steps to fix:
      1. Verify the model has a recognizable car silhouette
      2. Ensure 4 wheels are visible and positioned correctly
      3. Check that scale matches real car (3-6m length)
      4. Render a clay preview to verify geometry reads as car

      Common causes:
      - Topology is too abstract/stylized
      - Missing wheels or body panels
      - Wrong scale (microscopic or gigantic)

  GEO_SCALE_IMPLAUSIBLE:
    priority: 1
    action: repair
    instructions: |
      Asset dimensions are outside plausible car range.

      Expected ranges:
      - Length: 3.0-6.0 meters
      - Width: 1.4-2.5 meters
      - Height: 1.0-2.5 meters

      Steps to fix:
      1. Check current dimensions in Blender (N panel)
      2. Apply scale transforms (Ctrl+A → Scale)
      3. Resize to match realistic car proportions
      4. Verify origin is at asset center

  # Geometry issues (Priority 2)
  GEO_WHEEL_COUNT_LOW:
    priority: 2
    action: repair
    instructions: |
      Fewer than expected wheel-like regions detected.

      Steps to fix:
      1. Model or instantiate 4 distinct wheel objects
      2. Position wheels at corners of vehicle chassis
      3. Ensure wheels make contact near z=0 (ground)
      4. Wheels should be roughly cylindrical
      5. Typical wheel radius: 0.3-0.4 meters

      Tip: You can duplicate one wheel and mirror for efficiency.

  GEO_ASYMMETRIC:
    priority: 2
    action: repair
    instructions: |
      Low bilateral symmetry detected.

      Cars are typically symmetric across the length axis.

      Steps to fix:
      1. Use Mirror modifier for symmetric parts
      2. Delete one half and mirror if needed
      3. Check for accidental asymmetric modifications
      4. Apply any rotation transforms before checking

  # Quality issues (Priority 3)
  ALIGN_MARGIN_LOW:
    priority: 3
    action: repair
    instructions: |
      Asset doesn't match the prompt description well.

      Review the original prompt and check:
      1. Color matches description (e.g., "red sedan")
      2. Style/era matches (e.g., "1990s", "modern", "retro")
      3. Body type matches (sedan, SUV, sports car)
      4. Distinctive features mentioned are present

      Adjust materials and shape to better align.

  REAL_LOW_AESTHETIC:
    priority: 3
    action: repair
    instructions: |
      Visual quality/realism score is below threshold.

      Improvements to consider:
      1. Add material imperfections (scratches, wear)
      2. Use realistic roughness values (not all shiny)
      3. Add proper clearcoat for car paint
      4. Include environment reflections
      5. Check normal maps are applied correctly
      6. Add subtle texture variation

  MAT_MISSING_TEXTURES:
    priority: 2
    action: repair
    instructions: |
      Texture files are not properly linked/packed.

      Steps to fix:
      1. In Blender: File → External Data → Pack Resources
      2. Or: Re-link textures from packed folder
      3. When exporting glTF: Enable "Include: Images"
      4. Avoid absolute file paths in materials

      Check for magenta/pink areas indicating missing textures.
```

## Iteration Tracking

### Issue Field Updates

Each iteration updates:

```python
def update_issue_iteration(issue: Issue, verdict: GateVerdict, run_id: str):
    """Update issue with iteration state"""
    bd_update(
        issue_id=issue.id,
        dk_iteration_index=(issue.dk_iteration_index or 0) + 1,
        dk_last_gate_report_path=f"fab/runs/{run_id}/verdict/gate_verdict.json",
        dk_last_fail_codes=verdict.failures.hard + verdict.failures.soft,
        dk_attempts=(issue.dk_attempts or 0) + 1
    )
```

### Run Lineage

```python
def record_run_lineage(current_run_id: str, parent_run_id: Optional[str]):
    """Record iteration chain for audit"""
    manifest = load_manifest(current_run_id)
    manifest["iteration"] = {
        "parent_run_id": parent_run_id,
        "iteration_index": compute_depth(parent_run_id),
        "created_at": datetime.utcnow().isoformat()
    }
    save_manifest(current_run_id, manifest)
```

## Escalation Triggers

### Conditions

| Trigger               | Condition                            | Reason          |
| --------------------- | ------------------------------------ | --------------- |
| Max iterations        | `iteration_index >= max_iterations`  | Resource limit  |
| Repeated hard fail    | Same hard fail ≥2 consecutive times  | Not improving   |
| Import crash          | Blender crash on import              | Corrupted asset |
| Critic inconsistency  | Vote pack disagrees after tiebreaker | Ambiguous case  |
| Suspected adversarial | Semantic pass + geometry catastrophe | Gaming attempt  |

### Escalation Action

```python
def escalate_issue(issue: Issue, reason: str, verdict: GateVerdict):
    """Escalate issue to human review"""
    bd_update(
        issue_id=issue.id,
        status="escalated",
        tags=issue.tags + ["@human-escalated", f"@escalate:{reason}"]
    )

    log_event({
        "type": "fab_escalation",
        "issue_id": issue.id,
        "reason": reason,
        "iteration_index": issue.dk_iteration_index,
        "last_fail_codes": verdict.failures.hard + verdict.failures.soft,
        "timestamp": datetime.utcnow().isoformat()
    })

    if config.notification_webhook:
        send_escalation_notification(issue, reason, verdict)
```

## Template Fallback

When iterations aren't progressing, suggest template-based approach:

```python
def suggest_template_fallback(
    issue: Issue,
    verdict: GateVerdict,
    iteration_index: int
) -> Optional[str]:
    """Suggest falling back to template if struggling"""

    # Only suggest after 2+ failed iterations
    if iteration_index < 2:
        return None

    # Check if geometry issues dominate
    geo_fails = [c for c in verdict.failures.hard + verdict.failures.soft
                 if c.startswith("GEO_")]

    if len(geo_fails) >= 2:
        category = issue.tags.get("asset:", "car")
        return f"{category}_template_v001"

    return None
```

## Configuration

```yaml
iteration:
  max_iterations: 5

  escalation:
    on_repeated_hard_fail: true
    repeated_threshold: 2
    on_import_crash: true
    on_critic_inconsistency: true
    notify_webhook: "https://..."

  template_fallback:
    enabled: true
    suggest_after_iterations: 2
    templates:
      car: "car_sedan_template_v001"
      suv: "car_suv_template_v001"

  priority_escalation:
    # Bump priority on each iteration
    P3_to: P2
    P2_to: P1
    P1_to: P0
```

## Flow Diagram

```
Issue enters Fab pipeline
          │
          ▼
    ┌───────────┐
    │  GENERATE │◄──────────────────────────────────────┐
    │  (agent)  │                                       │
    └───────────┘                                       │
          │                                             │
          ▼                                             │
    ┌───────────┐                                       │
    │  EXPORT   │                                       │
    │ (.blend   │                                       │
    │  + .glb)  │                                       │
    └───────────┘                                       │
          │                                             │
          ▼                                             │
    ┌───────────┐                                       │
    │  RENDER   │                                       │
    │ (harness) │                                       │
    └───────────┘                                       │
          │                                             │
          ▼                                             │
    ┌───────────┐                                       │
    │  CRITICS  │                                       │
    └───────────┘                                       │
          │                                             │
          ▼                                             │
    ┌───────────┐                                       │
    │  VERDICT  │                                       │
    └───────────┘                                       │
          │                                             │
          ├── pass ──► DONE (merge + close)             │
          │                                             │
          ├── escalate ──► ESCALATE (human review)      │
          │                                             │
          └── fail ──┐                                  │
                     │                                  │
                     ▼                                  │
              ┌─────────────┐                          │
              │ iterations  │                          │
              │ < max?      │                          │
              └─────────────┘                          │
                     │                                  │
                Yes  │   No                             │
                ─────┴─────                             │
                │         │                             │
                ▼         ▼                             │
          ┌──────────┐  ┌──────────┐                   │
          │  CREATE  │  │ ESCALATE │                   │
          │  REPAIR  │  └──────────┘                   │
          │  ISSUE   │                                  │
          └──────────┘                                  │
                │                                       │
                └───────────────────────────────────────┘
```

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Gate Decision Logic](./fab-gate-logic.md) - How verdicts are computed
- [Failure Handling](./failure-handling.md) - General kernel failure patterns
