# Fab Lookdev Assets

This directory contains versioned lookdev scenes and camera rigs for the Fab Realism Gate.

## Directory Structure

```
fab/lookdev/
├── scenes/           # Versioned Blender lookdev scenes
│   └── car_lookdev_v001.blend
├── rigs/             # Camera rig JSON definitions
│   └── car_camrig_v001.json
├── hdris/            # Pinned HDRI files with hashes
│   └── manifest.json
└── README.md
```

## Scene Invariants

All lookdev scenes MUST enforce:

| Element           | Specification                                                        |
| ----------------- | -------------------------------------------------------------------- |
| **World**         | Single HDRI (pinned file + rotation), optional key/fill/rim lights   |
| **Ground**        | Shadow catcher plane at z=0, neutral gray, subtle roughness          |
| **Color Mgmt**    | Pinned (Filmic or Standard), fixed exposure/contrast                 |
| **Render Layers** | Beauty (RGBA), Object mask, Depth (linear), Normal (world/camera)    |
| **Clay Override** | View layer with all materials → neutral Principled BSDF (matte gray) |

## Scene Structure Convention

```
<category>_lookdev_v<version>.blend
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
│       └── (imported asset placeholder)
├── View Layers/
│   ├── beauty
│   └── clay (material override)
└── World/
    └── HDRI_Environment
```

## Camera Rig Convention

Camera rigs are defined in JSON for programmatic access:

```json
{
  "rig_id": "car_camrig_v001",
  "fixed_cameras": [
    {
      "id": "front_3q",
      "type": "perspective",
      "focal_length_mm": 50,
      "azimuth_deg": 45,
      "elevation_deg": 15,
      "distance_mode": "bbox_diagonal",
      "distance_factor": 2.5
    }
  ],
  "turntable": {
    "enabled": true,
    "frames": 12,
    "axis": "Z"
  }
}
```

## Versioning Rules

1. **Immutability**: Once published, scenes are never modified
2. **Semantic versioning**: `v<major>.<minor>.<patch>`
3. **Hash tracking**: All files tracked with SHA256 in manifest
4. **Golden tests**: Each scene includes render snapshots for regression

## Asset Normalization

When importing assets into lookdev scenes:

1. **Origin**: Geometric center, lowest vertex at z=0
2. **Scale**: Preserve real-world units (meters)
3. **Rotation**: Front of asset aligned to -Y axis
4. **Camera distance**: Computed from bounding box diagonal

## Creating New Scenes

1. Copy existing scene as template
2. Increment version number
3. Update manifest with new hashes
4. Run golden test renders
5. Commit with clear changelog
