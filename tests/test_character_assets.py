"""The browser build must include the PixelLab stills used by the demo visitors."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_character_stills_ship_with_browser_build() -> None:
    """Check that each assigned character and direction has a published PNG."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    for character in ("traveler", "veteran", "merchant"):
        for direction in ("north", "south", "east", "west"):
            path = ROOT / "frontend" / "dist" / "characters" / character / "Idle" / "rotations" / f"{direction}.png"
            assert path.is_file(), f"Missing browser asset: {path}"
