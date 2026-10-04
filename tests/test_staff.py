"""The staff cells behind the bar: what a hall must say about them, and how guests keep out."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.hall.staff import off_limits
from tavern.hall.world import create_world, start_action, step_world
from tavern.server.controls import toggle_block

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
CELLS = [[2, 1], [3, 1], [4, 1], [5, 1]]


def room(**bar: Any) -> dict[str, Any]:
    """The repository's hall with fields of its bar replaced; a value of None removes the field."""
    data = deepcopy(LAYOUT)
    item = next(item for item in data["objects"] if item["id"] == "bar")
    for key, value in bar.items():
        item.pop(key, None) if value is None else item.update({key: value})
    return data


def amended(object_id: str, **fields: Any) -> dict[str, Any]:
    """The repository's hall with fields of one object replaced."""
    data = deepcopy(LAYOUT)
    next(item for item in data["objects"] if item["id"] == object_id).update(fields)
    return data


def guest(actor_id: str, x: int, y: int) -> dict[str, Any]:
    """Describe a visitor standing on a cell."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": x, "y": y}


def hall_with(*actors: dict[str, Any]) -> dict[str, Any]:
    """The repository's hall, without its arrival draws, holding the given visitors."""
    data = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    return create_world({**data, "actors": list(actors)})


def tiny_hall(darts_spot: list[int]) -> dict[str, Any]:
    """A 7×3 hall whose only floor is one corridor, (1, 1) to (5, 1), with a tap and darts below it.

    The tap's spot is (1, 1), and the staff cell (2, 1) is the only one next to the tap. With the darts'
    spot at (3, 1) it lies between the two places; with the darts' spot at (1, 1) it cuts nothing off.
    """
    walls = [[x, 0] for x in range(7)] + [[0, 1], [6, 1], [0, 2], [1, 2], [4, 2], [6, 2]]
    return {"width": 7, "height": 3, "blocked": walls, "objects": [
        {"id": "tap", "kind": "tap", "x": 2, "y": 2, "interaction_spots": [[1, 1]], "stock": 5},
        {"id": "darts", "kind": "darts", "x": 3, "y": 2, "interaction_spots": [darts_spot]},
        {"id": "bar", "kind": "bar", "x": 5, "y": 2, "staff_cells": [[2, 1]], "staff_facing": "south"}]}


def test_the_repository_bar_has_four_staff_cells_and_one_is_next_to_the_tap() -> None:
    bar = next(item for item in create_world(LAYOUT)["map"]["objects"] if item["id"] == "bar")
    assert (bar["staff_cells"], bar["staff_facing"], [5, 1] in bar["staff_cells"]) == (CELLS, "south", True)


@pytest.mark.parametrize("data, message", [
    pytest.param(amended("tap", staff_cells=[[5, 1]], staff_facing="south"), "belong to a bar", id="on-a-tap"),
    pytest.param(room(staff_cells=[]), "nonempty list of cells", id="empty"),
    pytest.param(room(staff_cells=[[5]]), "nonempty list of cells", id="malformed-cell"),
    pytest.param(room(staff_cells=[[4, 1], [4, 1], [5, 1]]), "distinct", id="repeated-cell"),
    pytest.param(room(staff_cells=[[5, 1], [5, 99]]), "inside the hall", id="outside-the-hall"),
    pytest.param(room(staff_cells=[[5, 1], [5, 0]]), "free floor", id="on-a-wall"),
    pytest.param(room(staff_cells=[[5, 1], [5, 2]]), "free floor", id="on-the-bar"),
    pytest.param(room(staff_cells=[[5, 1], [4, 1], [10, 5]]), "free floor", id="on-a-table"),
    pytest.param(room(staff_cells=[[2, 1], [3, 1], [5, 1]]), "one stretch", id="with-a-gap"),
    pytest.param(amended("tap", interaction_spots=[[5, 1]]), "keep off", id="on-the-taps-spot"),
    pytest.param(amended("tap", queue_spots=[[7, 4], [8, 4], [9, 4], [10, 4], [11, 4], [4, 1]]), "keep off",
                 id="on-a-queue-spot"),
    pytest.param(room(staff_cells=[[2, 1], [3, 1], [4, 1]]), "next to a tap", id="no-tap-beside"),
    pytest.param(room(staff_facing=None), "staff_facing", id="no-facing"),
    pytest.param(room(staff_facing="up"), "staff_facing", id="unknown-facing"),
    pytest.param(room(staff_cells=None), "staff_facing", id="facing-without-cells"),
])
def test_a_hall_with_bad_staff_cells_is_refused(data: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_world(data)


def test_staff_cells_that_cut_one_place_off_from_another_are_refused() -> None:
    with pytest.raises(ValueError, match="cut"):
        create_world(tiny_hall([3, 1]))


def test_the_same_hall_opens_once_the_cells_cut_nothing_off() -> None:
    assert create_world(tiny_hall([1, 1]))["map"]["objects"][-1]["staff_cells"] == [[2, 1]]


def test_off_limits_lists_every_staff_cell_to_a_guest() -> None:
    world = hall_with(guest("ada", 1, 4))
    assert sorted(off_limits(world["map"], world["actors"][0])) == [(2, 1), (3, 1), (4, 1), (5, 1)]


def test_a_guest_sent_to_explore_never_heads_for_the_staff_cells() -> None:
    world = hall_with(guest("ada", 2, 2))
    ada = world["actors"][0]
    # The staff cells are the only cells Ada has not seen: nothing else is left to find.
    ada["knowledge"]["cells"] = [[x, y] for x in range(world["map"]["width"]) for y in range(world["map"]["height"])
                                 if [x, y] not in CELLS]
    assert start_action(world, "ada", {"id": "inspect", "verb": "inspect", "target_id": None})["accepted"]
    assert ada["_spot"] not in CELLS


def test_a_walker_cannot_push_an_idle_guest_onto_a_staff_cell() -> None:
    # Ada's only free neighbour is (2, 1), a staff cell: Bob, walking into her cell, must not send her there.
    world = hall_with(guest("ada", 2, 2), guest("dan", 1, 2), guest("bob", 2, 3))
    assert start_action(world, "bob", {"id": "beer", "verb": "take_beer", "target_id": "tap"})["accepted"]
    bob = next(item for item in world["actors"] if item["id"] == "bob")
    bob.update(path=[[2, 2]], status="walking")
    step_world(world, 0.4)
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    assert (ada["x"], ada["y"], ada["action"]) == (2, 2, None)


@pytest.mark.parametrize("cell", [
    pytest.param(cell, id=f"{cell[0]}-{cell[1]}") for cell in CELLS])
def test_the_operator_cannot_block_or_clear_a_cell_behind_the_bar(cell: list[int]) -> None:
    world = hall_with()
    with pytest.raises(ValueError, match="behind the bar"):
        toggle_block(world, LAYOUT["blocked"], {"x": cell[0], "y": cell[1], "blocked": True})
