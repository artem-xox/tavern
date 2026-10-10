"""Shoves and fights as the world runs them: who may, what it costs, who hears. (What a fight is: `test_fights.py`.)"""

import asyncio
from random import Random
from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import Evaluators, choose_action
from tavern.social.thoughts import opinion_of, think, thought_mood
from social_hall import actor, advance, command, hall
from staff_hall import HOB, opened, person


def seated() -> dict[str, Any]:
    """Ada and Bea sit at the near table, Cid at the far one, and Dan stands by the fire."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    return world


def heard_by_cid(world: dict[str, Any]) -> list[str]:
    """What made Cid, at the far table, look up or take note."""
    return [event["message"] for event in world["events"]
            if event["actor_id"] == "cid" and event["type"] in ("interrupted", "alerted")]


# A shove is over in a second; a fight is still going three seconds on, with its fighters on the spot.
@pytest.mark.parametrize("verb, event, kind, opinion, mood, noun, status", [
    pytest.param("shove", "shove", "shoved", -25.0, -8.0, "a scuffle", "idle", id="shove"),
    pytest.param("start_fight", "fight_started", "attacked", -35.0, -10.0, "a brawl", "interacting", id="start-fight"),
])
def test_a_hostile_act_is_logged_costs_the_victim_and_is_heard(verb: str, event: str, kind: str, opinion: float,
                                                               mood: float, noun: str, status: str) -> None:
    world = seated()
    assert start_action(world, "ada", command(verb, "bea")) == {"accepted": True, "reason": None}
    advance(world, 3)
    bea = actor(world, "bea")
    assert ([item["type"] for item in world["events"] if item["actor_id"] == "ada" and item["type"] == event],
            [item["kind"] for item in bea["thoughts"] if item["about"] == "ada"],
            opinion_of(bea, "ada", world["time"]), thought_mood(bea, world["time"]),
            [item["status"] for item in world["actors"] if item["id"] == "ada"]) == (
        [event], [kind], opinion, mood, [status])
    assert any(noun in message for message in heard_by_cid(world))


# Only a fight is a spectacle: those who see one begin hold it against whoever started it (`social/bystanders.py`).
@pytest.mark.parametrize("verb, onlookers", [
    pytest.param("shove", [[], []], id="shove"),
    pytest.param("start_fight", [["saw_fight"], ["saw_fight"]], id="start-fight"),
])
def test_the_one_turned_on_is_the_only_one_who_minds(verb: str, onlookers: list[list[str]]) -> None:
    world = seated()
    start_action(world, "ada", command(verb, "bea"))
    advance(world, 3)
    assert [item["thoughts"] for item in world["actors"] if item["id"] == "ada"] == [[]]
    assert [[thought["kind"] for thought in item["thoughts"]] for item in world["actors"]
            if item["id"] in ("cid", "dan")] == onlookers


@pytest.mark.parametrize("target, reason", [
    pytest.param("cid", "Visitors must sit at one table or stand side by side", id="at-another-table"),
    pytest.param("dan", "Visitors must sit at one table or stand side by side", id="across-the-room"),
    pytest.param("ada", "Choose another visitor to confront", id="oneself"),
    pytest.param("nobody", "Choose another visitor to confront", id="unknown-person"),
    pytest.param(None, "Choose another visitor to confront", id="no-target"),
])
@pytest.mark.parametrize("verb", [pytest.param("shove", id="shove"), pytest.param("start_fight", id="start-fight")])
def test_only_someone_within_reach_may_be_turned_on(verb: str, target: str | None, reason: str) -> None:
    world = seated()
    assert start_action(world, "ada", command(verb, target)) == {"accepted": False, "reason": reason}
    assert actor(world, "ada")["action"]["verb"] == "sit"  # a refusal leaves her doing what she was


def test_the_barkeep_is_not_to_be_fought() -> None:
    world = opened(HOB)
    advance(world, 1)
    assert start_action(world, "ada", command("shove", "hob")) == {
        "accepted": False, "reason": "Hob works behind the bar and is not to be fought"}
    assert person(world, "ada")["action"] is None


def chooses(world: dict[str, Any], *verbs: str) -> dict[str, Any]:
    """Ada's decision when the model favours the given verbs, made from what she sees in the world."""
    async def prefer(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["verb"] in verbs) for action in candidates}
    observation = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
    config = {"typesafe_api_key": "key", "model": "jev-latest", "timeout": 2.0, "temperature": 0.0}
    return asyncio.run(choose_action(observation, config, Random(1), Evaluators(prefer, prefer)))


def wronged(world: dict[str, Any], temper: float) -> None:
    """Ada has a short temper and a grudge: Bea quarreled with her, and she thought little of Bea before."""
    ada, bea = actor(world, "ada"), actor(world, "bea")
    ada["traits"]["temper"] = temper
    ada["relations"]["bea"] = {"name": "Bea", "opinion": -20.0, "familiarity": "acquaintance", "knows_name": True}
    think(ada, "quarrel", world["time"], "Quarreled with Bea", "quarrel", about=bea)


def test_a_guest_with_a_grudge_who_is_inclined_to_it_picks_a_fight_in_the_world() -> None:
    world = seated()
    wronged(world, 1.0)
    actor(world, "ada")["drunkenness"] = 0.5  # fights come by drink or by hatred
    decision = chooses(world, "confront", "start_fight")
    assert (decision["action"]["id"], decision["family"]["name"]) == ("start_fight:bea", "confront")
    assert start_action(world, "ada", decision["action"])["accepted"]
    advance(world, 3)
    assert [item["kind"] for item in actor(world, "bea")["thoughts"] if item["about"] == "ada"] == ["attacked"]


def test_the_same_guest_without_the_grudge_is_never_offered_a_fight() -> None:
    world = seated()
    wronged(world, 1.0)
    actor(world, "ada")["thoughts"].clear()
    decision = chooses(world, "confront", "shove", "start_fight")
    assert decision["action"]["verb"] not in ("shove", "start_fight")
