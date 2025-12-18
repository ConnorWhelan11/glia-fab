# Fab Render Harness

## Overview

The Render Harness produces **canonical, deterministic renders** of Blender assets for evaluation by the Critics Stack. It is kernel-owned and agent-inaccessible—assets are evaluated only through this controlled pipeline.

## Lookdev Scene Specification

### Scene Invariants

The lookdev scene (`.blend` file) must enforce:

| Element              | Specification                                                                         |
| -------------------- | ------------------------------------------------------------------------------------- |
| **World**            | Single HDRI (pinned file + rotation), optional key/fill/rim area lights               |
| **Ground**           | Shadow catcher plane at z=0, neutral gray, subtle roughness, optional curved backdrop |
| **Color Management** | Pinned (Filmic or Standard), fixed exposure/contrast                                  |
| **Render Layers**    | Beauty (RGBA), Object mask, Depth (linear), Normal (world/camera space)               |
| **Clay Override**    | View layer with all materials overridden by neutral Principled BSDF (matte gray)      |

### Scene Structure

```
car_lookdev_v001.blend
├── Collections/
│   ├── Lighting/
│   │   ├── HDRI_World
│   │   ├── Key_Light (optional)
│   │   ├── Fill_Light (optional)
│   │   └── Rim_Light (optional)
│   ├── Environment/
│   │   ├── Ground_Plane (shadow catcher)
│   │   └── Backdrop (optional)
│   ├── Cameras/
│   │   ├── cam_front_3q
│   │   ├── cam_rear_3q
│   │   ├── cam_side_left
│   │   ├── cam_front
│   │   ├── cam_top
│   │   ├── cam_wheel_close
│   │   └── cam_turntable (animated)
│   └── Asset/
│       └── (imported asset goes here)
├── View Layers/
│   ├── beauty
│   └── clay (material override)
└── World/
    └── HDRI_Environment
```

### Versioning

```yaml
lookdev_scene_id: "car_lookdev_v001"
file_sha256: "a1b2c3d4..."
blender_version: "4.1.0"
hdri_ref: "studio_small_09_4k.exr"
hdri_sha256: "e5f6g7h8..."
```

## Camera Rig Specification

### Fixed Cameras (Minimum Set)

| Camera ID           | Description                     | Purpose                       |
| ------------------- | ------------------------------- | ----------------------------- |
| `front_3q`          | Front three-quarter, eye height | Primary presentation view     |
| `rear_3q`           | Rear three-quarter, eye height  | Back detail, symmetry check   |
| `side_left`         | Profile view                    | Proportions, silhouette       |
| `front`             | Direct front                    | Frontal symmetry              |
| `top`               | Top-down, slightly forward      | Roof shape, overall footprint |
| `close_wheel_front` | Macro-ish, front wheel          | Wheel detail, ground contact  |

### Turntable Animation

| Parameter | Value                     |
| --------- | ------------------------- |
| Frames    | 12 (30° increments)       |
| Axis      | Z (vertical)              |
| Center    | Asset origin (normalized) |
| Modes     | Both beauty and clay      |

### Camera Rig JSON Schema

```json
{
  "rig_id": "car_camrig_v001",
  "fixed_cameras": [
    {
      "id": "front_3q",
      "type": "perspective",
      "focal_length_mm": 50,
      "position_mode": "auto",
      "azimuth_deg": 45,
      "elevation_deg": 15,
      "distance_mode": "bbox_diagonal",
      "distance_factor": 2.5
    }
  ],
  "turntable": {
    "enabled": true,
    "frames": 12,
    "axis": "Z",
    "start_angle_deg": 0,
    "camera_ref": "front_3q"
  }
}
```

### Deterministic Placement Rules

1. **Origin Normalization**: Asset origin at geometric center, lowest vertex at z=0
2. **Scale Normalization**: Bounding box diagonal used for camera distance calculation
3. **Rotation Normalization**: Front of asset aligned to -Y axis (Blender convention)

## Render Settings

### Determinism-First Defaults

| Setting    | Value                                  | Rationale                                             |
| ---------- | -------------------------------------- | ----------------------------------------------------- |
| Engine     | CYCLES                                 | Industry standard, deterministic with CPU             |
| Device     | CPU                                    | GPU introduces variance; CPU for baseline determinism |
| Resolution | 768×512 (V0), 1024×768 (V1)            | Balance quality vs. speed                             |
| Samples    | 128                                    | No adaptive sampling in V0                            |
| Seed       | Fixed integer from config (e.g., 1337) | Reproducible noise patterns                           |
| Denoiser   | Off (V0)                               | Avoid nondeterministic denoise variance               |
| Film       | Transparent off                        | Preserve ground/shadows                               |
| Output     | PNG 16-bit                             | Lossless, wide color support                          |
| Threads    | Fixed count (or 1 for max determinism) | Control parallelism variance                          |

### Render Configuration YAML

```yaml
render:
  engine: CYCLES
  device: CPU
  resolution: [768, 512]
  samples: 128
  seed: 1337
  denoise: false
  film:
    transparent: false
  output:
    format: PNG
    color_depth: 16
    color_mode: RGBA
  threads: 4 # Pin for determinism
```

### Render Passes

| Pass   | Format             | Purpose                  |
| ------ | ------------------ | ------------------------ |
| Beauty | PNG (RGBA)         | Primary evaluation       |
| Clay   | PNG (RGBA)         | Geometry-only evaluation |
| Mask   | PNG (L)            | Object segmentation      |
| Depth  | EXR (32-bit float) | Distance analysis        |
| Normal | EXR (RGB float)    | Surface orientation      |

## Headless Invocation

### CLI Contract

```bash
python -m dev_kernel.fab.render \
  --asset /path/to/asset.glb \
  --config /path/to/gate_config.yaml \
  --lookdev /path/to/lookdev.blend \
  --output /path/to/fab/runs/<run_id>/render/ \
  --manifest /path/to/fab/runs/<run_id>/manifest.json
```

### Blender Invocation Flags

```bash
blender \
  --background \
  --factory-startup \
  --noaudio \
  --python /path/to/render_script.py \
  -- \
  --asset /path/to/asset.glb \
  --config /path/to/render_config.json \
  --output /path/to/render/
```

### Environment Variables (Determinism)

```bash
export PYTHONHASHSEED=0
export BLENDER_THREADS=4
export BLENDER_SEED=1337
```

## Output Structure

```
fab/runs/<run_id>/render/
├── beauty/
│   ├── front_3q.png
│   ├── rear_3q.png
│   ├── side_left.png
│   ├── front.png
│   ├── top.png
│   ├── close_wheel_front.png
│   ├── turntable_f00.png
│   ├── turntable_f01.png
│   └── ...turntable_f11.png
├── clay/
│   ├── front_3q.png
│   ├── rear_3q.png
│   └── ...(same views as beauty)
└── passes/
    ├── mask/
    │   └── front_3q.png
    ├── depth/
    │   └── front_3q.exr
    └── normal/
        └── front_3q.exr
```

## Stability Considerations

### CI Environment (Recommended)

| Requirement  | Specification                                     |
| ------------ | ------------------------------------------------- |
| Container    | Linux-based with pinned Blender build             |
| OS Libraries | Pinned versions (Mesa, OpenGL drivers)            |
| Python       | Pinned version matching Blender's embedded Python |

### Local Development

| Platform              | Determinism Level              |
| --------------------- | ------------------------------ |
| Linux (containerized) | Full                           |
| Linux (native)        | High (with pinned deps)        |
| macOS                 | Best-effort (Metal variance)   |
| Windows               | Best-effort (DirectX variance) |

## Error Handling

### Import Failures

| Error Type     | Action                             |
| -------------- | ---------------------------------- |
| File not found | Hard fail, `IMPORT_FILE_NOT_FOUND` |
| Invalid glTF   | Hard fail, `IMPORT_INVALID_GLTF`   |
| Blender crash  | Hard fail, `BLENDER_CRASH`         |
| Timeout        | Hard fail, `RENDER_TIMEOUT`        |

### Render Failures

| Error Type       | Action                                |
| ---------------- | ------------------------------------- |
| Out of memory    | Hard fail, `RENDER_OOM`               |
| Missing textures | Warning + continue (critic will flag) |
| Corrupted output | Retry once, then hard fail            |

## Performance Budget

| Stage                                | Target Time | Notes                      |
| ------------------------------------ | ----------- | -------------------------- |
| Asset import                         | <5s         | glTF parsing + scene setup |
| Per-view render (beauty)             | <30s        | 768×512 @ 128 samples      |
| Per-view render (clay)               | <20s        | Simpler materials          |
| Full turntable (12 frames × 2 modes) | <10min      | Parallelizable per-frame   |
| Total harness execution              | <15min      | All views + passes         |

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Critics Stack](./fab-critics.md) - How renders are evaluated
- [Gate Decision Logic](./fab-gate-logic.md) - How verdicts are computed
