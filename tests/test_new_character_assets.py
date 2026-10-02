"""The three named PixelLab visitors must have complete local still exports."""

import json
import struct
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STATES = ("Idle", "Seated", "Darts", "Bathroom", "Drinking", "TakeBeer", "Walking", "Talking")
DIRECTIONS = ("north", "south", "east", "west")


@pytest.mark.parametrize(
    ("character", "actor_id", "display_name"),
    [
        pytest.param("edda", "mara", "Edda", id="healer"),
        pytest.param("rurik", "ivo", "Rurik", id="guard"),
        pytest.param("toren", "nell", "Toren", id="trader"),
    ],
)
def test_character_group_is_ready_for_tavern(character: str, actor_id: str, display_name: str) -> None:
    """Require every state and direction at native resolution for each visitor."""
    folder = ROOT / "frontend" / "static" / "characters" / character
    metadata = json.loads((folder / "metadata.json").read_text())
    assert {state["folder"] for state in metadata["states"]} == set(STATES)
    for state in STATES:
        for direction in DIRECTIONS:
            png = folder / state / "rotations" / f"{direction}.png"
            assert png.is_file(), f"Missing {png}"
            assert struct.unpack(">II", png.read_bytes()[16:24]) == (68, 68)

    layout = json.loads((ROOT / "data" / "tavern.json").read_text())
    assert next(actor["name"] for actor in layout["actors"] if actor["id"] == actor_id) == display_name
