"""The repository hall is closed all round."""

import json
from pathlib import Path

from tavern.hall.room import object_cells
from tavern.hall.world import create_world

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def test_the_hall_is_walled_all_round() -> None:
    world = create_world(LAYOUT)
    width, height = world["map"]["width"], world["map"]["height"]
    edge = {(x, y) for x in range(width) for y in range(height) if x in (0, width - 1) or y in (0, height - 1)}
    closed = {tuple(cell) for cell in world["map"]["blocked"]} | {
        cell for item in world["map"]["objects"] for cell in object_cells(item)}
    # A wall cell given to a window, the door or the fireplace is closed by that object.
    assert sorted(edge - closed) == []
