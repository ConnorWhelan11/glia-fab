# Fab Asset Templates

This directory contains vetted base assets that serve as starting points for agent-driven modifications.

## Purpose

Templates reduce blob risk and accelerate convergence by providing:
- Correct scale and orientation
- Named parts (Body, Wheel_FL, Wheel_FR, etc.)
- Baseline PBR materials
- Known-good geometry that passes the gate

## Structure

```
fab/templates/
├── README.md
├── registry.json           # Template registry with metadata + hashes
└── {category}/
    └── {template_id}/
        └── {version}/
            ├── manifest.json    # Template metadata + constraints
            ├── asset.blend      # Source Blender file
            ├── asset.glb        # Exported GLB for validation
            └── golden/          # Golden test renders + scores
                ├── beauty/
                ├── clay/
                └── gate_verdict.json
```

## Template Versioning

- Templates are immutable once published
- Changes require new semantic version (vX.Y.Z)
- Gate config references exact template version + SHA256

## Usage in Gate

When an issue specifies a template:
1. Agent starts from template as base
2. Gate checks template adherence (scale, named parts)
3. Stricter geometry constraints apply to modifications

## Template Manifest Schema

```json
{
  "template_id": "sedan_v001",
  "category": "car",
  "version": "1.0.0",
  "description": "Standard 4-door sedan template",
  "sha256": "abc123...",
  "constraints": {
    "required_parts": ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"],
    "scale_tolerance": 0.1,
    "max_modification_ratio": 0.5
  },
  "golden_scores": {
    "category": 0.95,
    "geometry": 0.92,
    "overall": 0.90
  }
}
```

