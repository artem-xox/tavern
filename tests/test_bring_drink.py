"""Bringing someone a drink: a choice with no invitation, offered to a guest who could, and run as an errand."""

import json
from collections.abc import Callable
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import create_world, observe_actor, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.mind.options import option_text
from hostile_view import person, view
from social_hall import actor, advance, command, hall, know
from test_giving import asked_about
from test_fetching_a_drink import advance_until, events, holds_a_mug, the_errand_ends

TAP = {"id": "tap", "kind": "tap", "name": "House ale", "x": 11, "y": 0, "interaction_spots": [[10, 0]],
       "stock": 5, "reserved_by": None}


def at_the_table(people: list[dict[str, Any]] | None = None, tap: dict[str, Any] | None = TAP,
                 beer: int = 0, **fields: Any) -> dict[str, Any]:
    """Ada's observation: seated at the near table with Bea, who holds nothing, and the tap she knows."""
    observation = view(None, people, **fields)
    observation["actor"]["inventory"]["beer"] = beer
    observation["objects"] = [*observation["objects"], *([tap] if tap else [])]
    observation["giving"] = {"refuse_below": -20.0, "again_after": 120.0, "carry_for": 30.0}
    observation["on_errands"] = fields.get("on_errands", [])
    return observation


def fetches(observation: dict[str, Any]) -> list[str]:
    """The IDs of the bring-a-drink options a guest is offered, whichever family holds them."""
    options = build_candidates(observation)
    return [item["id"] for option in options for item in option.get("members", [option])
            if item["verb"] == "bring_drink"]


@pytest.mark.parametrize("observation, expected", [
    pytest.param(at_the_table(), ["bring_drink:bea"], id="a-tablemate-with-empty-hands"),
    pytest.param(at_the_table([person("bea"), person("cid", seat_id="n")]), ["bring_drink:bea", "bring_drink:cid"],
                 id="each-tablemate"),
    pytest.param(at_the_table([person("dan", seat_id=None, table_id=None, beside=True)]), ["bring_drink:dan"],
                 id="someone-standing-beside"),
    pytest.param(at_the_table(beer=1), ["bring_drink:bea"], id="one-hand-is-still-free"),
    pytest.param(at_the_table(tap=None), [], id="no-tap-known"),
    pytest.param(at_the_table(tap={**TAP, "stock": 0}), [], id="the-tap-ran-dry-when-last-seen"),
    pytest.param(at_the_table(beer=2), [], id="no-free-hand"),
    pytest.param(at_the_table([person("bea", holding={"beer": 1})]), [], id="the-tablemate-holds-a-mug"),
    pytest.param(at_the_table([person("cid", seat_id="fw", table_id="far")]), [], id="someone-at-another-table"),
    pytest.param(at_the_table([person("hob", post="Bar")]), [], id="the-barkeep-needs-no-drink-brought"),
    pytest.param(at_the_table(on_errands=["ada"]), [], id="the-guest-is-already-on-an-errand"),
    pytest.param(at_the_table(on_errands=["bea"]), [], id="the-tablemate-is-already-being-served"),
    pytest.param(at_the_table(closed=True), [], id="the-inn-has-closed"),
    pytest.param(at_the_table([]), [], id="nobody-in-sight"),
])
def test_a_guest_is_offered_to_bring_a_drink_to_someone_with_empty_hands_if_they_could(
        observation: dict[str, Any], expected: list[str]) -> None:
    assert fetches(observation) == expected


def score(observation: dict[str, Any]) -> float:
    concrete = [item for option in build_candidates(observation) for item in option.get("members", [option])]
    return local_scores(observation, concrete)["bring_drink:bea"]


def test_a_guest_is_warmer_to_a_trip_for_someone_they_like() -> None:
    assert score(at_the_table(opinion=-10.0)) < score(at_the_table(opinion=60.0))


def test_a_sociable_guest_makes_the_trip_more_readily() -> None:
    quiet, warm = at_the_table(), at_the_table()
    quiet["actor"]["traits"]["sociability"], warm["actor"]["traits"]["sociability"] = 0.1, 0.9
    assert score(quiet) < score(warm)


@pytest.mark.parametrize("need", [pytest.param("bladder", id="a-full-bladder"), pytest.param("fatigue", id="weariness")])
def test_a_pressing_need_of_their_own_outweighs_the_trip(need: str) -> None:
    pressed = at_the_table()
    pressed["actor"]["needs"][need] = 90
    assert score(pressed) < score(at_the_table())


def test_a_trip_is_low_on_its_own_and_always_a_score() -> None:
    best = at_the_table(opinion=100.0)
    best["actor"]["traits"]["sociability"] = 1.0
    assert 0.0 <= score(at_the_table(opinion=-100.0)) <= score(best) < 0.6


def test_a_trip_is_told_with_the_tap_the_receiver_and_the_way_out() -> None:
    assert option_text(at_the_table(), command("bring_drink", "bea")) == (
        "fetch a mug of ale from the tap and bring it to Bea, who sits at their table with nothing in their hands "
        "(it takes a trip, and Bea may refuse it if there is bad blood between them)")


def test_jev_is_told_who_the_drink_is_for() -> None:
    assert "bring it to 'bea'" in asked_about(command("bring_drink", "bea"))


def fetching() -> dict[str, Any]:
    """Ada and Bea sit at the near table and Ada knows the tap; nobody has decided anything."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    know(world, "ada", "tap")
    return world


def test_bringing_a_drink_runs_as_an_errand_and_ends_in_the_receivers_hand() -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea")) == {"accepted": True, "reason": None}
    advance(world, 1)
    assert events(world, "fetch_begun") == ["Ada went to fetch Bea an ale"]
    advance_until(world, lambda world: holds_a_mug(world, "bea"))
    assert (actor(world, "ada")["inventory"]["beer"], events(world, "gave")[0],
            [item["kind"] for item in actor(world, "bea")["thoughts"] if item["about"] == "ada"]) == (
        0, "Ada gave Bea a mug of ale", ["treated"])
    advance_until(world, the_errand_ends)


def test_the_one_brought_a_drink_may_still_refuse_it() -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    advance(world, 1)  # the errand opens when the choice has run its half second
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -60.0, "familiarity": "acquaintance",
                                               "knows_name": True}
    advance_until(world, the_errand_ends, limit=60.0)
    assert (len(events(world, "gift_refused")), events(world, "invitation_failed"), actor(world, "ada")["inventory"]["beer"],
            actor(world, "bea")["inventory"]["beer"]) == (2, [], 1, 0)


@pytest.mark.parametrize("target, reason", [
    pytest.param("cid", "Visitors must sit at one table or stand side by side", id="at-another-table"),
    pytest.param("ada", "Choose another visitor to bring a drink to", id="oneself"),
    pytest.param("nobody", "Choose another visitor to bring a drink to", id="unknown-person"),
    pytest.param(None, "Choose another visitor to bring a drink to", id="no-target"),
])
def test_a_drink_is_brought_only_to_someone_within_reach(target: str | None, reason: str) -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", target)) == {"accepted": False, "reason": reason}


def test_a_guest_with_both_hands_full_cannot_bring_a_drink() -> None:
    world = fetching()
    actor(world, "ada")["inventory"]["beer"] = 2
    assert start_action(world, "ada", command("bring_drink", "bea")) == {
        "accepted": False, "reason": "Ada has no free hand for another mug"}


@pytest.mark.parametrize("asker, target, reason", [
    pytest.param("ada", "cid", "Ada is already on an errand", id="the-guest-is-on-one"),
    pytest.param("cid", "bea", "Bea is already on an errand", id="the-receiver-is-on-one"),
])
def test_nobody_is_sent_on_a_second_errand_while_on_one(asker: str, target: str, reason: str) -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    # Cid joins the near table, so the refusal is about the errand and not the distance.
    know(world, "cid", "tap")
    assert start_action(world, "cid", command("sit", "n"))["accepted"]
    advance(world, 6)
    assert start_action(world, asker, command("bring_drink", target)) == {"accepted": False, "reason": reason}


def test_the_briefing_tells_the_host_what_they_are_fetching_and_the_receiver_nothing() -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    advance(world, 1)

    def situation(actor_id: str) -> str:
        from tavern.hall.world import observe_people
        return brief({**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}, [])["situation"]
    assert ("They are fetching Bea an ale." in situation("ada"), "ale" in situation("bea").split("Needs")[0]) == (True, False)


def test_an_errand_without_an_invitation_survives_a_save() -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    advance_until(world, holds_a_mug)
    loaded = parse_world(json.dumps(world))
    assert loaded == world
    advance_until(loaded, lambda world: holds_a_mug(world, "bea"))


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: world["invitations"][0].update(unasked="yes"), id="unasked-not-a-flag"),
    pytest.param(lambda world: world["invitations"][0].update(unasked=1), id="unasked-a-number"),
])
def test_a_damaged_errand_in_a_save_is_rejected(damage: Callable[[dict[str, Any]], Any]) -> None:
    world = fetching()
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    advance(world, 1)
    damage(world)
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))


def test_the_observation_names_those_on_errands() -> None:
    world = fetching()
    assert observe_actor(world, "ada")["on_errands"] == []
    assert start_action(world, "ada", command("bring_drink", "bea"))["accepted"]
    advance(world, 1)
    assert observe_actor(world, "cid")["on_errands"] == ["ada", "bea"]
