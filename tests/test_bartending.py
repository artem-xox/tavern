"""Bartending: guests order at the tap, the barkeep pours, and the tap stays self-service without him."""

from typing import Any

import pytest

from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import start_action
from tavern.mind.briefing import brief
from tavern.mind.options import option_text
from tavern.social.scenes import conversation_of, start_conversation
from staff_hall import (HOB, LAYOUT, TAKE_BEER, advance, events, hob_of, opened, order_beer, person, place, plan,
                        sees)


def beers(world: dict[str, Any], actor_id: str) -> int:
    """How many mugs a guest holds."""
    return person(world, actor_id)["inventory"]["beer"]


def stock(world: dict[str, Any]) -> int:
    """Servings left at the tap."""
    return next(item["stock"] for item in world["map"]["objects"] if item["id"] == "tap")


def test_the_barkeep_pours_and_the_guest_waits_for_the_mug() -> None:
    world = opened(HOB)
    order_beer(world, "ada")
    seconds = world["rules"]["durations"]["pour_beer"]
    advance(world, seconds - 0.5)
    waiting = (beers(world, "ada"), stock(world), person(world, "ada")["status"], hob_of(world)["action"]["verb"])
    advance(world, 1.5)
    served = (beers(world, "ada"), stock(world), person(world, "ada")["action"], hob_of(world)["action"])
    assert (waiting, served, events(world, "served")) == (
        (0, 24, "interacting", "pour_beer"), (1, 23, None, None), ["Hob poured Ada a mug of ale"])


def test_the_barkeep_walks_to_the_pour_cell_before_he_pours() -> None:
    world = opened(HOB)
    place(world, "hob", (2, 1))
    order_beer(world, "ada")
    advance(world, 8.0)
    assert ((hob_of(world)["x"], hob_of(world)["y"]), beers(world, "ada"), stock(world)) == ((5, 1), 1, 23)


def test_without_a_barkeep_the_tap_is_self_service() -> None:
    world = open_evening(LAYOUT, parse_scenario(plan()), seed=1)
    order_beer(world, "ada")
    advance(world, world["rules"]["durations"]["take_beer"] + 0.3)
    assert (beers(world, "ada"), stock(world), events(world, "served")) == (1, 23, [])


def test_a_guest_called_away_mid_pour_gets_no_mug_and_the_stock_stays() -> None:
    world = opened(HOB)
    order_beer(world, "ada")
    advance(world, 1.0)
    assert start_action(world, "ada", {"id": "wait", "verb": "wait", "target_id": None})["accepted"]
    advance(world, 4.0)
    assert (beers(world, "ada"), stock(world), events(world, "served"), hob_of(world)["action"]) == (0, 24, [], None)


def test_the_barkeep_leaves_a_conversation_to_pour() -> None:
    world = opened(HOB)
    start_conversation(world, person(world, "bea"), hob_of(world))
    assert conversation_of(world, "hob") is not None
    order_beer(world, "ada")
    advance(world, 0.3)
    assert (conversation_of(world, "hob"), hob_of(world)["action"]["verb"]) == (None, "pour_beer")


def test_two_guests_are_served_in_turn() -> None:
    world = opened(HOB)
    order_beer(world, "ada")
    place(world, "bea", (7, 4))
    assert start_action(world, "bea", TAKE_BEER)["accepted"]
    advance(world, 4.5)
    # Nobody decides in this world: Ada walks off with her mug by hand, as a guest would, to free the tap.
    place(world, "ada", (12, 6))
    advance(world, 10.0)
    assert (beers(world, "ada"), beers(world, "bea"), stock(world), events(world, "served")) == (
        1, 1, 22, ["Hob poured Ada a mug of ale", "Hob poured Bea a mug of ale"])


def test_a_drink_bought_for_a_friend_is_still_delivered() -> None:
    world = opened(HOB)
    world["invitations"].append({"kind": "buy_drink", "from": "ada", "to": "bea", "stage": "accepted", "held": 0})
    advance(world, 25.0)
    assert (beers(world, "ada"), beers(world, "bea"), stock(world)) == (0, 1, 23)


def test_a_guest_cannot_start_pouring() -> None:
    world = opened(HOB)
    result = start_action(world, "ada", {"id": "pour_beer", "verb": "pour_beer", "target_id": None})
    assert (result["accepted"], "staff" in result["reason"]) == (False, True)


def test_people_in_sight_carry_a_post_only_for_staff() -> None:
    world = opened(HOB)
    assert {item["id"]: item.get("post") for item in sees(world, "ada")["people"]} == {"hob": "Oak bar", "bea": None}


@pytest.mark.parametrize("barkeep_in_sight, phrase", [
    pytest.param(True, "to the tap and ask Hob for a mug of ale", id="ask-the-barkeep"),
    pytest.param(False, "to the tap and pour a mug of ale", id="pour-your-own"),
])
def test_the_option_says_who_pours(barkeep_in_sight: bool, phrase: str) -> None:
    world = opened(HOB)
    observation = sees(world, "ada")
    if not barkeep_in_sight:
        observation["people"] = [item for item in observation["people"] if item["id"] != "hob"]
    assert phrase in option_text(observation, {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"})


@pytest.mark.parametrize("busy, phrase", [
    pytest.param(False, "Hob, the barkeep, is tending the bar", id="idle"),
    pytest.param(True, "Hob, the barkeep, is pouring ale behind the bar", id="pouring"),
])
def test_the_briefing_shows_what_the_barkeep_is_doing(busy: bool, phrase: str) -> None:
    world = opened(HOB)
    if busy:
        order_beer(world, "bea")
        advance(world, 0.3)
    assert phrase in brief(sees(world, "ada"), [])["situation"]
