"""Scenario evenings in saves and sessions: version 2 saves, refused old saves, reset and seeds."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tavern.persistence import load_world, save_world
from tavern.scenario import Scenario, open_evening, parse_scenario
from tavern.world import step_world


def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a door in the bottom wall and a tap."""
    return {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5},
    ]}


def plan(*arrivals: float, seed: int | None = None) -> Scenario:
    """Expect one guest per arrival time, named ada, bea, cid… in order, before closing at 300 s."""
    guests = [{"id": name, "name": name.title(), "color": "#a08060", "sprite": "visitor", "traits": {},
               "arrives_at": time} for name, time in zip(("ada", "bea", "cid", "dan"), arrivals)]
    data = {"guests": guests, "arrival": {"needs": {"thirst": [40, 80]}}, "closes_at": 300}
    return parse_scenario({**data, **({} if seed is None else {"seed": seed})})


def walked_in(*arrivals: float) -> dict[str, Any]:
    """Open the hall for the given arrivals and let ten seconds pass."""
    world = open_evening(hall(), plan(*arrivals), seed=3)
    for _ in range(20):
        step_world(world, 0.5)
    return world


@pytest.mark.parametrize("arrivals", [
    pytest.param((0,), id="empty-expected-list"),
    pytest.param((0, 60), id="single-guest-expected"),
    pytest.param((0, 60, 60), id="duplicate-arrival-times"),
])
def test_scenario_evening_survives_save_and_load(tmp_path: Path, arrivals: tuple[float, ...]) -> None:
    world = walked_in(*arrivals)
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def expected_guest(world: dict[str, Any]) -> dict[str, Any]:
    """Return the first guest still on the way."""
    return world["expected"][0]


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=1), id="version-1-save"),
    pytest.param(lambda world: world.update(expected={}), id="malformed-expected"),
    pytest.param(lambda world: world.update(closes_at="late"), id="malformed-closing-time"),
    pytest.param(lambda world: expected_guest(world).pop("needs"), id="expected-without-needs"),
    pytest.param(lambda world: expected_guest(world)["needs"].update(thirst=150), id="need-out-of-range"),
    pytest.param(lambda world: expected_guest(world)["needs"].update(courage=10), id="unknown-need"),
    pytest.param(lambda world: expected_guest(world).update(sprite=""), id="expected-without-sprite"),
    pytest.param(lambda world: expected_guest(world).update(id="ada"), id="duplicate-of-a-present-guest"),
    pytest.param(lambda world: world["expected"].reverse(), id="out-of-arrival-order"),
    pytest.param(lambda world: expected_guest(world).update(arrives_at=400), id="arrives-after-closing"),
    pytest.param(lambda world: world["actors"][0].pop("sprite"), id="present-guest-without-sprite"),
])
def test_old_or_corrupt_evening_saves_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = walked_in(0, 60, 120)
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
