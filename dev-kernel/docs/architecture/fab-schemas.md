# Fab JSON Schemas

## Overview

All Fab artifacts use JSON Schema (draft-07) for validation. Schemas live in `dev-kernel/schemas/fab/` and follow existing kernel conventions.

## Schema Versioning

- Version: `schema_version: "1.0"` field in every document
- Files: Semantic suffix if parallel support needed (e.g., `critic-report.v2.schema.json`)
- Validation: Kernel validates reports using `jsonschema` before accepting verdicts

## Asset+Proof Schema

**File**: `dev-kernel/schemas/fab/asset-proof.schema.json`

Blender workcell output containing asset metadata and export proof.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "fab.schema.asset_proof.v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "run_id",
    "asset_id",
    "category",
    "files",
    "metadata"
  ],
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
      "required": [
        "blender_version",
        "exporter",
        "geometry_stats",
        "material_stats"
      ],
      "properties": {
        "blender_version": { "type": "string" },
        "exporter": {
          "type": "object",
          "properties": {
            "format": { "type": "string", "enum": ["glb", "gltf"] },
            "settings_hash": { "type": "string" }
          }
        },
        "geometry_stats": {
          "type": "object",
          "properties": {
            "triangle_count": { "type": "integer", "minimum": 0 },
            "vertex_count": { "type": "integer", "minimum": 0 },
            "bounds_m": {
              "type": "object",
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
          "properties": {
            "material_count": { "type": "integer" },
            "uses_textures": { "type": "boolean" }
          }
        }
      }
    }
  }
}
```

## Critic Report Schema

**File**: `dev-kernel/schemas/fab/critic-report.schema.json`

Aggregated output from all critics.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "fab.schema.critic_report.v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "run_id",
    "asset_id",
    "gate_config_id",
    "models",
    "views",
    "scores",
    "failures"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "run_id": { "type": "string" },
    "asset_id": { "type": "string" },
    "gate_config_id": { "type": "string" },
    "determinism": {
      "type": "object",
      "properties": {
        "cpu_only": { "type": "boolean" },
        "seeds": { "type": "object" },
        "framework_versions": { "type": "object" }
      }
    },
    "models": {
      "type": "array",
      "items": {
        "type": "object",
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
        "required": ["view_id", "mode", "image_path", "per_critic"],
        "properties": {
          "view_id": { "type": "string" },
          "mode": { "type": "string", "enum": ["beauty", "clay"] },
          "image_path": { "type": "string" },
          "per_critic": {
            "type": "object",
            "additionalProperties": {
              "type": "object",
              "required": ["score", "fail_codes"],
              "properties": {
                "score": { "type": "number", "minimum": 0, "maximum": 1 },
                "fail_codes": {
                  "type": "array",
                  "items": { "type": "string" }
                },
                "metrics": { "type": "object" }
              }
            }
          }
        }
      }
    },
    "scores": {
      "type": "object",
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
      "required": ["hard", "soft"],
      "properties": {
        "hard": { "type": "array", "items": { "type": "string" } },
        "soft": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

## Gate Verdict Schema

**File**: `dev-kernel/schemas/fab/gate-verdict.schema.json`

Final gate decision with next actions.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "fab.schema.gate_verdict.v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "run_id",
    "asset_id",
    "gate_config_id",
    "verdict",
    "scores",
    "failures",
    "next_actions"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "run_id": { "type": "string" },
    "asset_id": { "type": "string" },
    "gate_config_id": { "type": "string" },
    "verdict": { "type": "string", "enum": ["pass", "fail", "escalate"] },
    "scores": {
      "type": "object",
      "required": ["overall", "by_critic"],
      "properties": {
        "overall": { "type": "number", "minimum": 0, "maximum": 1 },
        "by_critic": {
          "type": "object",
          "additionalProperties": { "type": "number" }
        }
      }
    },
    "failures": {
      "type": "object",
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
        "required": ["action", "priority", "instructions"],
        "properties": {
          "action": {
            "type": "string",
            "enum": [
              "repair",
              "rerender_vote_pack",
              "fallback_to_template",
              "human_review"
            ]
          },
          "priority": { "type": "integer", "minimum": 1, "maximum": 5 },
          "instructions": { "type": "string" },
          "suggested_template_ref": { "type": "string" }
        }
      }
    }
  }
}
```

## Run Manifest Schema

**File**: `dev-kernel/schemas/fab/run-manifest.schema.json`

Immutable manifest for artifact provenance.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "fab.schema.run_manifest.v1",
  "type": "object",
  "required": [
    "schema_version",
    "run_id",
    "created_at",
    "files",
    "tool_versions"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "run_id": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "files": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
          "size_bytes": { "type": "integer" }
        }
      }
    },
    "tool_versions": {
      "type": "object",
      "properties": {
        "blender": { "type": "string" },
        "python": { "type": "string" },
        "dev_kernel": { "type": "string" }
      }
    },
    "iteration": {
      "type": "object",
      "properties": {
        "parent_run_id": { "type": ["string", "null"] },
        "iteration_index": { "type": "integer" }
      }
    }
  }
}
```

## Naming Conventions

| Element   | Pattern                         | Example                       |
| --------- | ------------------------------- | ----------------------------- |
| Run ID    | `run_<UTCISO>_<shortsha>`       | `run_20250115T143022Z_a1b2c3` |
| Views     | `<mode>_<view_id>.<ext>`        | `beauty_front_3q.png`         |
| Turntable | `<mode>_turntable_f<frame>.png` | `clay_turntable_f05.png`      |
| Reports   | Fixed paths in run directory    | `critics/report.json`         |
| Verdict   | Fixed path                      | `verdict/gate_verdict.json`   |

## Validation in Kernel

```python
import jsonschema

def validate_gate_verdict(verdict_data: dict) -> bool:
    """Validate verdict against schema before accepting"""
    schema = load_schema("fab/gate-verdict.schema.json")
    try:
        jsonschema.validate(verdict_data, schema)
        return True
    except jsonschema.ValidationError as e:
        log_error(f"Invalid gate verdict: {e.message}")
        return False
```

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Workcell Contract](./workcell-contract.md) - Existing Patch+Proof schema
