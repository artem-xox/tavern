"""The walk_to verb: the player's walk to a spot on the floor, where the walker ends idle and standing."""

import json
from collections.abc import Callable
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import create_world, start_action
from social_hall import actor, advance
from test_staff import guest, tiny_hall


def corridor() -> dict[str, Any]:
    """The 7×3 corridor of `tiny_hall`, (1, 1) to (5, 1), with Ada at (3, 1): the bar's staff cell (2, 1) cuts (1, 1) off."""
    return create_world({**tiny_hall([1, 1]), "actors": [guest("ada", 3, 1)]})


def walk_to(cell: Any) -> dict[str, Any]:
    """Build a walk_to action for a cell, which may be malformed."""
    name = f"{cell[0]},{cell[1]}" if isinstance(cell, list) and len(cell) == 2 else "x"
    return {"id": f"walk_to:{name}", "verb": "walk_to", "target_id": None, "cell": cell}


@pytest.mark.parametrize("cell", [
    pytest.param([4, 1], id="next-to-the-walker"),
    pytest.param([5, 1], id="across-the-hall"),
    pytest.param([3, 1], id="the-walkers-own-cell"),
])
def test_the_walker_ends_idle_on_the_cell_they_walked_to(cell: list[int]) -> None:
    world = corridor()
    assert start_action(world, "ada", walk_to(cell))["accepted"]
    advance(world, 6)
    ada = actor(world, "ada")
    assert ([ada["x"], ada["y"]], ada["status"], ada["action"], ada["seat_id"]) == (cell, "idle", None, None)


@pytest.mark.parametrize("cell, reason", [
    pytest.param([0, 0], "Nobody can stand there", id="a-wall"),
    pytest.param([2, 1], "Nobody can stand there", id="behind-the-bar"),
    pytest.param([7, 1], "Nobody can stand there", id="outside-the-hall"),
    pytest.param([-1, 1], "Nobody can stand there", id="before-the-hall"),
    pytest.param([1, 1], "No way there", id="cut-off"),
    pytest.param([4], "Choose a cell to walk to", id="malformed-cell"),
    pytest.param([1.5, 1], "Choose a cell to walk to", id="a-fraction"),
    pytest.param(None, "Choose a cell to walk to", id="no-cell"),
])
def test_a_cell_nobody_can_stand_on_or_reach_is_refused_with_a_reason(cell: Any, reason: str) -> None:
    world = corridor()
    assert start_action(world, "ada", walk_to(cell)) == {"accepted": False, "reason": reason}


def test_a_cell_where_another_guest_stands_is_refused() -> None:
    world = create_world({**tiny_hall([1, 1]), "actors": [guest("ada", 3, 1), guest("bea", 5, 1)]})
    assert start_action(world, "ada", walk_to([5, 1])) == {"accepted": False, "reason": "Nobody can stand there"}


def walking() -> dict[str, Any]:
    """Ada is on her way to (5, 1)."""
    world = corridor()
    assert start_action(world, "ada", walk_to([5, 1]))["accepted"]
    advance(world, 0.5)
    return world


def saved(world: dict[str, Any]) -> str:
    """Encode a world as a save."""
    return json.dumps(world)


def set_cell(cell: Any) -> Callable[[dict[str, Any]], None]:
    """Change the cell Ada's action names."""
    return lambda world: actor(world, "ada")["action"].update(cell=cell)


def drop_cell(world: dict[str, Any]) -> None:
    """Take the cell off Ada's action."""
    del actor(world, "ada")["action"]["cell"]


def give_cell_to_a_wait(world: dict[str, Any]) -> None:
    """Make Ada's action a plain wait that names a cell."""
    actor(world, "ada")["action"].update(verb="wait", id="wait")


def test_a_walk_in_progress_survives_a_save() -> None:
    world = walking()
    assert parse_world(saved(world))["actors"][0]["action"]["cell"] == [5, 1]


@pytest.mark.parametrize("change", [
    pytest.param(set_cell([7, 1]), id="a-cell-off-the-map"),
    pytest.param(set_cell("5,1"), id="a-cell-that-is-not-a-pair"),
    pytest.param(drop_cell, id="a-walk-without-its-cell"),
    pytest.param(give_cell_to_a_wait, id="a-cell-on-a-verb-that-walks-to-none"),
])
def test_a_save_with_a_bad_cell_in_an_action_is_rejected(change: Callable[[dict[str, Any]], None]) -> None:
    world = walking()
    change(world)
    with pytest.raises(ValueError, match="Invalid saved action"):
        parse_world(saved(world))
