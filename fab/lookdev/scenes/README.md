# Lookdev Scenes

This directory contains versioned Blender lookdev scenes for asset evaluation.

## Creating the Scene

The lookdev scene is generated using the script in `../scripts/`:

```bash
# From Blender command line:
blender --background --python ../scripts/create_car_lookdev_v001.py -- --output car_lookdev_v001.blend

# Or run interactively in Blender's scripting workspace
```

## Scene: car_lookdev_v001.blend

**Version**: 1.0.0  
**Category**: car  
**Created**: 2024-12-17

### Contents

- **Collections**:

  - `Lighting/` - Three-point lighting setup
  - `Environment/` - Ground plane, backdrop
  - `Cameras/` - 6 fixed cameras + turntable ready
  - `Asset/` - Empty collection for imported assets

- **Cameras**:

  - `cam_front_3q` - Primary presentation view
  - `cam_rear_3q` - Back detail view
  - `cam_side_left` - Profile view
  - `cam_front` - Direct front
  - `cam_top` - Top-down view
  - `cam_close_wheel_front` - Wheel detail

- **View Layers**:

  - `beauty` - Full materials
  - `clay` - Gray material override

- **Render Settings**:
  - Engine: Cycles (CPU)
  - Resolution: 768×512
  - Samples: 128
  - Seed: 1337

## Generating the Scene

If `car_lookdev_v001.blend` doesn't exist, generate it:

```bash
cd /path/to/glia-fab/fab/lookdev/scripts
blender --background --python create_car_lookdev_v001.py -- -o ../scenes/car_lookdev_v001.blend
```

## Verification

After generating, verify the scene:

1. Open in Blender
2. Check all cameras render correctly
3. Verify ground plane shadow catcher works
4. Test asset import workflow
