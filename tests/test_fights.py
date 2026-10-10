"""Fights in the world: how one opens, runs its exchanges, ends, and what it leaves on the fighters."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.blows import MIN_SECONDS
from tavern.body.fights import OUTCOMES, fight_of, running
from tavern.evening.decisions import free_to_decide
from tavern.hall.world import create_world, start_action
from social_hall import actor, advance, command, hall


def pair(seed: int = 4, strong: str = "ada", beaten_courage: float = 1.0) -> dict[str, Any]:
    """Ada and Bea sit at the near table, Cid at the far one; `strong` is a heavy brawler, the other a weak one."""
    world = create_world(hall(), seed)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    weak = "bea" if strong == "ada" else "ada"
    actor(world, strong)["traits"].update(strength=1.0, brawling=1.0, courage=1.0, temper=0.2)
    actor(world, weak)["traits"].update(strength=0.1, brawling=0.0, courage=beaten_courage, temper=0.2)
    return world


def brawl(world: dict[str, Any], attacker: str = "ada", victim: str = "bea") -> None:
    assert start_action(world, attacker, command("start_fight", victim)) == {"accepted": True, "reason": None}


def finish(world: dict[str, Any], limit: float = 30.0) -> dict[str, Any]:
    """Run the world until the first fight is over, and return it."""
    for _ in range(round(limit * 10)):
        advance(world, 0.1)
        if world["fights"] and world["fights"][0]["outcome"] is not None:
            return dict(world["fights"][0])
    raise AssertionError("the fight never ended")


def test_a_fight_opens_with_both_fighters_holding_the_fight_verb_at_each_other() -> None:
    world = pair()
    brawl(world)
    advance(world, 0.2)
    fights = running(world)
    assert [(item["a"], item["b"], item["outcome"]) for item in fights] == [("ada", "bea", None)]
    assert [(actor(world, who)["action"]["verb"], actor(world, who)["action"]["target_id"], actor(world, who)["status"])
            for who in ("ada", "bea")] == [("start_fight", "bea", "interacting"), ("start_fight", "ada", "interacting")]


def test_a_fighter_is_not_free_to_decide_while_the_fight_lasts() -> None:
    world = pair()
    brawl(world)
    advance(world, 0.5)
    assert [free_to_decide(world, actor(world, who)) for who in ("ada", "bea", "cid")] == [False, False, True]


def test_both_fighters_lose_the_mug_in_their_hands() -> None:
    world = pair()
    for who in ("ada", "bea"):
        actor(world, who)["inventory"]["beer"] = 1
    brawl(world)
    advance(world, 0.2)
    assert [actor(world, who)["inventory"]["beer"] for who in ("ada", "bea")] == [0, 0]
    assert sum(1 for item in world["events"] if item["type"] == "spilled") == 2


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in (1, 4, 9)])
def test_a_fight_lasts_at_least_three_seconds_and_ends_in_a_known_way(seed: int) -> None:
    world = pair(seed)
    brawl(world)
    fight = finish(world)
    assert fight["outcome"] in OUTCOMES and fight["ended_at"] - fight["started_at"] >= MIN_SECONDS


def test_a_knockout_lies_on_the_floor_then_gets_up_groggy_with_their_thoughts() -> None:
    world = pair()
    brawl(world)
    fight = finish(world)
    assert (fight["outcome"], fight["loser"]) == ("knockout", "bea")
    bea = actor(world, "bea")
    assert (bea["condition"], bea["action"]["verb"], bea["health"] <= 15) == ("out", "recover", True)
    assert actor(world, "ada")["action"] is None
    thoughts = [item["kind"] for item in bea["thoughts"]]
    advance(world, 41)
    assert (bea["condition"], bea["action"]) == ("groggy", None)
    assert [item["kind"] for item in bea["thoughts"] if item["kind"] in thoughts] == thoughts


def test_nobody_may_turn_on_someone_already_fighting() -> None:
    world = pair()
    brawl(world)
    advance(world, 0.2)
    assert start_action(world, "cid", command("start_fight", "ada")) == {"accepted": False, "reason": "Ada is fighting"}
    assert fight_of(world, "cid") is None


def test_a_fighter_cannot_start_another_fight() -> None:
    world = pair()
    brawl(world)
    advance(world, 0.2)
    assert start_action(world, "ada", command("start_fight", "cid"))["accepted"] is False
    assert len(running(world)) == 1


def test_a_witness_holds_the_fight_against_whoever_started_it() -> None:
    world = pair()
    brawl(world)
    advance(world, 1)
    assert [item["about"] for item in actor(world, "cid")["thoughts"] if item["kind"] == "saw_fight"] == ["ada"]


def test_a_seeded_fight_replays_identically() -> None:
    first, second = pair(7), pair(7)
    for world in (first, second):
        brawl(world)
        finish(world)
    assert first["fights"] == second["fights"]


def test_a_fight_saves_and_loads_while_it_runs_and_after_it_ended() -> None:
    world = pair()
    brawl(world)
    advance(world, 1.5)
    assert parse_world(json.dumps(world))["fights"] == world["fights"]
    finish(world)
    assert parse_world(json.dumps(world))["fights"] == world["fights"]


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: world["fights"][0].update(outcome="brawl"), id="unknown-outcome"),
    pytest.param(lambda world: world["fights"][0].update(b="ada"), id="against-themselves"),
    pytest.param(lambda world: world["fights"][0].update(weapons={"ada": "fists", "bea": "sword"}), id="unknown-weapon"),
    pytest.param(lambda world: world["fights"][0].update(witnessed="yes"), id="malformed-flag"),
    pytest.param(lambda world: actor(world, "bea").update(action=None), id="a-fighter-not-holding-the-verb"),
    pytest.param(lambda world: actor(world, "bea").update(health=140.0), id="health-out-of-range"),
    pytest.param(lambda world: actor(world, "bea").update(condition="asleep"), id="unknown-condition"),
    pytest.param(lambda world: actor(world, "bea").update(condition="out"), id="a-condition-with-no-end"),
])
def test_a_malformed_fight_or_wound_fails_loudly_on_load(damage: Any) -> None:
    world = pair()
    brawl(world)
    advance(world, 1.5)
    damage(world)
    with pytest.raises(ValueError):
        parse_world(json.dumps(world))
