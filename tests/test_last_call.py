"""The barkeep's call, a minute before the inn closes: said aloud once, heard by all, and it stops new orders but nothing else."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.hearing import EVENT_SOUNDS
from tavern.evening.scenario import parse_scenario
from tavern.hall.closing import LAST_CALL_LINE, call_last_orders, closing_called
from tavern.hall.world import create_world, start_action
from tavern.mind.agents import build_candidates
from staff_hall import HOB, advance, events, hob_of, opened, order_beer, person, plan, sees

CALL = 60.0
CLOSE = 100.0


def called_evening(*staff: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """The repository's hall with a call at 60 s and the close at 100 s."""
    return opened(*staff, closes_at=CLOSE, last_call_at=CALL, **fields)


def last_calls(world: dict[str, Any]) -> list[dict[str, Any]]:
    """The logged calls, oldest first."""
    return [item for item in world["events"] if item["type"] == "last_call"]


@pytest.mark.parametrize("seconds, expected", [
    pytest.param(59.5, 0, id="just-before"),
    pytest.param(60.5, 1, id="on-the-tick-after"),
    pytest.param(99.0, 1, id="called-only-once"),
])
def test_the_barkeep_calls_closing_time_once(seconds: float, expected: int) -> None:
    world = called_evening(HOB)
    advance(world, seconds)
    assert len(last_calls(world)) == expected


def test_the_call_is_the_barkeeps_own_words() -> None:
    world = called_evening(HOB)
    advance(world, 61)
    (call,) = last_calls(world)
    assert (call["actor_id"], call["line"], call["message"]) == ("hob", LAST_CALL_LINE, f'Hob called out: "{LAST_CALL_LINE}"')
    assert any(item["type"] == "last_call" for item in hob_of(world)["memory"])


def test_without_a_barkeep_the_innkeeper_calls() -> None:
    world = called_evening()
    advance(world, 61)
    (call,) = last_calls(world)
    assert (call["actor_id"], call["message"]) == (None, f'The innkeeper called out: "{LAST_CALL_LINE}"')


def test_an_evening_without_a_call_has_none() -> None:
    world = opened(HOB, closes_at=CLOSE)
    advance(world, 120)
    assert last_calls(world) == [] and world["last_call_at"] is None and not closing_called(world)


def test_the_call_is_a_loud_sound_from_the_barkeep() -> None:
    world = called_evening(HOB)
    world["time"] = CALL
    call_last_orders(world, CALL - 0.5)
    (sound,) = [item for item in world["stimuli"] if item["event"] == "last_call"]
    assert (sound["kind"], sound["sources"], sound["loudness"], sound["cell"]) == (
        "closing_call", ["hob"], 1.0, [hob_of(world)["x"], hob_of(world)["y"]])
    assert EVENT_SOUNDS["last_call"].loudness >= 0.5


def test_guests_hear_how_long_ago_the_call_was() -> None:
    world = called_evening(HOB)
    advance(world, 59)
    before = sees(world, "ada")["called_closing"]
    advance(world, 4)
    after = sees(world, "ada")["called_closing"]
    assert before is None and after == pytest.approx(3.0, abs=0.11)


def ids(world: dict[str, Any], guest_id: str = "ada") -> list[str]:
    """The IDs of the options a guest has, those grouped into a family of wishes included."""
    return [item["id"] for action in build_candidates(sees(world, guest_id)) for item in action.get("members", [action])]


def test_before_the_call_a_guest_may_fetch_a_beer() -> None:
    world = called_evening(HOB)
    advance(world, 30)
    assert "take_beer:tap" in ids(world)


def test_after_the_call_nobody_is_offered_a_beer_from_the_tap_but_they_may_still_leave() -> None:
    world = called_evening(HOB)
    advance(world, 62)
    options = ids(world)
    assert "take_beer:tap" not in options and "leave:door" in options


def test_after_the_call_a_new_order_is_refused_with_the_reason() -> None:
    world = called_evening(HOB)
    advance(world, 62)
    assert start_action(world, "ada", {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}) == {
        "accepted": False, "reason": "The bar has stopped serving"}


def test_an_order_made_before_the_call_is_still_poured() -> None:
    world = called_evening(HOB)
    advance(world, 58)
    order_beer(world, "ada")
    advance(world, 8)
    assert events(world, "served") == ["Hob poured Ada a mug of ale"] and person(world, "ada")["inventory"]["beer"] == 1


def test_after_the_call_a_tired_seated_guest_is_not_offered_a_nap() -> None:
    world = called_evening(HOB)
    advance(world, 30)
    chair = next(item["id"] for item in world["map"]["objects"] if item["kind"] == "chair")
    assert start_action(world, "ada", {"id": "sit", "verb": "sit", "target_id": chair})["accepted"]
    advance(world, 10)
    person(world, "ada")["needs"]["fatigue"] = 90
    assert "doze" in ids(world)
    advance(world, 22)
    assert "doze" not in ids(world)


def test_a_save_made_after_the_call_reloads() -> None:
    world = called_evening(HOB)
    advance(world, 70)
    reloaded = parse_world(json.dumps(world))
    assert reloaded["last_call_at"] == CALL and len(last_calls(reloaded)) == 1


def with_last_call(**fields: Any) -> dict[str, Any]:
    """A scenario file's text with the given fields."""
    return plan(**fields)


@pytest.mark.parametrize("value, closes_at", [
    pytest.param(0, 300, id="at-opening"),
    pytest.param(-5, 300, id="before-opening"),
    pytest.param(300, 300, id="at-closing"),
    pytest.param(400, 300, id="after-closing"),
    pytest.param("late", 300, id="text"),
    pytest.param(True, 300, id="boolean"),
])
def test_a_scenario_call_outside_the_evening_fails_loudly(value: Any, closes_at: float) -> None:
    with pytest.raises(ValueError, match="last_call_at"):
        parse_scenario(with_last_call(closes_at=closes_at, last_call_at=value))


@pytest.mark.parametrize("change", [
    pytest.param(lambda world: world.update(last_call_at="late"), id="text"),
    pytest.param(lambda world: world.update(last_call_at=0), id="at-opening"),
    pytest.param(lambda world: world.update(last_call_at=world["closes_at"]), id="at-closing"),
    pytest.param(lambda world: world.update(closes_at=None), id="call-without-a-closing-time"),
    pytest.param(lambda world: world.pop("last_call_at"), id="missing"),
    pytest.param(lambda world: world.update(schema_version=15), id="version-15-save"),
])
def test_a_save_with_a_malformed_call_is_refused(change: Any) -> None:
    world = called_evening(HOB)
    change(world)
    with pytest.raises(ValueError):
        parse_world(json.dumps(world))


def test_a_hall_without_a_scenario_has_no_call() -> None:
    assert create_world({"width": 5, "height": 5, "blocked": [], "objects": []})["last_call_at"] is None
