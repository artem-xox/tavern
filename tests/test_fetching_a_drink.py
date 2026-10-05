"""A drink bought for someone is carried to them, not handed across the room: the errand's walk back and its ends."""

import json
from collections.abc import Callable
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.rules import default_rules
from tavern.hall.world import start_action
from social_hall import actor, advance, command, know, say, seated_talk

SAME_TABLE = "Visitors must sit at one table or stand side by side"


def bought_for_bea() -> dict[str, Any]:
    """Ada, who knows the tap, has invited Bea, her tablemate, to an ale on her, and Bea has said yes."""
    world = seated_talk()
    know(world, "ada", "tap")
    say(world, "invite", "Shall we?", invitation="buy_drink")
    say(world, "accept", "Gladly.")
    return world


def advance_until(world: dict[str, Any], reached: Callable[[dict[str, Any]], bool], limit: float = 40.0) -> None:
    """Advance a tenth of a second at a time until something is true, or fail after `limit` seconds."""
    for _ in range(round(limit * 10)):
        if reached(world):
            return
        advance(world, 0.1)
    raise AssertionError(f"Not reached within {limit} s: {[item['message'] for item in world['events'][-6:]]}")


def holds_a_mug(world: dict[str, Any], actor_id: str = "ada") -> bool:
    return actor(world, actor_id)["inventory"]["beer"] > 0


def events(world: dict[str, Any], kind: str) -> list[str]:
    return [item["message"] for item in world["events"] if item["type"] == kind]


def the_errand_ends(world: dict[str, Any]) -> bool:
    return world["invitations"] == []


def test_the_host_walks_back_with_the_mug_and_hands_it_over_at_the_table() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    assert (actor(world, "bea")["inventory"]["beer"], [item["stage"] for item in world["invitations"]]) == (0, ["carrying"])
    advance_until(world, lambda world: holds_a_mug(world, "bea"))
    assert (actor(world, "ada")["inventory"]["beer"], events(world, "gave")[:1]) == (0, ["Ada gave Bea a mug of ale"])
    advance_until(world, the_errand_ends)


def test_a_drink_that_is_carried_is_still_a_treat() -> None:
    world = bought_for_bea()
    advance_until(world, lambda world: holds_a_mug(world, "bea"))
    assert [item["kind"] for item in actor(world, "bea")["thoughts"] if item["about"] == "ada"] == ["treated"]


def test_the_host_keeps_the_mug_in_hand_until_they_are_beside_the_invitee() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    # The tap is across the hall: the host is not near the invitee yet, and the mug has not left their hand.
    assert start_action(world, "ada", {"id": "give:beer:bea", "verb": "give", "target_id": "bea",
                                       "item": "beer"}) == {"accepted": False, "reason": SAME_TABLE}


def leaves(world: dict[str, Any]) -> None:
    know(world, "bea", "door")
    assert start_action(world, "bea", command("leave", "door"))["accepted"]


def stands_at_the_darts(world: dict[str, Any]) -> None:
    assert start_action(world, "bea", command("play_darts", "darts"))["accepted"]


def holds_two_mugs(world: dict[str, Any]) -> None:
    actor(world, "bea")["inventory"]["beer"] = 2


def thinks_ill_of_ada(world: dict[str, Any]) -> None:
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -60.0, "familiarity": "acquaintance",
                                               "knows_name": True}


@pytest.mark.parametrize("change", [
    pytest.param(leaves, id="the-invitee-goes-home"),
    pytest.param(stands_at_the_darts, id="the-invitee-stays-at-the-darts-past-the-wait"),
    pytest.param(holds_two_mugs, id="the-invitees-hands-are-full"),
])
def test_an_errand_that_cannot_hand_the_mug_over_fails_and_the_host_keeps_it(change: Callable[[dict[str, Any]], None]) -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    change(world)
    advance_until(world, the_errand_ends, limit=60.0)
    assert (len(events(world, "invitation_failed")), actor(world, "ada")["inventory"]["beer"], events(world, "gave")) == (
        1, 1, [])


def test_an_invitee_who_thinks_ill_of_the_host_may_still_refuse_the_mug() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    thinks_ill_of_ada(world)
    advance_until(world, the_errand_ends, limit=60.0)
    assert (events(world, "gift_refused")[:1], events(world, "invitation_failed"), actor(world, "ada")["inventory"]["beer"],
            actor(world, "bea")["inventory"]["beer"]) == (["Bea would not take a mug of ale from Ada"], [], 1, 0)


def test_a_host_who_no_longer_holds_the_mug_ends_the_errand_in_failure() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    actor(world, "ada")["inventory"]["beer"] = 0  # drunk or spilt on the way
    advance_until(world, the_errand_ends)
    assert (len(events(world, "invitation_failed")), actor(world, "bea")["inventory"]["beer"]) == (1, 0)


def test_the_wait_for_the_invitee_is_the_rules_carry_for() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    stands_at_the_darts(world)
    since = world["time"]
    advance_until(world, the_errand_ends, limit=60.0)
    assert world["time"] - since == pytest.approx(world["rules"]["giving"]["carry_for"], abs=3.0)


def test_the_carry_for_rule_defaults_to_half_a_minute() -> None:
    assert default_rules()["giving"]["carry_for"] == 30.0


def test_an_errand_under_way_survives_a_save_and_is_finished_after_it() -> None:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    loaded = parse_world(json.dumps(world))
    assert loaded == world
    advance_until(loaded, lambda world: holds_a_mug(world, "bea"))
    assert actor(loaded, "ada")["inventory"]["beer"] == 0


def damaged(damage: Callable[[dict[str, Any]], Any]) -> str:
    world = bought_for_bea()
    advance_until(world, holds_a_mug)
    damage(world)
    return json.dumps(world)


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: world["invitations"][0].pop("since"), id="carrying-without-a-start"),
    pytest.param(lambda world: world["invitations"][0].update(since=-1.0), id="start-before-the-evening"),
    pytest.param(lambda world: world["invitations"][0].update(since="soon"), id="start-not-a-time"),
    pytest.param(lambda world: world["invitations"][0].update(since=world["time"] + 5), id="start-in-the-future"),
    pytest.param(lambda world: world["invitations"][0].update(stage="accepted"), id="a-start-before-carrying-began"),
    pytest.param(lambda world: world["rules"]["giving"].pop("carry_for"), id="no-carry-for-rule"),
    pytest.param(lambda world: world["rules"]["giving"].update(carry_for=0), id="carry-for-zero"),
    pytest.param(lambda world: world["rules"]["giving"].update(carry_for="long"), id="carry-for-not-a-number"),
])
def test_a_damaged_errand_or_rule_in_a_save_is_rejected(damage: Callable[[dict[str, Any]], Any]) -> None:
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(damaged(damage))
