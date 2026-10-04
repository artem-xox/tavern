"""The repository hall's composition: where the darts, the fireplace and the dice table stand relative to each other."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.hall.room import object_cells
from tavern.hall.world import create_world

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def only(kind: str) -> dict[str, Any]:
    """The hall's single object of a kind."""
    found = [item for item in create_world(LAYOUT)["map"]["objects"] if item["kind"] == kind]
    assert len(found) == 1, f"expected one {kind}, found {len(found)}"
    return found[0]


def middle(item: dict[str, Any]) -> float:
    """The column through the middle of an object, in cells (a cell's middle is its x + 0.5)."""
    return item["x"] + item.get("width", 1) / 2


def test_the_fireplace_is_in_the_north_wall_straight_across_from_the_door() -> None:
    fireplace, door = only("fireplace"), only("door")
    assert (fireplace["y"], middle(fireplace)) == (0, middle(door))


def test_the_darts_hang_on_the_west_wall_on_the_dice_tables_row() -> None:
    darts, dice = only("darts"), only("dice_table")
    assert (darts["x"], darts["y"]) == (1, dice["y"])


def test_the_hall_is_walled_all_round() -> None:
    world = create_world(LAYOUT)
    width, height = world["map"]["width"], world["map"]["height"]
    edge = {(x, y) for x in range(width) for y in range(height) if x in (0, width - 1) or y in (0, height - 1)}
    closed = {tuple(cell) for cell in world["map"]["blocked"]} | {
        cell for item in world["map"]["objects"] for cell in object_cells(item)}
    # A wall cell given to a window, the door or the fireplace is closed by that object.
    assert sorted(edge - closed) == []


def test_the_fireplace_is_stood_at_from_the_row_below_it() -> None:
    fireplace = only("fireplace")
    width = fireplace.get("width", 1)
    assert [(spot[1], 0 <= spot[0] - fireplace["x"] < width) for spot in fireplace["interaction_spots"]] == [
        (fireplace["y"] + 1, True)] * len(fireplace["interaction_spots"])


@pytest.mark.parametrize("cell", [
    pytest.param([9, 0], id="left-of-the-door-column"),
    pytest.param([10, 0], id="on-the-door-column"),
    pytest.param([11, 0], id="right-of-the-door-column"),
])
def test_fireplace_cells_are_not_also_walls(cell: list[int]) -> None:
    # The fireplace is built into the wall: its cells are its own, never listed as blocked as well.
    assert cell not in create_world(LAYOUT)["map"]["blocked"]
