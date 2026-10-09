"""Standing a round: a guest fetches an ale for each empty-handed tablemate in turn, as one plan."""

from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.local_policy import local_scores
from social_hall import actor, advance, command, know, spotted_hall


def three_at_a_table(tap_stock: int = 9) -> dict[str, Any]:
    """Ada, Bea and Cid sit at the near table; Ada knows the tap."""
    world = create_world(spotted_hall(), 4)
    for name, chair in (("ada", "w"), ("bea", "e"), ("cid", "n")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 10)
    know(world, "ada", "tap", "near", "w", "e", "n")
    next(item for item in world["map"]["objects"] if item["id"] == "tap")["stock"] = tap_stock
    know(world, "ada", "tap")
    return world


def stand(world: dict[str, Any]) -> dict[str, Any]:
    """Ada stands the table a round."""
    return start_action(world, "ada", command("stand_a_round"))


def of(world: dict[str, Any], kind: str) -> list[str]:
    """Messages of logged events of a kind."""
    return [item["message"] for item in world["events"] if item["type"] == kind]


def test_a_round_is_a_project_with_a_step_for_each_tablemate_in_seat_order() -> None:
    world = three_at_a_table()
    assert stand(world)["accepted"]
    [project] = world["projects"]
    assert (project["kind"], project["target"], project["targets"], project["of"]) == (
        "stand_a_round", "near", ["bea", "cid"], 2)


def test_every_tablemate_is_served_in_turn_and_the_round_is_logged() -> None:
    world = three_at_a_table()
    assert stand(world)["accepted"]
    advance(world, 140)
    assert ([actor(world, name)["inventory"]["beer"] + actor(world, name)["visit"]["beers"] for name in ("bea", "cid")],
            of(world, "project_done"), world["projects"]) == (
        [1, 1], ["Ada stood the table a round (stand_a_round)"], [])


def test_a_tablemate_who_goes_home_is_skipped() -> None:
    world = three_at_a_table()
    assert stand(world)["accepted"]
    world["actors"].remove(actor(world, "cid"))
    advance(world, 140)
    assert (actor(world, "bea")["inventory"]["beer"] + actor(world, "bea")["visit"]["beers"],
            of(world, "project_done")) == (1, ["Ada stood the table a round (stand_a_round)"])


def test_a_tablemate_who_already_holds_a_mug_is_skipped() -> None:
    world = three_at_a_table()
    assert stand(world)["accepted"]
    actor(world, "cid")["inventory"]["beer"] = 1
    advance(world, 140)
    assert (of(world, "project_done"), [item for item in of(world, "gave") if "Cid" in item]) == (
        ["Ada stood the table a round (stand_a_round)"], [])


def test_the_round_fails_when_the_tap_runs_dry_on_the_second_mug() -> None:
    world = three_at_a_table(tap_stock=1)
    assert stand(world)["accepted"]
    advance(world, 140)
    failed = of(world, "project_failed")
    assert (len(failed), of(world, "project_done"), world["projects"]) == (1, [], [])
    assert failed[0].startswith("Ada could not stand a round: ") and failed[0].endswith("(stand_a_round)")


@pytest.mark.parametrize("prepare", [
    pytest.param(lambda world: world["actors"].remove(actor(world, "cid")), id="only-one-tablemate"),
    pytest.param(lambda world: [actor(world, name)["inventory"].update(beer=1) for name in ("bea", "cid")],
                 id="everyone-has-a-mug"),
    pytest.param(lambda world: actor(world, "ada")["inventory"].update(beer=2), id="no-free-hand"),
    pytest.param(lambda world: actor(world, "ada")["knowledge"]["objects"].pop("tap"), id="no-tap-known"),
    pytest.param(lambda world: actor(world, "ada").update(seat_id=None), id="not-seated"),
])
def test_a_round_that_cannot_be_stood_is_refused(prepare: Any) -> None:
    world = three_at_a_table()
    prepare(world)
    assert (stand(world)["accepted"], world["projects"]) == (False, [])


def seen(world: dict[str, Any], projects: bool = True) -> dict[str, Any]:
    """Ada's observation."""
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada"), **({"projects": ["stand_a_round"]} if projects else {})}


@pytest.mark.parametrize("prepare, offered", [
    pytest.param(lambda world: None, True, id="two-empty-handed-tablemates"),
    pytest.param(lambda world: world["actors"].remove(actor(world, "cid")), False, id="one-tablemate"),
    pytest.param(lambda world: actor(world, "bea")["inventory"].update(beer=1), False, id="one-of-two-has-a-mug"),
    pytest.param(lambda world: actor(world, "ada")["inventory"].update(beer=2), False, id="no-free-hand"),
])
def test_a_round_is_offered_to_a_seated_guest_with_two_empty_handed_tablemates(prepare: Any, offered: bool) -> None:
    world = three_at_a_table()
    prepare(world)
    found = [item for option in build_candidates(seen(world)) for item in option.get("members", [option])
             if item["verb"] == "stand_a_round"]
    assert bool(found) is offered


def test_a_round_is_not_offered_where_projects_are_not_on() -> None:
    world = three_at_a_table()
    assert all(item["verb"] != "stand_a_round" for option in build_candidates(seen(world, projects=False))
               for item in option.get("members", [option]))


def test_a_round_shares_a_family_with_fetching_one_drink_and_scores_above_it() -> None:
    world = three_at_a_table()
    view = seen(world)
    [fetching] = [option for option in build_candidates(view) if option["id"] == "fetching"]
    scores = local_scores(view, fetching["members"])
    assert scores["stand_a_round"] == pytest.approx(scores["bring_drink:bea"] + 0.1)
