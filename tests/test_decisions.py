"""Who asks for a decision when, and how an answer reaches the world."""

from collections.abc import Callable, Collection, Mapping
from typing import Any

import pytest

from tavern.evening.decisions import apply_decision, decision_requests
from tavern.hall.world import create_world, start_action, step_world


def room() -> dict[str, Any]:
    """Build a 8×5 room with one two-chair table, a tap, and two visitors."""
    def chair(side: str, x: int) -> dict[str, Any]:
        return {"id": f"table-{side}", "kind": "chair", "name": f"Table · {side}", "x": x, "y": 2,
                "walkable": True, "table_id": "table", "interaction_spots": [[x, 2]]}
    return {"width": 8, "height": 5, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2}, chair("west", 2), chair("east", 4),
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 7, "y": 0, "interaction_spots": [[6, 0]], "stock": 3},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 4}, {"id": "bea", "name": "Bea", "x": 5, "y": 4}]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def busy(world: dict[str, Any]) -> None:
    """Send Ada to fetch a beer."""
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]


def chatting(world: dict[str, Any]) -> None:
    """Seat both visitors at the table, then let Bea start talking to Ada."""
    for actor_id, seat in (("ada", "table-west"), ("bea", "table-east")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    for _ in range(200):
        step_world(world, 0.1)
    assert start_action(world, "bea", command("talk", "ada"))["accepted"]


@pytest.mark.parametrize("prepare, pending, rested, expected", [
    pytest.param(None, [], {}, ["ada", "bea"], id="everyone-free"),
    pytest.param(lambda world: world["actors"].clear(), [], {}, [], id="empty-room"),
    pytest.param(None, ["ada"], {}, ["bea"], id="single-pending"),
    pytest.param(None, ["ada", "ada"], {}, ["bea"], id="duplicate-pending"),
    pytest.param(None, [], {"bea": 5.0}, ["ada"], id="still-resting-after-an-answer"),
    pytest.param(busy, [], {}, ["bea"], id="busy-with-an-action"),
    pytest.param(chatting, [], {}, [], id="partner-is-not-pulled-from-a-chat"),
])
def test_free_visitors_ask_one_at_a_time(
        prepare: Callable[[dict[str, Any]], None] | None, pending: Collection[str],
        rested: Mapping[str, float], expected: list[str]) -> None:
    world = create_world(room())
    if prepare is not None:
        prepare(world)
    requests = decision_requests(world, pending, rested)
    assert [(actor_id, observation["actor"]["id"]) for actor_id, observation in requests] == [
        (actor_id, actor_id) for actor_id in expected]


def answer(action: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    """Return a ready decision for the action."""
    return lambda: {"action": action, "source": "jev", "scores": {action["id"]: 1.0}, "error": None}


def failure() -> dict[str, Any]:
    """Stand in for a decision request that failed."""
    raise ValueError("Observation is malformed")


@pytest.mark.parametrize("outcome, verb, error, control", [
    pytest.param(answer(command("wait")), "wait", None, [], id="accepted-action-starts"),
    pytest.param(answer(command("take_beer", "missing")), None, None, ["Ada: Target no longer exists"],
                 id="refused-action-is-logged"),
    pytest.param(failure, None, "Observation is malformed", ["Decision failed for Ada"],
                 id="failed-request-is-shown"),
    pytest.param(lambda: {"source": "jev"}, None, "'scores'", ["Decision failed for Ada"],
                 id="malformed-decision"),
])
def test_answer_starts_its_action_or_is_logged(
        outcome: Callable[[], dict[str, Any]], verb: str | None, error: str | None, control: list[str]) -> None:
    world = create_world(room())
    ada = world["actors"][0]
    rest_until = apply_decision(world, ada, outcome)
    logged = [event["message"] for event in world["events"] if event["type"] == "control"]
    assert ((ada["action"] or {}).get("verb"), ada["decision"]["error"], logged, rest_until) == (
        verb, error, control, world["time"] + 1.0)
