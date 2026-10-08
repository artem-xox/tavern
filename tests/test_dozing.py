"""Dozing: what counts as asleep, who may nod off, and how a nap starts and ends."""

from typing import Any

import pytest

from tavern.body.dozing import asleep
from tavern.body.hearing import EVENT_SOUNDS, Sound, emit
from tavern.hall.world import start_action
from tavern.mind.intentions import IntentionRules, intention_due
from test_attention import actor, events, guest, hall, start, ticks


@pytest.mark.parametrize("action, expected", [
    pytest.param(None, False, id="no-action"),
    pytest.param({"id": "sit", "verb": "sit", "target_id": "west"}, False, id="sitting"),
    pytest.param({"id": "drink", "verb": "drink", "target_id": None}, False, id="drinking"),
    pytest.param({"id": "doze", "verb": "doze", "target_id": None}, True, id="dozing"),
])
def test_only_a_nap_is_asleep(action: dict[str, Any] | None, expected: bool) -> None:
    assert asleep({"action": action}) is expected


def asleep_at_the_table(**traits: float) -> dict[str, Any]:
    """The real hall with Ada in chair-4, asleep, and Bea standing by."""
    world = hall(guest("ada", (5, 6), traits=traits), guest("bea", (8, 7)))
    start(world, "sit", "chair-4")
    assert start_action(world, "ada", {"id": "doze", "verb": "doze", "target_id": None})["accepted"]
    return world


def sound(world: dict[str, Any], heard: Sound, cell: tuple[int, int]) -> None:
    """Bea makes a sound where she stands."""
    emit(world, heard, ["bea"], cell, [], f"Bea made {heard.noun}", None)


LOUD = [pytest.param(EVENT_SOUNDS[kind], (8, 7), id=kind) for kind in ("quarrel", "shove", "fight_started", "closing")]


@pytest.mark.parametrize("heard, cell", [
    *LOUD,
    pytest.param(EVENT_SOUNDS["quarrel"], (19, 13), id="a-quarrel-across-the-hall"),
    pytest.param(EVENT_SOUNDS["quarrel"], (12, 3), id="a-quarrel-behind-a-wall"),
])
@pytest.mark.parametrize("curiosity", [pytest.param(0.0, id="incurious"), pytest.param(1.0, id="curious")])
def test_a_loud_sound_always_wakes_a_sleeper(heard: Sound, cell: tuple[int, int], curiosity: float) -> None:
    world = asleep_at_the_table(curiosity=curiosity)
    sound(world, heard, cell)
    ticks(world, 1)
    ada = actor(world, "ada")
    assert (ada["action"], ada["seat_id"], ada["emote"]["kind"], len(events(world, "woken")),
            events(world, "interrupted")) == (None, "chair-4", "alert", 1, [])
    assert events(world, "woken")[0].startswith(f"Ada woke with a start at {heard.noun}")


@pytest.mark.parametrize("heard", [
    pytest.param(Sound("chat", 0.25, 6.0, "a conversation"), id="a-chat"),
    pytest.param(Sound("thud", 0.25, 10.0, "darts thudding into the board"), id="darts"),
    pytest.param(EVENT_SOUNDS["arrival"], id="the-door"),
    pytest.param(EVENT_SOUNDS["dice_won"], id="a-cheer"),
    pytest.param(EVENT_SOUNDS["action_failed"], id="a-grumble"),
])
@pytest.mark.parametrize("curiosity", [pytest.param(0.0, id="incurious"), pytest.param(1.0, id="curious")])
def test_a_quiet_sound_does_not_even_turn_a_sleepers_head(heard: Sound, curiosity: float) -> None:
    world = asleep_at_the_table(curiosity=curiosity)
    sound(world, heard, (6, 6))
    ticks(world, 5)
    ada = actor(world, "ada")
    assert ((ada["action"] or {}).get("verb"), ada["gaze"], events(world, "woken")) == ("doze", None, [])


def test_a_sleeper_does_not_wake_to_their_own_noise() -> None:
    world = asleep_at_the_table()
    emit(world, EVENT_SOUNDS["quarrel"], ["ada"], (5, 6), [], "Ada snored fit to wake the dead", None)
    ticks(world, 1)
    assert (actor(world, "ada")["action"] or {}).get("verb") == "doze"


def test_a_nap_is_logged_when_it_starts_and_when_it_ends_by_itself() -> None:
    world = asleep_at_the_table()
    ticks(world, 410)
    assert (events(world, "dozed_off"), events(world, "woke_up"), events(world, "woken"),
            actor(world, "ada")["action"]) == (["Ada fell asleep at the table"], ["Ada woke up at the table"], [], None)


def test_a_wasted_guest_who_nods_off_is_logged_once() -> None:
    world = hall(guest("ada", (5, 6)))
    actor(world, "ada")["drunkenness"] = 0.9
    start(world, "sit", "chair-4")
    world["rules"]["drunkenness"]["doze_per_second"] = 1000.0
    ticks(world, 2)
    assert events(world, "dozed_off") == ["Ada fell asleep at the table"]


def test_nobody_nods_off_once_the_inn_has_closed() -> None:
    world = hall(guest("ada", (5, 6)))
    actor(world, "ada")["drunkenness"] = 0.9
    start(world, "sit", "chair-4")
    world["rules"]["drunkenness"]["doze_per_second"] = 1000.0
    world["closes_at"] = 0.05
    ticks(world, 3)
    assert events(world, "dozed_off") == []


def test_a_sleeper_takes_no_stock_until_they_are_woken() -> None:
    rules = IntentionRules(interval=180.0, min_gap=3.0)
    world = asleep_at_the_table()
    ada = actor(world, "ada")
    ada["intention"] = {"thought": "A long road.", "intention": "Sleep a bit.", "written_at": 0.0,
                        "trigger": {"kind": "arrival", "text": "Came in", "time": 0.0}}
    world["time"] = 500.0  # long past the interval
    asleep_due = intention_due(world, ada, rules)
    sound(world, EVENT_SOUNDS["quarrel"], (8, 7))
    ticks(world, 1)
    woken = intention_due(world, ada, rules)
    assert (asleep_due, woken["kind"] if woken else None) == (None, "woken")
