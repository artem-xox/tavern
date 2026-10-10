"""The room's part in a fight: what a guest who sees one may do, and what stepping in, waiting a turn or helping up do."""

from typing import Any

import pytest

from tavern.body.fights import fight_of, running
from tavern.hall.world import start_action
from tavern.social.bystanders import reactions
from social_hall import actor, advance, command
from fight_hall import at_blows, table_of_three, until_fight_ends

NOW = 300.0


def person(person_id: str, **fields: Any) -> dict[str, Any]:
    """Someone Ada sees, seated at her table, whole and at peace."""
    return {"id": person_id, "name": person_id.title(), "seat_id": "e", "table_id": "near", "beside": False,
            "fighting": None, "condition": "ok", **fields}


def view(people: list[dict[str, Any]], **opinions: float) -> dict[str, Any]:
    """Ada's observation: the people she sees, and her opinion of some of them."""
    relations = {name: {"name": name.title(), "opinion": value, "familiarity": "acquaintance"}
                 for name, value in opinions.items()}
    return {"actor": {"id": "ada", "inventory": {}, "traits": {}, "relations": relations, "thoughts": [],
                      "drunkenness": 0.0}, "people": people, "time": NOW}


@pytest.mark.parametrize("people, opinions, expected", [
    pytest.param([], {}, [], id="nobody-in-sight"),
    pytest.param([person("bea")], {}, [], id="everyone-at-peace"),
    pytest.param([person("bea", fighting="cid"), person("cid", fighting="bea")], {},
                 [("watch_fight", None), ("cheer", None), ("intervene", "bea"), ("intervene", "cid")], id="a-fight-at-her-table"),
    pytest.param([person("bea", fighting="cid", seat_id=None, table_id=None),
                  person("cid", fighting="bea", seat_id=None, table_id=None)], {},
                 [("watch_fight", None), ("cheer", None)], id="a-fight-she-cannot-walk-to"),
    pytest.param([person("bea", fighting="cid", seat_id=None, table_id=None, beside=True),
                  person("cid", fighting="bea", seat_id=None, table_id=None)], {},
                 [("watch_fight", None), ("cheer", None), ("intervene", "bea")], id="one-of-them-beside-her"),
    pytest.param([person("bea", fighting="cid"), person("cid", fighting="bea")], {"cid": -30.0},
                 [("watch_fight", None), ("cheer", None), ("intervene", "bea"), ("intervene", "cid"),
                  ("join_fight", "cid")], id="a-grudge-against-one"),
    pytest.param([person("bea", fighting="cid"), person("cid", fighting="bea")], {"bea": 60.0},
                 [("watch_fight", None), ("cheer", None), ("intervene", "bea"), ("intervene", "cid"),
                  ("join_fight", "cid")], id="a-friend-is-being-beaten"),
    pytest.param([person("bea", condition="out")], {}, [("help_up", "bea")], id="someone-on-the-floor"),
    pytest.param([person("bea", condition="out", seat_id=None, table_id=None)], {}, [], id="on-the-floor-out-of-reach"),
    pytest.param([person("bea", condition="out", fighting="cid"), person("cid", fighting="bea")], {},
                 [("watch_fight", None), ("cheer", None), ("intervene", "bea"), ("intervene", "cid")],
                 id="a-fighter-is-not-helped-up-mid-fight"),
])
def test_what_a_guest_may_do_about_a_fight_or_a_fallen_guest(people: list[dict[str, Any]], opinions: dict[str, float],
                                                             expected: list[tuple[str, str | None]]) -> None:
    assert reactions(view(people, **opinions)) == expected


def test_stepping_between_two_fighters_sometimes_parts_them() -> None:
    results = []
    for seed in range(12):
        world = table_of_three(seed)
        actor(world, "cid")["traits"].update(strength=1.0, courage=1.0)
        at_blows(world)
        advance(world, 3.2)
        assert start_action(world, "cid", command("intervene", "ada"))["accepted"]
        advance(world, 2.0)
        results.append(world["fights"][0]["outcome"])
    assert 0 < results.count("separated") < len(results)


def test_a_fight_pulled_apart_frees_both_and_leaves_thoughts_of_the_one_who_did_it() -> None:
    for seed in range(12):
        world = table_of_three(seed)
        actor(world, "cid")["traits"].update(strength=1.0, courage=1.0)
        at_blows(world)
        advance(world, 3.2)
        start_action(world, "cid", command("intervene", "ada"))
        advance(world, 2.0)
        if world["fights"][0]["outcome"] != "separated":
            continue
        assert [actor(world, who)["action"] for who in ("ada", "bea")] == [None, None]
        assert [[item["kind"] for item in actor(world, who)["thoughts"] if item["about"] == "cid"] for who in ("ada", "bea")] == [
            ["separated_us"], ["separated_us"]]
        return
    raise AssertionError("no seed parted them")


def test_a_bystander_away_from_the_table_walks_over_to_step_between() -> None:
    world = table_of_three()
    at_blows(world)
    advance(world, 0.5)
    assert start_action(world, "dan", command("intervene", "ada"))["accepted"]  # walks over to the table
    assert actor(world, "dan")["status"] == "walking"


def test_nobody_may_part_two_who_are_not_fighting() -> None:
    world = table_of_three()
    assert start_action(world, "cid", command("intervene", "ada")) == {"accepted": False, "reason": "Ada is not fighting"}


def test_one_who_waits_a_turn_fights_whoever_is_left_standing() -> None:
    world = table_of_three(strong="ada", weak_courage=1.0)
    at_blows(world)
    advance(world, 0.5)
    assert start_action(world, "cid", command("join_fight", "ada"))["accepted"]
    first = until_fight_ends(world)
    advance(world, 0.3)
    assert first["loser"] == "bea"
    assert [(item["a"], item["b"]) for item in running(world)] == [("cid", "ada")]
    assert fight_of(world, "cid") is not None


def test_only_one_may_wait_against_a_fighter() -> None:
    world = table_of_three()
    at_blows(world)
    advance(world, 0.5)
    assert start_action(world, "cid", command("join_fight", "ada"))["accepted"]
    assert start_action(world, "dan", command("join_fight", "ada"))["accepted"]
    advance(world, 10)
    assert [entry["id"] for entry in world["fights"][0]["waiting"]] == ["cid"]


def test_a_fighter_cannot_be_joined_by_someone_fighting_already() -> None:
    world = table_of_three()
    at_blows(world)
    advance(world, 0.5)
    assert start_action(world, "ada", command("join_fight", "bea"))["accepted"] is False


def test_helping_a_knocked_out_guest_up_makes_them_groggy_and_grateful() -> None:
    world = table_of_three()
    at_blows(world)
    until_fight_ends(world)
    assert actor(world, "bea")["condition"] == "out"
    assert start_action(world, "cid", command("help_up", "bea"))["accepted"]
    advance(world, 3)
    bea = actor(world, "bea")
    assert (bea["condition"], bea["action"]) == ("groggy", None)
    assert [item["kind"] for item in bea["thoughts"] if item["about"] == "cid"] == ["helped_up"]


def test_only_someone_on_the_floor_is_helped_up() -> None:
    world = table_of_three()
    assert start_action(world, "cid", command("help_up", "bea")) == {"accepted": False, "reason": "Bea is not on the floor"}
