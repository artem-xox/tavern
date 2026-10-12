"""The filesystem catalog requires complete role-specific eight-view art."""

import json
import struct
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import DIRECTIONS, GUEST_POSES, load_catalog
from tavern.evening.scenario import parse_scenario
from tavern.mind.cards import PARAMS


def character() -> dict[str, Any]:
    """Build the profile fields unrelated to files."""
    return {"id": "ada", "role": "guest", "name": "Ada", "color": "#a08060", "looks": "the drover",
            "occupation": "drover", "background": "Drives cattle.", "temperament": "Calm.", "speech": "Slow.",
            "quirks": "Counts mugs.", "secret": "Lost a herd.", "goal": "Rest.", "sex": "female",
            "params": dict.fromkeys(PARAMS, 0.5), "carries": {}}


def png(size: int = 68) -> bytes:
    """Build the signature and transparent RGBA header the catalog checks."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sIIBBBBB", 13, b"IHDR", size, size, 8, 6, 0, 0, 0)


def catalog(tmp_path: Path, missing: tuple[str, str] | None = None) -> Path:
    """Write a complete single-guest catalog, optionally omitting one image."""
    folder = tmp_path / "ada"
    folder.mkdir()
    (folder / "character.json").write_text(json.dumps(character()))
    (folder / "relationships.json").write_text("[]")
    (folder / "visuals.json").write_text(json.dumps({"size": 68, "lift": -16}))
    for pose in GUEST_POSES:
        for direction in DIRECTIONS:
            if (pose, direction) != missing:
                path = folder / "art" / pose / "rotations" / f"{direction}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png())
    return tmp_path


def test_load_catalog_reads_a_complete_character_directory(tmp_path: Path) -> None:
    loaded = load_catalog(catalog(tmp_path))
    assert (loaded.character("ada")["card"]["sprite"], loaded.public()["characters"][0]["sprite"]) == ("ada", "ada")


@pytest.mark.parametrize("missing, message", [
    pytest.param(("Idle", "north-east"), "north-east", id="missing-diagonal"),
    pytest.param(("Fighting", "south"), "Fighting", id="missing-guest-pose"),
])
def test_load_catalog_refuses_incomplete_eight_view_art(tmp_path: Path, missing: tuple[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_catalog(catalog(tmp_path, missing))


def test_repository_scenario_resolves_catalog_defaults() -> None:
    root = Path(__file__).resolve().parents[1]
    loaded = load_catalog(root / "characters")
    scenario = parse_scenario(json.loads((root / "data" / "scenarios" / "first_evening.json").read_text()), catalog=loaded)
    edda = next(guest for guest in scenario.guests if guest["id"] == "edda")
    assert (edda["sprite"], edda["carries"], len(scenario.ties), scenario.staff[0]["card"]["id"]) == (
        "edda", {"remedy": 3}, 3, "hob")
