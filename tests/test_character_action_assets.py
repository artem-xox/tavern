"""The browser build must include the full-action tavern character art."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("edda", "rurik", "toren", "cook", "courier", "visitor", "bartender")
DIRECTIONS = ("north", "south", "east", "west")


def test_action_stills_ship_with_browser_build() -> None:
    """Check seated action stills ship for every shipped character folder."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    assert {folder.name for folder in exported.iterdir() if folder.is_dir()} == set(CHARACTERS)
    for character in CHARACTERS:
        for direction in DIRECTIONS:
            for pose in ("DrinkingSeated", "TalkingSeated"):
                path = exported / character / pose / "rotations" / f"{direction}.png"
                assert path.is_file(), f"Missing browser asset: {path}"


def test_pouring_beer_still_is_bartender_only() -> None:
    """Keep the bar-serving pose available only to the bartender asset folder."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    for direction in DIRECTIONS:
        path = exported / "bartender" / "PouringBeer" / "rotations" / f"{direction}.png"
        assert path.is_file(), f"Missing bartender asset: {path}"
    for character in CHARACTERS:
        if character != "bartender":
            assert not (exported / character / "PouringBeer").exists()
