"""A guest walked up to on their feet waits for the walker instead of deciding, and turns to face them."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.body.expression import facing_toward
from tavern.evening.decisions import free_to_decide
from tavern.hall.world import start_action
from tavern.social.walk_ups import walker_toward
from social_hall import actor, advance, command
from test_approach import approach, evening


def walking_up_to_dan() -> dict[str, Any]:
    """Ada has set out to walk up to Dan, who stands by the fire."""
    world = evening({})
    assert approach(world, "ada", "dan")["accepted"]
    advance(world, 0.5)
    return world


def ada_gives_up(world: dict[str, Any]) -> None:
    """Ada turns to fetch a beer instead."""
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]


def ada_is_held_up(world: dict[str, Any]) -> None:
    """Ada has waited on a blocked route for as long as it shows."""
    actor(world, "ada").update(status="waiting", _blocked_for=world["rules"]["long_wait"])


def dan_needs_the_wc(world: dict[str, Any]) -> None:
    """A need presses on Dan."""
    actor(world, "dan")["needs"]["bladder"] = 90.0


def dan_walks_off(world: dict[str, Any]) -> None:
    """Dan sets off on his own."""
    actor(world, "dan").update(status="walking", path=[[9, 5]])


@pytest.mark.parametrize("change, expected", [
    pytest.param(None, "ada", id="a-walker-on-their-way"),
    pytest.param(ada_gives_up, None, id="the-walker-gives-up"),
    pytest.param(ada_is_held_up, None, id="the-walker-is-held-up-for-long"),
    pytest.param(dan_needs_the_wc, None, id="a-need-presses-on-the-one-walked-up-to"),
    pytest.param(dan_walks_off, None, id="the-one-walked-up-to-walks-off"),
])
def test_the_guest_walked_up_to_knows_their_walker(change: Callable[[dict[str, Any]], None] | None,
                                                   expected: str | None) -> None:
    world = walking_up_to_dan()
    if change:
        change(world)
    walker = walker_toward(world, "dan")
    assert (walker["id"] if walker else None) == expected


def test_nobody_is_walking_up_to_a_guest_nobody_approached() -> None:
    assert walker_toward(evening({}), "dan") is None


def test_a_guest_at_a_table_has_no_walker_to_wait_for() -> None:
    world = evening({"cid": "fw"})
    assert approach(world, "ada", "cid")["accepted"]
    advance(world, 0.5)
    assert walker_toward(world, "cid") is None


@pytest.mark.parametrize("change, free", [
    pytest.param(None, False, id="while-the-walker-comes"),
    pytest.param(ada_gives_up, True, id="once-the-walker-gives-up"),
    pytest.param(dan_needs_the_wc, True, id="once-a-need-presses"),
])
def test_a_guest_walked_up_to_asks_for_no_decision(change: Callable[[dict[str, Any]], None] | None,
                                                   free: bool) -> None:
    world = walking_up_to_dan()
    if change:
        change(world)
    assert free_to_decide(world, actor(world, "dan")) is free


def test_a_guest_walked_up_to_turns_to_face_the_walker() -> None:
    world = walking_up_to_dan()
    ada, dan = actor(world, "ada"), actor(world, "dan")
    assert dan["facing"] == facing_toward((dan["x"], dan["y"]), (ada["x"], ada["y"]))
