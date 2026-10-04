"""The browser build must include only the six full-action tavern visitors."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("edda", "rurik", "toren", "cook", "courier", "visitor")
DIRECTIONS = ("north", "south", "east", "west")


def test_action_stills_ship_with_browser_build() -> None:
    """Check seated action stills ship for every named visitor and no other folder."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    assert {folder.name for folder in exported.iterdir() if folder.is_dir()} == set(CHARACTERS)
    for character in CHARACTERS:
        for direction in DIRECTIONS:
            for pose in ("DrinkingSeated", "TalkingSeated"):
                path = exported / character / pose / "rotations" / f"{direction}.png"
                assert path.is_file(), f"Missing browser asset: {path}"
