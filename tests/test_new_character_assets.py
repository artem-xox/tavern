"""Every named PixelLab visitor must have complete local still exports."""

import json
import struct
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "data" / "scenarios" / "first_evening.json"
STATES = ("Idle", "Seated", "Darts", "Bathroom", "Drinking", "DrinkingSeated", "TalkingSeated", "TakeBeer", "Walking", "Talking")
DIRECTIONS = ("north", "south", "east", "west")


@pytest.mark.parametrize(
    ("character", "actor_id", "display_name"),
    [
        pytest.param("edda", "mara", "Edda", id="healer"),
        pytest.param("rurik", "ivo", "Rurik", id="guard"),
        pytest.param("toren", "nell", "Toren", id="trader"),
        pytest.param("cook", "brannoc", "Brida", id="cook"),
        pytest.param("courier", "wenna", "Calder", id="courier"),
        pytest.param("visitor", "osric", "Saye", id="storyteller"),
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

    scenario = json.loads(SCENARIO.read_text())
    guest = next(guest for guest in scenario["guests"] if guest["id"] == actor_id)
    assert (guest["name"], guest["sprite"]) == (display_name, character)


def test_rurik_uses_replacement_pixel_lab_group() -> None:
    """Keep the compact original guard group out of the shipped roster."""
    metadata = json.loads(
        (ROOT / "frontend" / "static" / "characters" / "rurik" / "metadata.json").read_text()
    )
    assert metadata["group_id"] != "d0e1751d-6fc5-409c-ae81-9680ed03834b"


def test_saye_uses_the_regenerated_walking_state() -> None:
    """Keep the visually inconsistent storyteller walk out of the shipped roster."""
    metadata = json.loads(
        (ROOT / "frontend" / "static" / "characters" / "visitor" / "metadata.json").read_text()
    )
    walking = next(state for state in metadata["states"] if state["folder"] == "Walking")
    assert walking["character"]["id"] != "16ef800f-fa48-4726-8fac-a4a9c1e9ded2"
