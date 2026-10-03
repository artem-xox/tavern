"""The browser build must include Idle stills for the six tavern visitors."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("edda", "rurik", "toren", "cook", "courier", "visitor")


def test_character_stills_ship_with_browser_build() -> None:
    """Check that each assigned character and direction has a published PNG."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    for character in CHARACTERS:
        for direction in ("north", "south", "east", "west"):
            path = ROOT / "frontend" / "dist" / "characters" / character / "Idle" / "rotations" / f"{direction}.png"
            assert path.is_file(), f"Missing browser asset: {path}"
