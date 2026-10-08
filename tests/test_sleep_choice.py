"""The fork of a tired guest: sleep in their seat or go home, offered, refused without a seat, and weighed."""

from typing import Any

import pytest

from tavern.body.activities import FAMILIES
from tavern.hall.world import create_world, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.local_policy import local_scores
from tavern.mind.options import family_text, option_text
from hostile_view import person, view
from social_hall import command, hall


def tired(fatigue: float, **fields: Any) -> dict[str, Any]:
    """Ada, seated at the near table with Bea, with a given weariness."""
    observation = view(None, [person("bea")], **fields)
    observation["actor"]["needs"]["fatigue"] = fatigue
    return observation


def verbs(observation: dict[str, Any]) -> list[str]:
    """The verbs of every concrete option a guest is offered, whichever family holds them."""
    return [item["verb"] for option in build_candidates(observation) for item in option.get("members", [option])]


@pytest.mark.parametrize("observation, offered", [
    pytest.param(tired(60.0), True, id="tired-enough"),
    pytest.param(tired(59.0), False, id="just-rested-enough"),
    pytest.param(tired(95.0, on_errands=["ada"]), False, id="out-on-an-errand"),
    pytest.param(tired(95.0, closed=True), False, id="the-inn-has-closed"),
])
def test_a_seated_tired_guest_may_choose_to_sleep(observation: dict[str, Any], offered: bool) -> None:
    assert ("doze" in verbs(observation)) is offered


def test_a_guest_without_a_seat_is_not_offered_sleep() -> None:
    observation = tired(95.0)
    observation["actor"]["seat_id"] = None
    assert "doze" not in verbs(observation)


def test_sleep_and_sitting_are_one_wish_so_no_first_stage_request_grows() -> None:
    options = build_candidates(tired(90.0))
    family = next(option for option in options if option["id"] == "resting")
    assert (sorted(item["verb"] for item in family["members"]), len([o for o in options if o["id"] == "resting"])) == (
        ["doze", "sit"], 1)


@pytest.mark.parametrize("seated, reason", [
    pytest.param(True, None, id="in-a-seat-at-a-table"),
    pytest.param(False, "This needs a seat at a table", id="standing"),
])
def test_sleeping_needs_a_seat_at_a_table(seated: bool, reason: str | None) -> None:
    world = create_world(hall(), 4)
    if seated:
        assert start_action(world, "ada", command("sit", "w"))["accepted"]
    assert start_action(world, "ada", command("doze")).get("reason") == reason


def choice(fatigue: float, drunkenness: float, seconds: float, beers: int = 3) -> dict[str, float]:
    """Local scores of sleeping, sitting on and going home, for a guest seated `seconds` into the evening."""
    observation = view(None, [], drunkenness=drunkenness)
    observation["actor"].update(visit={"seconds": seconds, "beers": beers})
    observation["actor"]["needs"]["fatigue"] = fatigue
    observation["objects"].append({"id": "door", "kind": "door", "x": 0, "y": 7, "reserved_by": None,
                                   "interaction_spots": [[0, 6]]})
    actions = [command("doze"), command("sit", "w"), command("leave", "door")]
    scores = local_scores(observation, actions)
    return {action["verb"]: scores[action["id"]] for action in actions}


@pytest.mark.parametrize("fatigue, drunkenness, seconds, best", [
    pytest.param(85.0, 0.8, 300.0, "doze", id="tired-and-wasted-sleeps-where-they-sit"),
    pytest.param(90.0, 0.0, 300.0, "leave", id="tired-and-sober-goes-home-to-bed"),
    pytest.param(70.0, 0.0, 20.0, "sit", id="tired-on-arrival-sits-down-first"),
])
def test_a_tired_guest_weighs_sleep_against_going_home(fatigue: float, drunkenness: float, seconds: float,
                                                       best: str) -> None:
    scores = choice(fatigue, drunkenness, seconds)
    assert max(scores, key=lambda verb: scores[verb]) == best


@pytest.mark.parametrize("drunkenness", [pytest.param(0.0, id="sober"), pytest.param(0.9, id="wasted")])
def test_drink_makes_sleep_likelier(drunkenness: float) -> None:
    sober, drunk = choice(80.0, 0.0, 300.0)["doze"], choice(80.0, drunkenness, 300.0)["doze"]
    assert (drunk > sober) is (drunkenness > 0)


def test_a_rested_guest_has_no_wish_to_sleep() -> None:
    assert choice(20.0, 0.0, 300.0)["doze"] == 0.0


def test_the_option_says_what_sleeping_means() -> None:
    sentence = option_text(tired(90.0), {"id": "doze", "verb": "doze", "target_id": None})
    assert all(words in sentence for words in ("sleep", "their seat", "loud noise will wake them"))


def test_the_resting_wish_names_sleep() -> None:
    assert "sleep" in FAMILIES["resting"]
    options = build_candidates(tired(90.0))
    assert "sleep" in family_text(tired(90.0), next(option for option in options if option["id"] == "resting"))
