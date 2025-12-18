#!/usr/bin/env python3
"""
Create a sprite sheet atlas from rendered frame sequence.

Usage:
    python create_spritesheet.py

Requires: Pillow (pip install Pillow)
"""

import os
import json
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    exit(1)


def create_spritesheet(
    input_dir: Path,
    output_path: Path,
    grid_cols: int = 8,
    grid_rows: int = 6,
    total_frames: int = 48,
    fps: int = 24,
):
    """Create a sprite sheet atlas from a sequence of PNG frames."""

    # Find frames
    frames = sorted(input_dir.glob("frame_*.png"))
    if not frames:
        print(f"No frames found in {input_dir}")
        return False

    print(f"Found {len(frames)} frames")

    # Load first frame to get dimensions
    first_frame = Image.open(frames[0])
    frame_width, frame_height = first_frame.size

    # Calculate atlas dimensions
    atlas_width = frame_width * grid_cols
    atlas_height = frame_height * grid_rows

    print(f"Creating atlas: {atlas_width}x{atlas_height}")
    print(f"Grid: {grid_cols}x{grid_rows}")
    print(f"Frame size: {frame_width}x{frame_height}")

    # Create new RGBA image with transparent background
    atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))

    # Place each frame
    for i, frame_path in enumerate(frames[:total_frames]):
        frame = Image.open(frame_path)

        # Calculate position in grid
        col = i % grid_cols
        row = i // grid_cols

        x = col * frame_width
        y = row * frame_height

        atlas.paste(frame, (x, y))

        if (i + 1) % 12 == 0:
            print(f"  Placed frame {i + 1}/{min(len(frames), total_frames)}")

    # Save atlas
    atlas.save(output_path, "PNG", optimize=True)
    print(f"\nAtlas saved to: {output_path}")

    # Create metadata JSON
    metadata = {
        "atlas": {
            "width": atlas_width,
            "height": atlas_height,
        },
        "frame": {
            "width": frame_width,
            "height": frame_height,
        },
        "grid": {
            "columns": grid_cols,
            "rows": grid_rows,
        },
        "animation": {
            "total_frames": min(len(frames), total_frames),
            "fps": fps,
            "duration_seconds": min(len(frames), total_frames) / fps,
            "loop": True,
        },
        "usage": {
            "uv_step_x": 1.0 / grid_cols,
            "uv_step_y": 1.0 / grid_rows,
            "note": "Frames are arranged left-to-right, top-to-bottom",
        },
    }

    metadata_path = output_path.with_suffix(".json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved to: {metadata_path}")

    return True


if __name__ == "__main__":
    # Paths
    project_root = Path(__file__).parent.parent
    input_dir = project_root / "export" / "space_gel_drip"
    output_path = project_root / "export" / "space_gel_drip_atlas.png"

    # Create sprite sheet
    success = create_spritesheet(
        input_dir=input_dir,
        output_path=output_path,
        grid_cols=8,
        grid_rows=6,
        total_frames=48,
        fps=24,
    )

    if success:
        print("\n✓ Sprite sheet created successfully!")
        print(f"\nTo use in your web app:")
        print(f"  - Atlas image: {output_path}")
        print(f"  - Metadata: {output_path.with_suffix('.json')}")
    else:
        print("\n✗ Failed to create sprite sheet")
