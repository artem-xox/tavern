"""The barkeep greets: he steps across to a guest at the bar and opens the talk, unless he has reason not to."""

from collections.abc import Callable
import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.state import World
from tavern.social.scenes import conversation_of, start_conversation
from staff_hall import HOB, advance, events, hob_of, opened, order_beer, person, place

SPOT = (3, 3)


def at_the_bar(world: dict[str, Any], actor_id: str = "ada", spot: tuple[int, int] = SPOT) -> None:
    """A guest leans on the bar, at ease: no need presses on them."""
    place(world, actor_id, spot)
    person(world, actor_id)["needs"] = {need: 10.0 for need in person(world, actor_id)["needs"]}


def heard_from(world: dict[str, Any], actor_id: str, ago: float) -> None:
    """Hob heard a guest speak `ago` seconds back."""
    hob_of(world)["heard"].append({"time": world["time"] - ago, "scene_id": "conversation-9", "speaker_id": actor_id,
                                   "speaker": actor_id.capitalize(), "line": "Evening.", "act": "greet"})


def greetings(world: dict[str, Any]) -> list[str]:
    """The conversations Hob has started, oldest first."""
    return [message for message in events(world, "conversation_started") if message.startswith("Hob ")]


def test_the_barkeep_steps_across_to_a_guest_at_the_bar_and_greets_them() -> None:
    world = opened(HOB)
    at_the_bar(world)
    advance(world, 3.5)
    assert (greetings(world), (hob_of(world)["x"], hob_of(world)["y"])) == (["Hob started talking to Ada"], (3, 1))


def test_he_stands_across_from_a_guest_wherever_they_lean() -> None:
    world = opened(HOB)
    at_the_bar(world, spot=(4, 3))
    advance(world, 3.5)
    assert ((hob_of(world)["x"], hob_of(world)["y"]), len(greetings(world))) == ((4, 1), 1)


def test_he_does_not_greet_the_same_guest_again_within_the_gap_and_does_afterwards() -> None:
    world = opened(HOB)
    at_the_bar(world)
    heard_from(world, "ada", ago=1.0)
    advance(world, 30.0)
    quiet = greetings(world)
    person(world, "ada")["needs"] = {need: 10.0 for need in person(world, "ada")["needs"]}
    advance(world, 40.0)
    assert (quiet, greetings(world)) == ([], ["Hob started talking to Ada"])


def test_a_new_order_breaks_off_his_chat() -> None:
    world = opened(HOB)
    at_the_bar(world)
    advance(world, 3.0)
    scene = conversation_of(world, "hob")
    assert scene is not None
    order_beer(world, "bea")
    advance(world, 0.3)
    assert (conversation_of(world, "hob"), hob_of(world)["action"]["verb"]) == (None, "pour_beer")


@pytest.mark.parametrize("damage", [
    pytest.param(lambda rules: rules.update(bartending={}), id="no-gap"),
    pytest.param(lambda rules: rules["bartending"].update(chat_gap=0.0), id="gap-of-zero"),
    pytest.param(lambda rules: rules["bartending"].update(chat_gap=-5.0), id="negative-gap"),
    pytest.param(lambda rules: rules["bartending"].update(chat_gap="a minute"), id="gap-not-a-number"),
    pytest.param(lambda rules: rules["bartending"].update(extra=1), id="unknown-rule"),
])
def test_a_save_with_a_broken_chat_gap_is_refused(damage: Callable[[dict[str, Any]], None]) -> None:
    world = opened(HOB)
    damage(world["rules"])
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))


def closed(world: World) -> None:
    """Closing time has come."""
    world["closes_at"] = world["time"]


def pressed(world: World) -> None:
    """Ada is parched: she has no mind to chat."""
    person(world, "ada")["needs"]["thirst"] = 90.0


def chatting_already(world: World) -> None:
    """Ada and Bea are in a conversation of their own at the bar, and long for company still."""
    at_the_bar(world, "bea", (5, 3))
    for actor_id in ("ada", "bea"):
        person(world, actor_id)["needs"]["social"] = 100.0
    start_conversation(world, person(world, "ada"), person(world, "bea"))


def off_the_bar(world: World) -> None:
    """Ada stands beside the bar, not on one of its spots."""
    place(world, "ada", (2, 3))


@pytest.mark.parametrize("change", [
    pytest.param(closed, id="after-closing"),
    pytest.param(pressed, id="guest-pressed-by-a-need"),
    pytest.param(chatting_already, id="guests-in-a-scene-of-their-own"),
    pytest.param(off_the_bar, id="guest-not-at-the-bar"),
])
def test_he_does_not_greet_when_he_has_reason_not_to(change: Callable[[World], None]) -> None:
    world = opened(HOB)
    at_the_bar(world)
    change(world)
    advance(world, 6.0)
    assert greetings(world) == []
