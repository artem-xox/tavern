"""The browser build must include the still action poses for every demo visitor."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_action_stills_ship_with_browser_build() -> None:
    """Check all character poses are available at their runtime URLs."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    for character in ("traveler", "veteran", "merchant"):
        for action, direction in (("Seated", "south"), ("Darts", "south"), ("Bathroom", "north")):
            path = ROOT / "frontend" / "dist" / "characters" / character / action / f"{direction}.png"
            assert path.is_file(), f"Missing browser asset: {path}"
