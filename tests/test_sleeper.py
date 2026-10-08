"""A sleeper at the table: the others see them asleep, let them be, and do not offer them anything."""

from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.social.giving import empty_handed_company, gift_targets
from tavern.social.hostility import hostile_targets
from hostile_view import QUARREL, person, view
from social_hall import actor, advance, command, hall
from test_bring_drink import at_the_table
from test_fetching_a_drink import advance_until, bought_for_bea, events, holds_a_mug, the_errand_ends


def table_for_two(bea_asleep: bool) -> dict[str, Any]:
    """Ada and Bea sit at the near table, Ada with a mug of ale; Bea sleeps there if she is to."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 0.5)
    actor(world, "ada")["inventory"]["beer"] = 1
    if bea_asleep:
        assert start_action(world, "bea", command("doze"))["accepted"]
    return world


@pytest.mark.parametrize("verb, item", [
    pytest.param("talk", None, id="chat"),
    pytest.param("give", "beer", id="giving"),
    pytest.param("bring_drink", None, id="fetching-a-drink"),
    pytest.param("shove", None, id="shoving"),
    pytest.param("start_fight", None, id="fighting"),
])
def test_nobody_turns_to_a_sleeper_but_they_would_to_a_waking_guest(verb: str, item: str | None) -> None:
    def attempt(asleep: bool) -> dict[str, Any]:
        world = table_for_two(asleep)
        aimed = {**command(verb, "bea"), **({"item": item, "id": f"{verb}:{item}:bea"} if item else {})}
        return start_action(world, "ada", aimed)
    assert (attempt(False)["accepted"], attempt(True)) == (True, {"accepted": False, "reason": "Bea is asleep"})


def test_a_sleeper_is_seen_asleep_and_is_not_free_to_talk() -> None:
    world = table_for_two(True)
    bea = next(item for item in observe_people(world, "ada") if item["id"] == "bea")
    assert (bea["asleep"], bea["available"]) == (True, False)


def test_a_waking_tablemate_is_not_asleep() -> None:
    world = table_for_two(False)
    bea = next(item for item in observe_people(world, "ada") if item["id"] == "bea")
    assert (bea["asleep"], bea["available"]) == (False, True)


def offered(observation: dict[str, Any]) -> set[str]:
    """The verbs of every first-stage option a guest is offered, with the members of each family."""
    return {item["verb"] for option in build_candidates(observation) for item in option.get("members", [option])}


@pytest.mark.parametrize("asleep, verbs", [
    pytest.param(False, {"talk", "bring_drink"}, id="awake-tablemate"),
    pytest.param(True, set(), id="sleeping-tablemate"),
])
def test_a_sleeping_tablemate_gets_no_chat_and_no_drink(asleep: bool, verbs: set[str]) -> None:
    sleeper = person("bea", asleep=asleep, available=not asleep)
    assert offered(at_the_table([sleeper])) & {"talk", "bring_drink"} == verbs


@pytest.mark.parametrize("asleep, expected", [
    pytest.param(False, ["bea"], id="awake"),
    pytest.param(True, [], id="asleep"),
])
def test_a_sleeper_is_nobody_to_give_to_or_to_fetch_for_or_to_turn_on(asleep: bool, expected: list[str]) -> None:
    observation = at_the_table([person("bea", asleep=asleep, available=not asleep)], beer=1)
    observation["actor"].update(drunkenness=0.9)
    observation["actor"]["thoughts"] = QUARREL
    observation["actor"]["relations"]["bea"]["opinion"] = -40.0
    observation["actor"]["traits"]["temper"] = 1.0
    assert (gift_targets(observation, "beer"), empty_handed_company(observation),
            hostile_targets(observation, "shove"), hostile_targets(observation, "start_fight")) == (
        expected, expected, expected, expected)


def test_the_briefing_says_asleep_not_in_a_hurry() -> None:
    world = table_for_two(True)
    situation = brief(observe_actor(world, "ada"), [])["situation"]
    assert ("Bea sits across the table from them, asleep" in situation, "in a hurry" in situation) == (True, False)


def test_a_mug_is_not_pressed_on_a_sleeper_and_the_errand_ends() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    assert start_action(world, "bea", command("doze"))["accepted"]
    advance_until(world, the_errand_ends)
    bea = actor(world, "bea")
    assert (bea["inventory"]["beer"], actor(world, "ada")["inventory"]["beer"], (bea["action"] or {}).get("verb"),
            events(world, "fetch_failed")) == (0, 1, "doze", ["Ada could not bring Bea an ale"])
