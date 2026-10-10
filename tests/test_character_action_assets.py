"""The browser build must include the full-action tavern character art."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ("edda", "rurik", "toren", "cook", "courier", "visitor", "bartender")
DIRECTIONS = ("north", "south", "east", "west")
FIGHT_POSES = ("Fighting", "KnockedOut", "Hurt", "HurtSeated", "Shoving", "HelpingUp")


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


def test_giving_and_receiving_stills_ship_for_every_character() -> None:
    """Check both sides of a hand-over, standing and seated, ship for every character folder."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    for character in CHARACTERS:
        for direction in DIRECTIONS:
            for pose in ("Giving", "GivingSeated", "Receiving", "ReceivingSeated"):
                path = exported / character / pose / "rotations" / f"{direction}.png"
                assert path.is_file(), f"Missing browser asset: {path}"


def test_sleeping_stills_ship_for_every_character() -> None:
    """Check the nap at the table, seated and asleep, ships in four views for every character folder."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    for character in CHARACTERS:
        for direction in DIRECTIONS:
            path = exported / character / "SleepingSeated" / "rotations" / f"{direction}.png"
            assert path.is_file(), f"Missing browser asset: {path}"


def test_fight_stills_ship_for_every_guest() -> None:
    """Check every guest has the six combat and recovery poses in four views."""
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True, capture_output=True)
    exported = ROOT / "frontend" / "dist" / "characters"
    for character in ("edda", "rurik", "toren", "cook", "courier", "visitor"):
        for direction in DIRECTIONS:
            for pose in FIGHT_POSES:
                path = exported / character / pose / "rotations" / f"{direction}.png"
                assert path.is_file(), f"Missing browser asset: {path}"
