"""Handing an item to someone beside you: who may, whether it is taken, what both keep, and the saved world."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.items import empty_inventory
from tavern.hall.world import create_world, start_action
from tavern.server.runtime import TavernRuntime
from social_hall import actor, advance, command, hall
from staff_hall import HOB, opened, person


def seated() -> dict[str, Any]:
    """Ada and Bea sit at the near table, Cid at the far one, and Dan stands by the fire."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    return world


def hold(world: dict[str, Any], actor_id: str, **counts: int) -> None:
    """Put exactly these things in a guest's hands and pockets."""
    actor(world, actor_id)["inventory"].update({**empty_inventory(), **counts})


def give(item: str | None, receiver: str | None = "bea") -> dict[str, Any]:
    """Build the action of handing an item to someone."""
    return {"id": f"give:{item}:{receiver}", "verb": "give", "target_id": receiver, "item": item}


def handed(world: dict[str, Any], giver: str, action: dict[str, Any], seconds: float = 2.0) -> None:
    """Start a gift, let it finish, and check it was accepted."""
    assert start_action(world, giver, action) == {"accepted": True, "reason": None}
    advance(world, seconds)


def kinds_about(world: dict[str, Any], holder: str, about: str) -> list[str]:
    return [item["kind"] for item in actor(world, holder)["thoughts"] if item["about"] == about]


@pytest.mark.parametrize("kind, mine, theirs, expected", [
    pytest.param("remedy", 2, 0, (1, 1, ["cared_for"]), id="remedy"),
    pytest.param("keepsake", 1, 0, (0, 1, ["gifted"]), id="keepsake-the-last-one"),
    pytest.param("beer", 1, 0, (0, 1, ["treated"]), id="a-mug-of-ale"),
    pytest.param("remedy", 2, 1, (1, 2, ["cared_for"]), id="receiver-already-holds-one"),
    pytest.param("remedy", 3, 2, (2, 3, ["cared_for"]), id="receiver-fills-their-pockets"),
])
def test_a_gift_that_is_taken_moves_one_item_and_leaves_the_receiver_a_thought(
        kind: str, mine: int, theirs: int, expected: tuple[int, int, list[str]]) -> None:
    world = seated()
    hold(world, "ada", **{kind: mine})
    hold(world, "bea", **{kind: theirs})
    handed(world, "ada", give(kind))
    assert (actor(world, "ada")["inventory"][kind], actor(world, "bea")["inventory"][kind],
            kinds_about(world, "bea", "ada")) == expected


def test_a_gift_costs_the_giver_nothing_but_the_item() -> None:
    world = seated()
    hold(world, "ada", remedy=1)
    handed(world, "ada", give("remedy"))
    assert (kinds_about(world, "ada", "bea"), actor(world, "ada")["status"], actor(world, "ada")["action"]) == (
        [], "idle", None)


@pytest.mark.parametrize("who", [pytest.param("ada", id="giver"), pytest.param("bea", id="receiver")])
def test_both_remember_the_gift(who: str) -> None:
    world = seated()
    hold(world, "ada", remedy=1)
    handed(world, "ada", give("remedy"))
    assert [item["message"] for item in actor(world, who)["memory"] if item["type"] == "gave"] == [
        "Ada gave Bea a herbal remedy"]


def test_the_receiver_shows_affection() -> None:
    world = seated()
    hold(world, "ada", keepsake=1)
    handed(world, "ada", give("keepsake"))
    assert (actor(world, "bea")["emote"] or {}).get("kind") == "affection"
    assert actor(world, "ada")["emote"] is None


def test_the_giver_faces_the_receiver() -> None:
    world = seated()
    hold(world, "ada", remedy=1)
    assert start_action(world, "ada", give("remedy"))["accepted"]
    advance(world, 0.5)
    assert actor(world, "ada")["facing"] == "east"  # Bea sits to Ada's east


@pytest.mark.parametrize("opinion, outcome", [
    pytest.param(-21.0, (1, 0, ["gift_refused"], ["rebuffed"]), id="just-below-the-threshold"),
    pytest.param(-100.0, (1, 0, ["gift_refused"], ["rebuffed"]), id="loathing"),
    pytest.param(-20.0, (0, 1, ["gave"], []), id="at-the-threshold"),
    pytest.param(0.0, (0, 1, ["gave"], []), id="strangers"),
])
def test_someone_who_thinks_ill_of_the_giver_may_refuse(opinion: float, outcome: tuple[int, int, list[str], list[str]]) -> None:
    world = seated()
    hold(world, "ada", keepsake=1)
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": opinion, "familiarity": "acquaintance",
                                               "knows_name": True}
    handed(world, "ada", give("keepsake"))
    logged = [item["type"] for item in actor(world, "ada")["memory"] if item["type"] in ("gave", "gift_refused")]
    assert (actor(world, "ada")["inventory"]["keepsake"], actor(world, "bea")["inventory"]["keepsake"], logged,
            kinds_about(world, "ada", "bea")) == outcome


def test_a_refusal_is_remembered_by_both() -> None:
    world = seated()
    hold(world, "ada", keepsake=1)
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -50.0, "familiarity": "acquaintance",
                                               "knows_name": True}
    handed(world, "ada", give("keepsake"))
    assert [[item["message"] for item in actor(world, who)["memory"] if item["type"] == "gift_refused"]
            for who in ("ada", "bea")] == [["Bea would not take a keepsake from Ada"]] * 2


@pytest.mark.parametrize("ada_has, bea_has, action, reason", [
    pytest.param({"remedy": 1}, {}, give("remedy", "cid"), "Visitors must sit at one table or stand side by side",
                 id="receiver-at-another-table"),
    pytest.param({"remedy": 1}, {}, give("remedy", "dan"), "Visitors must sit at one table or stand side by side",
                 id="receiver-across-the-room"),
    pytest.param({"remedy": 1}, {}, give("remedy", "ada"), "Choose another visitor to give to", id="oneself"),
    pytest.param({"remedy": 1}, {}, give("remedy", "nobody"), "Choose another visitor to give to", id="unknown-person"),
    pytest.param({"remedy": 1}, {}, give("remedy", None), "Choose another visitor to give to", id="no-receiver"),
    pytest.param({}, {}, give("remedy"), "No remedy in inventory", id="nothing-to-give"),
    pytest.param({"keepsake": 1}, {}, give("remedy"), "No remedy in inventory", id="holding-another-kind"),
    pytest.param({"remedy": 1}, {"remedy": 3}, give("remedy"), "Bea has no free hand for a herbal remedy",
                 id="receiver-has-no-room"),
    pytest.param({"beer": 1}, {"beer": 2}, give("beer"), "Bea has no free hand for a mug of ale", id="receiver-hands-full"),
    pytest.param({"remedy": 1}, {}, give("wine"), "Unknown item 'wine'", id="unknown-kind"),
    pytest.param({"remedy": 1}, {}, give(None), "Choose something to give", id="no-item-named"),
    pytest.param({"remedy": 1}, {}, {"id": "wait", "verb": "wait", "target_id": None, "item": "remedy"},
                 "This action does not take an item", id="item-on-a-verb-that-takes-none"),
])
def test_a_gift_the_world_cannot_allow_is_refused_and_changes_nothing(
        ada_has: dict[str, int], bea_has: dict[str, int], action: dict[str, Any], reason: str) -> None:
    world = seated()
    hold(world, "ada", **ada_has)
    hold(world, "bea", **bea_has)
    before = (actor(world, "ada")["inventory"], actor(world, "bea")["inventory"])
    assert start_action(world, "ada", action) == {"accepted": False, "reason": reason}
    assert ((actor(world, "ada")["inventory"], actor(world, "bea")["inventory"]),
            actor(world, "ada")["action"]["verb"]) == (before, "sit")  # a refusal leaves her doing what she was


def test_the_barkeep_takes_no_gifts() -> None:
    world = opened(HOB)
    person(world, "ada")["inventory"]["remedy"] = 1
    advance(world, 1)
    assert start_action(world, "ada", give("remedy", "hob")) == {
        "accepted": False, "reason": "Hob works behind the bar and takes no gifts"}


def after_a_gift(wait: float) -> dict[str, Any]:
    """Ada has handed Bea a remedy, and `wait` more seconds have gone by; each holds more to give."""
    world = seated()
    hold(world, "ada", remedy=2, keepsake=1)
    hold(world, "bea", keepsake=1)
    handed(world, "ada", give("remedy"))
    advance(world, wait)
    return world


@pytest.mark.parametrize("giver, action, reason", [
    pytest.param("bea", give("keepsake", "ada"), "Ada gave Bea something a moment ago", id="giving-it-straight-back"),
    pytest.param("ada", give("remedy"), "Ada just gave Bea a herbal remedy", id="the-same-kind-again"),
])
def test_a_gift_is_not_passed_back_and_forth(giver: str, action: dict[str, Any], reason: str) -> None:
    assert start_action(after_a_gift(100.0), giver, action) == {"accepted": False, "reason": reason}


@pytest.mark.parametrize("wait, giver, action", [
    pytest.param(125.0, "bea", give("keepsake", "ada"), id="giving-back-after-the-wait"),
    pytest.param(125.0, "ada", give("remedy"), id="the-same-kind-after-the-wait"),
    pytest.param(100.0, "ada", give("keepsake"), id="another-kind-at-once"),
])
def test_a_gift_may_follow_another_once_enough_time_has_passed_or_it_is_another_kind(
        wait: float, giver: str, action: dict[str, Any]) -> None:
    assert start_action(after_a_gift(wait), giver, action) == {"accepted": True, "reason": None}


def test_a_gift_in_progress_survives_a_save() -> None:
    world = seated()
    hold(world, "ada", remedy=2)
    assert start_action(world, "ada", give("remedy"))["accepted"]
    advance(world, 0.5)
    loaded = parse_world(json.dumps(world))
    assert loaded == world
    advance(loaded, 2.0)
    assert (actor(loaded, "ada")["inventory"]["remedy"], actor(loaded, "bea")["inventory"]["remedy"]) == (1, 1)


def test_a_finished_gift_survives_a_save() -> None:
    world = seated()
    hold(world, "ada", remedy=1)
    handed(world, "ada", give("remedy"))
    assert parse_world(json.dumps(world)) == world


def damaged(damage: Any) -> str:
    world = seated()
    hold(world, "ada", remedy=2)
    assert start_action(world, "ada", give("remedy"))["accepted"]
    damage(world)
    return json.dumps(world)


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: actor(world, "ada")["action"].update(item="wine"), id="unknown-item"),
    pytest.param(lambda world: actor(world, "ada")["action"].pop("item"), id="gift-without-an-item"),
    pytest.param(lambda world: actor(world, "bea")["action"].update(item="beer"), id="item-on-a-sit"),
    pytest.param(lambda world: world["rules"].pop("giving"), id="no-giving-rules"),
    pytest.param(lambda world: world["rules"]["giving"].update(again_after=-1), id="negative-wait"),
    pytest.param(lambda world: world["rules"]["giving"].update(refuse_below=-101), id="threshold-out-of-range"),
    pytest.param(lambda world: world["rules"]["giving"].update(extra=1), id="unknown-rule"),
    pytest.param(lambda world: world["rules"]["giving"].pop("refuse_below"), id="missing-rule"),
])
def test_a_damaged_gift_in_a_save_is_rejected(damage: Any) -> None:
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(damaged(damage))


def test_the_client_is_told_which_verbs_name_an_item_and_target_a_person(tmp_path: Path) -> None:
    runtime = TavernRuntime({"width": 6, "height": 4, "tile_size": 32, "blocked": [], "objects": [],
                             "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]},
                            tmp_path / "save.json", {"typesafe_api_key": None})
    assert runtime.snapshot()["activities"]["give"] == {
        "label": "Give", "status": "giving", "pose": None, "target_kinds": [], "partner": True, "names_item": True}
