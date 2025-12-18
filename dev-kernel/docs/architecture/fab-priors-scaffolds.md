# Fab Priors & Scaffolds

## Overview

Priors and scaffolds constrain the agent's search space, dramatically reducing blob risk and accelerating convergence to passing assets.

## Strategy Comparison

| Approach     | Description                        | Blob Risk | Agent Freedom |
| ------------ | ---------------------------------- | --------- | ------------- |
| **Freeform** | Agent creates from scratch         | High      | Maximum       |
| **Template** | Start from vetted base asset       | Low       | Moderate      |
| **Scaffold** | Procedural rig constrains topology | Very Low  | Constrained   |

## Template-First Approach

### Concept

Start from vetted base assets that already pass the gate. Agents modify parameters/materials rather than inventing topology.

### Template Structure

```
fab/templates/car/<template_id>/<version>/
├── asset.blend          # Source Blender file
├── asset.glb            # Pre-exported canonical format
├── manifest.json        # Metadata + golden test results
├── preview/
│   ├── beauty_front_3q.png
│   └── clay_front_3q.png
└── README.md            # Usage documentation
```

### Template Manifest

```json
{
  "template_id": "car_sedan_v001",
  "version": "1.0.0",
  "category": "car",
  "created_at": "2024-01-15T10:00:00Z",

  "files": {
    "blend_sha256": "abc123...",
    "glb_sha256": "def456..."
  },

  "structure": {
    "named_parts": ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"],
    "material_slots": ["Body_Paint", "Glass", "Chrome", "Rubber", "Interior"],
    "origin": "center_ground",
    "up_axis": "Z",
    "forward_axis": "-Y"
  },

  "geometry_stats": {
    "triangle_count": 45000,
    "vertex_count": 24000,
    "bounds_m": { "x": 1.8, "y": 4.5, "z": 1.4 }
  },

  "golden_test": {
    "gate_config_id": "car_realism_v001",
    "passed_at": "2024-01-15T12:00:00Z",
    "scores": {
      "category": 0.95,
      "alignment": 0.88,
      "realism": 0.82,
      "geometry": 0.91,
      "overall": 0.89
    }
  },

  "allowed_modifications": [
    "material_parameters",
    "texture_replacement",
    "color_changes",
    "minor_mesh_edits",
    "accessory_additions"
  ],

  "forbidden_modifications": [
    "wheel_deletion",
    "major_topology_changes",
    "scale_beyond_bounds"
  ]
}
```

### Template Usage

```python
def create_asset_from_template(template_ref: str, modifications: Dict) -> Path:
    """Create asset starting from template"""
    template = load_template(template_ref)

    # Copy template to workcell
    work_path = copy_template_to_workcell(template)

    # Apply modifications
    for mod_type, mod_params in modifications.items():
        if mod_type in template.forbidden_modifications:
            raise TemplateViolation(f"Modification {mod_type} not allowed")
        apply_modification(work_path, mod_type, mod_params)

    return work_path
```

## Procedural Scaffolds

### Concept

A versioned parametric rig (Geometry Nodes) that outputs a car-like scaffold: wheel placement, body volume envelope, basic proportions.

### Scaffold Parameters

| Parameter       | Type  | Range      | Purpose                 |
| --------------- | ----- | ---------- | ----------------------- |
| `wheelbase`     | float | 2.4–3.2m   | Distance between axles  |
| `track_width`   | float | 1.4–1.8m   | Distance between wheels |
| `body_length`   | float | 3.5–5.5m   | Overall length          |
| `body_height`   | float | 1.2–1.8m   | Overall height          |
| `roof_line`     | curve | —          | Roof profile shape      |
| `fender_radius` | float | 0.1–0.3m   | Wheel arch radius       |
| `wheel_radius`  | float | 0.28–0.42m | Wheel size              |

### Scaffold Structure

```
fab/scaffolds/car/<scaffold_id>/<version>/
├── scaffold.blend       # Geometry Nodes setup
├── parameters.json      # Default parameter values
├── constraints.json     # Valid parameter ranges
├── preview/
│   └── scaffold_preview.png
└── README.md
```

### Scaffold Constraints

```json
{
  "scaffold_id": "car_scaffold_v001",
  "version": "1.0.0",

  "parameters": {
    "wheelbase": {
      "type": "float",
      "default": 2.7,
      "min": 2.4,
      "max": 3.2,
      "unit": "meters"
    },
    "track_width": {
      "type": "float",
      "default": 1.6,
      "min": 1.4,
      "max": 1.8,
      "unit": "meters"
    }
  },

  "derived_constraints": [
    {
      "rule": "body_length >= wheelbase + 0.8",
      "reason": "Body must extend past wheels"
    },
    {
      "rule": "wheel_radius <= body_height * 0.35",
      "reason": "Wheels must fit under body"
    }
  ],

  "outputs": {
    "guaranteed": [
      "4 wheel positions at ground level",
      "body envelope mesh",
      "symmetric across X axis"
    ]
  }
}
```

### Scaffold Enforcement

```python
def validate_scaffold_adherence(mesh: trimesh.Trimesh, scaffold_ref: str) -> List[str]:
    """Validate mesh adheres to scaffold constraints"""
    scaffold = load_scaffold(scaffold_ref)
    violations = []

    # Check wheel positions match scaffold
    expected_wheels = scaffold.compute_wheel_positions()
    detected_wheels = detect_wheel_regions(mesh)

    for expected in expected_wheels:
        if not any(is_near(expected, detected) for detected in detected_wheels):
            violations.append("SCAFFOLD_WHEEL_POSITION_MISMATCH")

    # Check bounds within scaffold envelope
    if not scaffold.envelope_contains(mesh.bounding_box):
        violations.append("SCAFFOLD_BOUNDS_EXCEEDED")

    return violations
```

## Agent Interaction Model

### Preferred Path: Template/Scaffold

```
Issue: "Create red sports car"
  │
  ├─► Agent selects template: car_sports_v001
  │
  ├─► Agent modifies:
  │   - Material: Body_Paint → red metallic
  │   - Texture: Add racing stripes
  │   - Minor mesh: Spoiler addition
  │
  ├─► Export + Gate evaluation
  │
  └─► High probability of passing
```

### Freeform Path (Stricter Checks)

```
Issue: "Create unique concept car"
  │
  ├─► Agent creates from scratch
  │
  ├─► Gate applies stricter checks:
  │   - require_clay_agreement: true
  │   - symmetry_min: 0.75 (higher)
  │   - wheel_clusters_min: 4 (stricter)
  │
  ├─► Higher iteration likelihood
  │
  └─► More escalation risk
```

### Gate Config Per Path

```yaml
# Template-based
template_mode:
  critics:
    geometry:
      wheel_clusters_min: 3 # Relaxed
      symmetry_min: 0.65
  iteration:
    max_iterations: 3

# Freeform
freeform_mode:
  critics:
    geometry:
      wheel_clusters_min: 4 # Stricter
      symmetry_min: 0.75
    category:
      require_clay_agreement: true
  iteration:
    max_iterations: 5
```

## Versioning & Drift Prevention

### Immutability Rules

1. Templates/scaffolds are immutable once published
2. Changes require new semantic version
3. Old versions remain available for reproducibility

### Version Schema

```
<template_id>_v<major>.<minor>.<patch>

Major: Breaking changes (structure change)
Minor: Additive changes (new material slots)
Patch: Fixes (normal corrections)
```

### Golden Render Tests

Each template includes golden test results:

```python
def validate_template_integrity(template_ref: str) -> bool:
    """Verify template still passes its golden test"""
    template = load_template(template_ref)

    # Render with reference config
    renders = render_harness.run(
        asset_path=template.glb_path,
        config=template.golden_test.gate_config_id
    )

    # Run critics
    results = critics.evaluate(renders)

    # Compare to golden results
    for critic, score in results.scores.items():
        golden_score = template.golden_test.scores[critic]
        if abs(score - golden_score) > 0.05:  # 5% tolerance
            log_warning(f"Template {template_ref} drift: {critic} changed")
            return False

    return True
```

### Registry Manifest

```json
{
  "registry_version": "1.0",
  "updated_at": "2024-01-15T10:00:00Z",

  "templates": {
    "car_sedan_v001": {
      "status": "active",
      "versions": ["1.0.0", "1.0.1", "1.1.0"],
      "latest": "1.1.0",
      "deprecated": []
    }
  },

  "scaffolds": {
    "car_scaffold_v001": {
      "status": "active",
      "versions": ["1.0.0"],
      "latest": "1.0.0"
    }
  }
}
```

## Configuration

```yaml
priors:
  templates:
    enabled: true
    registry_path: "fab/templates/registry.json"
    auto_suggest_on_failure: true
    suggest_after_iterations: 2

  scaffolds:
    enabled: true
    registry_path: "fab/scaffolds/registry.json"
    enforce_adherence: true

  golden_tests:
    enabled: true
    run_on_startup: false
    run_on_ci: true
    tolerance: 0.05
```

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Gate Decision Logic](./fab-gate-logic.md) - Template fallback suggestions
- [Iteration Loop](./fab-iteration-loop.md) - How templates help repair
