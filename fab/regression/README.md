# Fab Regression Dataset

This directory contains the calibration and regression testing dataset for the Fab Realism Gate.

## Purpose

1. **Calibration**: Tune critic thresholds based on known-good and known-bad assets
2. **Regression Testing**: Ensure gate changes don't break existing functionality
3. **Golden Renders**: Reference renders for visual comparison

## Directory Structure

```
fab/regression/
├── README.md                    # This file
├── manifest.json                # Dataset manifest with expected verdicts
├── assets/
│   ├── good/                    # Assets that should PASS
│   │   ├── car_sedan_001.glb
│   │   ├── car_suv_001.glb
│   │   └── ...
│   ├── bad/                     # Assets that should FAIL
│   │   ├── blob_001.glb         # Obvious blobs
│   │   ├── wrong_scale_001.glb  # Scale issues
│   │   └── ...
│   └── edge/                    # Edge cases (document expected behavior)
│       ├── stylized_car_001.glb
│       └── ...
├── golden_renders/              # Reference renders for comparison
│   ├── car_sedan_001/
│   │   ├── beauty/
│   │   └── clay/
│   └── ...
└── expected_verdicts/           # Expected gate outputs
    ├── car_sedan_001.json
    └── ...
```

## Adding New Assets

### Good Assets (should pass)

1. Place GLB file in `assets/good/`
2. Name format: `{category}_{type}_{number}.glb` (e.g., `car_sedan_001.glb`)
3. Run gate to generate golden renders:
   ```bash
   python -m dev_kernel.fab.gate \
     --asset fab/regression/assets/good/car_sedan_001.glb \
     --config fab/gates/car_realism_v001.yaml \
     --output fab/regression/golden_renders/car_sedan_001
   ```
4. Verify the asset passes
5. Add to `manifest.json` with expected verdict

### Bad Assets (should fail)

1. Place GLB file in `assets/bad/`
2. Name format: `{failure_type}_{number}.glb` (e.g., `blob_001.glb`)
3. Document expected failure codes in `manifest.json`

## Manifest Format

```json
{
  "schema_version": "1.0",
  "created_at": "2025-12-18T00:00:00Z",
  "gate_config_id": "car_realism_v001",
  "assets": [
    {
      "path": "assets/good/car_sedan_001.glb",
      "category": "car",
      "expected_verdict": "pass",
      "min_score": 0.8,
      "notes": "Clean sedan model with proper proportions"
    },
    {
      "path": "assets/bad/blob_001.glb",
      "category": "car",
      "expected_verdict": "fail",
      "expected_fail_codes": ["CAT_NO_CAR_DETECTED", "GEO_WHEEL_COUNT_LOW"],
      "notes": "Intentional blob to test rejection"
    }
  ]
}
```

## Running Regression Tests

```bash
# Full regression suite
python -m dev_kernel.fab.regression run

# Specific category
python -m dev_kernel.fab.regression run --category car

# Update golden renders (after intentional changes)
python -m dev_kernel.fab.regression update-golden

# Compare current results to golden
python -m dev_kernel.fab.regression compare
```

## Calibration Process

1. **Collect Diverse Assets**: Gather 50+ good and 50+ bad examples per category
2. **Generate Scores**: Run all assets through gate, collect per-critic scores
3. **Analyze Distribution**: Plot score distributions for good vs bad
4. **Set Thresholds**: Choose thresholds that maximize separation
5. **Validate**: Run regression suite to verify thresholds work

### Calibration Script

```bash
python -m dev_kernel.fab.calibrate \
  --good-dir fab/regression/assets/good \
  --bad-dir fab/regression/assets/bad \
  --output fab/calibration_report.json
```

## Threshold Tuning Guidelines

| Metric          | Good Assets | Bad Assets | Recommended Threshold |
| --------------- | ----------- | ---------- | --------------------- |
| Category Score  | > 0.85      | < 0.50     | 0.70                  |
| Alignment Score | > 0.75      | < 0.40     | 0.60                  |
| Realism Score   | > 0.70      | < 0.45     | 0.55                  |
| Geometry Score  | > 0.80      | < 0.30     | 0.60                  |
| Overall Score   | > 0.80      | < 0.45     | 0.75                  |

## Contributing Assets

When contributing assets to the regression dataset:

1. Ensure you have rights to share the asset
2. Remove any proprietary textures/materials
3. Normalize scale to real-world units (meters)
4. Document the source and any modifications
5. Test locally before submitting
