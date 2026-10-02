"""Closing time: once the inn has closed, every guest's only option is to go home, and they know why."""

import asyncio
from random import Random
from typing import Any, Callable

import pytest

from tavern.agents import build_candidates, choose_action
from tavern.briefing import brief
from tavern.scenario import open_evening, parse_scenario
from tavern.world import create_world, observe_actor, observe_people, start_action, step_world


def hall() -> dict[str, Any]:
    """Build a 10×7 hall: a two-spot door in the bottom wall, a tap, and a two-seat table."""
    def chair(side: str, x: int) -> dict[str, Any]:
        return {"id": f"chair-{side}", "kind": "chair", "name": f"Chair {side}", "x": x, "y": 2,
                "walkable": True, "table_id": "table", "interaction_spots": [[x, 2]]}
    return {"width": 10, "height": 7, "blocked": [[x, 6] for x in range(10) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 6, "interaction_spots": [[5, 5], [4, 5]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5},
        {"id": "table", "kind": "table", "name": "Table", "x": 5, "y": 2}, chair("west", 4), chair("east", 6),
    ]}


def evening() -> dict[str, Any]:
    """Open the hall for Ada and Bea, who arrive together; the inn closes after 60 seconds."""
    guests = [{"id": name, "name": name.title(), "color": "#a08060", "sprite": "visitor", "traits": {},
               "arrives_at": 0} for name in ("ada", "bea")]
    return open_evening(hall(), parse_scenario(
        {"guests": guests, "arrival": {"needs": {}}, "closes_at": 60}), seed=1)


def without_scenario() -> dict[str, Any]:
    """Build the same hall with Ada already inside and no closing time."""
    return create_world({**hall(), "actors": [{"id": "ada", "name": "Ada", "x": 5, "y": 5}]})


def advance(world: dict[str, Any], seconds: float) -> None:
    """Step the world in half-second ticks without decisions."""
    for _ in range(round(seconds / 0.5)):
        step_world(world, 0.5)


def look(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Observe a visitor the way the runtime does before a decision."""
    return {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}


@pytest.mark.parametrize("build, seconds, closed", [
    pytest.param(evening, 59.5, False, id="still-open"),
    pytest.param(evening, 60.0, True, id="closing-time"),
    pytest.param(evening, 90.0, True, id="after-closing"),
    pytest.param(without_scenario, 1000.0, False, id="no-closing-time"),
])
def test_guests_see_when_the_inn_has_closed(build: Callable[[], dict[str, Any]], seconds: float,
                                             closed: bool) -> None:
    world = build()
    advance(world, seconds)
    assert look(world, "ada")["closed"] is closed


@pytest.mark.parametrize("door_busy, expected", [
    pytest.param(False, ["leave:door"], id="door-free"),
    pytest.param(True, ["wait"], id="door-busy-wait-a-turn"),
])
def test_after_closing_the_only_option_is_to_go_home(door_busy: bool, expected: list[str]) -> None:
    world = evening()
    advance(world, 60)
    if door_busy:
        assert start_action(world, "bea", {"id": "leave", "verb": "leave", "target_id": "door"})["accepted"]
    assert [action["id"] for action in build_candidates(look(world, "ada"))] == expected


def test_a_newcomer_goes_home_at_closing_however_little_they_want_to() -> None:
    world = evening()
    advance(world, 60)
    decision = asyncio.run(choose_action(look(world, "ada"), {"temperature": 0.25}, Random(0)))
    assert decision["action"]["id"] == "leave:door"


@pytest.mark.parametrize("seconds, closing", [
    pytest.param(30.0, False, id="open"),
    pytest.param(60.0, True, id="closed"),
])
def test_briefing_says_the_inn_is_closing(seconds: float, closing: bool) -> None:
    world = evening()
    advance(world, seconds)
    observation = look(world, "ada")
    assert ("The inn has closed for the night" in brief(observation, [])["situation"]) is closing


def test_closing_time_is_called_once_in_the_event_log() -> None:
    world = evening()
    advance(world, 120)
    assert [event["time"] for event in world["events"] if event["type"] == "closing"] == [60.0]


def test_malformed_closing_flag_is_rejected() -> None:
    observation = {**look(evening(), "ada"), "closed": "yes"}
    with pytest.raises(ValueError):
        build_candidates(observation)
