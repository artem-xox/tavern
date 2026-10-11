"""A visitor walks across corners: a diagonal step takes longer than a straight one, and a saved route may hold one."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import create_world, start_action, step_world


def hall(chair_cell: tuple[int, int]) -> dict[str, Any]:
    """Build an open floor with one chair, and Ada standing in the corner."""
    return {"width": 6, "height": 6, "tile_size": 32, "blocked": [], "objects": [
        {"id": "chair", "kind": "chair", "name": "Chair", "x": chair_cell[0] + 1, "y": chair_cell[1],
         "interaction_spots": [list(chair_cell)]}],
        "actors": [{"id": "ada", "name": "Ada", "x": 0, "y": 0}]}


def walking(chair_cell: tuple[int, int]) -> dict[str, Any]:
    """Ada, set off for the chair, and the world around her."""
    world = create_world(hall(chair_cell))
    assert start_action(world, "ada", {"id": "sit", "verb": "sit", "target_id": "chair"})["accepted"]
    return world


def after(world: dict[str, Any], seconds: float) -> tuple[int, int]:
    """Ada's cell once the world has run for some seconds in 0.1 s ticks."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)
    ada = world["actors"][0]
    return ada["x"], ada["y"]


@pytest.mark.parametrize("chair_cell, seconds, expected", [
    pytest.param((3, 0), 0.4, (1, 0), id="a-straight-step-takes-a-move-time"),
    pytest.param((3, 0), 1.1, (3, 0), id="three-straight-steps"),
    pytest.param((3, 3), 0.4, (0, 0), id="a-diagonal-step-is-not-done-in-a-move-time"),
    pytest.param((3, 3), 0.6, (1, 1), id="a-diagonal-step-takes-root-two-move-times"),
    pytest.param((3, 3), 1.6, (3, 3), id="three-diagonal-steps"),
])
def test_walking_takes_the_time_of_the_steps(chair_cell: tuple[int, int], seconds: float,
                                              expected: tuple[int, int]) -> None:
    assert after(walking(chair_cell), seconds) == expected


def test_a_route_with_diagonal_steps_survives_a_save() -> None:
    world = walking((3, 3))
    assert world["actors"][0]["path"] == [[1, 1], [2, 2], [3, 3]]
    assert parse_world(json.dumps(world)) == world


def test_a_saved_route_that_skips_a_cell_is_rejected() -> None:
    world = walking((3, 3))
    world["actors"][0]["path"] = [[2, 2], [3, 3]]
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))
