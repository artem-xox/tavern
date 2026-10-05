"""When a guest takes stock: a budget per guest, and only events that change what they want."""

from typing import Any

import pytest

from tavern.hall.memory import record_event
from tavern.hall.world import create_world
from tavern.mind.intentions import IntentionRules, intention_due, intention_requests
from tavern.social.thoughts import think

RULES = IntentionRules(interval=180.0, min_gap=3.0, budget=2)
HALL = {"width": 10, "height": 6, "blocked": [], "objects": [
    {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 5, "interaction_spots": [[0, 4]]}],
    "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 5, "y": 2}]}


def stocked(time: float = 20.0) -> dict[str, Any]:
    """A hall where both guests took stock at 10 s."""
    world = create_world(HALL)
    for guest in world["actors"]:
        guest["intention"] = {"thought": "Hm.", "intention": "Stay.", "goal": None, "written_at": 10.0,
                              "trigger": {"kind": "arrival", "text": "Came in", "time": 10.0}}
    world["time"] = time
    return world


def ada(world: dict[str, Any]) -> dict[str, Any]:
    """Ada."""
    return world["actors"][0]


def asked(world: dict[str, Any], made: dict[str, int]) -> list[str]:
    """Guests whose mind is asked now."""
    return [actor_id for actor_id, _ in intention_requests(world, (), {}, RULES, made)]


@pytest.mark.parametrize("made, expected", [
    pytest.param({}, ["ada"], id="none-asked-yet"),
    pytest.param({"ada": 1}, ["ada"], id="one-left"),
    pytest.param({"ada": 2}, [], id="budget-spent"),
    pytest.param({"ada": 5}, [], id="over-budget"),
    pytest.param({"bea": 2}, ["ada"], id="another-guests-budget"),
])
def test_a_guest_who_has_spent_their_budget_is_not_asked_again(made: dict[str, int], expected: list[str]) -> None:
    world = stocked()
    record_event(world, ada(world), "interrupted", "Ada: interrupted")
    assert asked(world, made) == expected


@pytest.mark.parametrize("trigger", [
    pytest.param(lambda world: world.update(closes_at=15.0), id="closing-time"),
    pytest.param(lambda world: ada(world).update(intention=None), id="arrival"),
])
def test_arrival_and_closing_are_asked_whatever_the_budget(trigger: Any) -> None:
    world = stocked()
    trigger(world)
    assert "ada" in asked(world, {"ada": 99})


def test_a_budget_is_not_negative() -> None:
    with pytest.raises(ValueError):
        IntentionRules(interval=180.0, min_gap=3.0, budget=-1)


@pytest.mark.parametrize("kind, expected", [
    pytest.param("conversation", None, id="a-scene-ending-alone"),
    pytest.param("left_conversation", None, id="leaving-a-scene-alone"),
    pytest.param("goal_done", "goal", id="a-goal-reached"),
    pytest.param("goal_failed", "goal", id="a-goal-lost"),
    pytest.param("goal_expired", "goal", id="a-goal-lapsed"),
])
def test_only_events_that_change_what_a_guest_wants_make_them_take_stock(kind: str, expected: str | None) -> None:
    world = stocked()
    record_event(world, ada(world), kind, f"Ada: {kind}")
    trigger = intention_due(world, ada(world), RULES)
    assert (trigger and trigger["kind"]) == expected


@pytest.mark.parametrize("thought", ["insulted", "shoved", "attacked", "quarrel", "seat_taken"])
def test_a_wrong_done_to_a_guest_makes_them_take_stock(thought: str) -> None:
    world = stocked()
    think(ada(world), thought, 15.0, f"{thought} by Bea", f"{thought} event", about=world["actors"][1])
    trigger = intention_due(world, ada(world), RULES)
    assert trigger is not None and trigger["kind"] == thought
