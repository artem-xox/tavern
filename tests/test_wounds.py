"""The hurt: what they are offered, how a remedy mends them, and who slips away home untreated."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.wounds import GROGGY_SECONDS, health_of, hurt, laid_out
from tavern.hall.world import observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from social_hall import actor, advance, command, know
from fight_hall import at_blows, battered, table_of_three, until_fight_ends


def offered(world: dict[str, Any], actor_id: str) -> list[str]:
    """The verbs a guest's first-stage and family options hold, from what they see in the world."""
    observation = {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}
    return sorted({item["verb"] for option in build_candidates(observation) for item in option.get("members", [option])})


@pytest.mark.parametrize("health, expected", [
    pytest.param(100.0, False, id="whole"), pytest.param(70.0, False, id="at-the-line"),
    pytest.param(69.9, True, id="just-under"), pytest.param(0.0, True, id="nothing-left"),
])
def test_a_guest_is_hurt_below_seventy(health: float, expected: bool) -> None:
    assert hurt({"health": health}) is expected


def test_a_record_with_no_health_counts_as_whole() -> None:
    assert (health_of({}), hurt({}), laid_out({})) == (100.0, False, False)


def test_a_hurt_guest_is_offered_only_the_road_to_mending() -> None:
    world = table_of_three()
    battered(world, "bea")
    know(world, "bea", "door")
    assert offered(world, "bea") == ["leave"]


def test_a_hurt_guest_who_carries_a_remedy_may_take_it_and_one_who_sees_a_healer_may_ask() -> None:
    world = table_of_three()
    battered(world, "bea")
    actor(world, "bea")["inventory"]["remedy"] = 1
    actor(world, "cid")["inventory"]["remedy"] = 2
    know(world, "bea", "door")
    assert offered(world, "bea") == ["leave", "seek_remedy", "use_remedy"]


def test_a_whole_guest_is_offered_what_they_always_are() -> None:
    world = table_of_three()
    assert {"talk", "wait", "inspect"} <= set(offered(world, "bea"))


def test_the_briefing_tells_a_hurt_guest_that_mending_is_their_business() -> None:
    world = table_of_three()
    battered(world, "bea", 35.0)
    actor(world, "cid")["inventory"]["remedy"] = 1
    observation = {**observe_actor(world, "bea"), "people": observe_people(world, "bea")}
    situation = brief(observation, build_candidates(observation))["situation"]
    assert "hurt (health 35 of 100)" in situation and "first business is to mend" in situation and "Cid carries remedies" in situation


def test_taking_a_remedy_mends_a_hurt_guest_and_uses_it_up() -> None:
    world = table_of_three()
    battered(world, "bea", 30.0)
    actor(world, "bea")["inventory"]["remedy"] = 1
    assert start_action(world, "bea", command("use_remedy"))["accepted"]
    advance(world, 3)
    bea = actor(world, "bea")
    assert (bea["health"], bea["inventory"]["remedy"], bea["condition"]) == (90.0, 0, "ok")


def test_asking_a_healer_for_a_remedy_mends_the_hurt_guest() -> None:
    world = table_of_three()
    battered(world, "bea", 40.0)
    actor(world, "cid")["inventory"]["remedy"] = 2
    assert start_action(world, "bea", command("seek_remedy", "cid"))["accepted"]
    advance(world, 6)
    assert (actor(world, "bea")["health"], actor(world, "cid")["inventory"]["remedy"]) == (100.0, 1)
    assert [item["kind"] for item in actor(world, "bea")["thoughts"] if item["about"] == "cid"] == ["tended"]


def test_a_healer_who_thinks_ill_of_the_asker_refuses() -> None:
    world = table_of_three()
    battered(world, "bea", 40.0)
    cid = actor(world, "cid")
    cid["inventory"]["remedy"] = 2
    cid["relations"]["bea"] = {"name": "Bea", "opinion": -60.0, "familiarity": "acquaintance", "knows_name": True}
    assert start_action(world, "bea", command("seek_remedy", "cid"))["accepted"]
    advance(world, 6)
    assert (actor(world, "bea")["health"], actor(world, "cid")["inventory"]["remedy"]) == (40.0, 2)
    assert any(item["type"] == "remedy_refused" for item in world["events"])


@pytest.mark.parametrize("target, reason", [
    pytest.param("cid", "Cid carries no remedy", id="someone-with-none"),
    pytest.param("bea", "Choose another visitor to go to", id="oneself"),
])
def test_a_healer_must_be_someone_who_carries_a_remedy(target: str, reason: str) -> None:
    world = table_of_three()
    assert start_action(world, "bea", command("seek_remedy", target)) == {"accepted": False, "reason": reason}


def test_a_remedy_given_to_a_hurt_guest_mends_them_on_the_spot() -> None:
    world = table_of_three()
    battered(world, "bea", 20.0)
    actor(world, "cid")["inventory"]["remedy"] = 1
    assert start_action(world, "cid", {"id": "give:remedy:bea", "verb": "give", "target_id": "bea", "item": "remedy"})["accepted"]
    advance(world, 3)
    bea = actor(world, "bea")
    assert (bea["health"], bea["inventory"]["remedy"]) == (80.0, 0)


def test_a_knocked_out_guest_left_untreated_slips_away_home() -> None:
    world = table_of_three()
    at_blows(world)
    until_fight_ends(world)
    assert actor(world, "bea")["condition"] == "out"
    advance(world, 40 + GROGGY_SECONDS + 20)
    assert [item["id"] for item in world["departed"]] == ["bea"]
    assert [item["message"] for item in actor(world, "bea")["memory"] if item["type"] == "limped_home"] == [
        "Bea, battered, slipped out of the inn to go home"]


def test_a_remedy_in_time_keeps_a_knocked_out_guest_in_the_hall() -> None:
    world = table_of_three()
    actor(world, "cid")["inventory"]["remedy"] = 1
    at_blows(world)
    until_fight_ends(world)
    advance(world, 45)
    assert actor(world, "bea")["condition"] == "groggy"
    assert start_action(world, "cid", {"id": "give:remedy:bea", "verb": "give", "target_id": "bea", "item": "remedy"})["accepted"]
    advance(world, 40)
    assert (actor(world, "bea")["condition"], [item["id"] for item in world["departed"]]) == ("ok", [])


def test_a_hurt_and_groggy_guest_saves_and_loads() -> None:
    world = table_of_three()
    at_blows(world)
    until_fight_ends(world)
    advance(world, 45)
    assert parse_world(json.dumps(world))["actors"] == world["actors"]
