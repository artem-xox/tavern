"""Sobchak's microphone: whom it offers an interview, the scene it opens, and what the interviewee takes from it (S2-19)."""

from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.options import option_text
from tavern.social.scenes import conversation_of
from social_hall import actor, advance, command, spotted_hall


def evening(microphone: int = 1) -> dict[str, Any]:
    """Ada sits at the near table with a microphone; Cid and Dan sit at the far one; the others stand."""
    world = create_world(spotted_hall(), 4)
    actor(world, "ada")["inventory"]["microphone"] = microphone
    for guest, chair in (("ada", "w"), ("cid", "fw"), ("dan", "fe")):
        assert start_action(world, guest, command("sit", chair))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    return world


def seen(world: dict[str, Any], who: str = "ada") -> dict[str, Any]:
    return {**observe_actor(world, who), "people": observe_people(world, who)}


def interviews(view: dict[str, Any]) -> list[str]:
    options = build_candidates(view)
    return sorted(member["id"] for option in options for member in option.get("members", [option])
                  if member["verb"] == "interview_guest")


@pytest.mark.parametrize("microphone, expected", [
    pytest.param(1, ["interview_guest:cid"], id="a-carrier-walks-up-to-the-far-table"),
    pytest.param(0, [], id="no-microphone-no-interview"),
])
def test_a_microphone_offers_an_interview_wherever_a_walk_over_is_offered(microphone: int, expected: list[str]) -> None:
    assert interviews(seen(evening(microphone))) == expected


def test_the_option_names_the_interviewee() -> None:
    view = seen(evening())
    assert "Cid" in option_text(view, {"verb": "interview_guest", "target_id": "cid"})


def interview(opinion: float | None = None, who: str = "cid") -> dict[str, Any]:
    """Ada walks over to the far table and interviews Cid, whose opinion of her is as given."""
    world = evening()
    if opinion is not None:
        actor(world, who)["relations"]["ada"] = {"name": "Ada", "opinion": opinion, "familiarity": "acquaintance"}
    assert start_action(world, "ada", command("interview_guest", who)) == {"accepted": True, "reason": None}
    advance(world, 6)
    return world


def test_arriving_opens_a_conversation_whose_topic_is_the_interview() -> None:
    scene = conversation_of(interview(), "ada")
    assert (scene["participants"], scene["topic"]) == (["ada", "cid"], "Ada's microphone interview of Cid")


def test_arriving_at_a_table_already_talking_joins_it_and_keeps_its_topic() -> None:
    world = evening()
    assert start_action(world, "cid", command("talk", "dan"))["accepted"]
    topic = conversation_of(world, "cid")["topic"]
    assert start_action(world, "ada", command("interview_guest", "cid"))["accepted"]
    advance(world, 6)
    assert (conversation_of(world, "ada")["participants"], conversation_of(world, "ada")["topic"]) == (
        ["cid", "dan", "ada"], topic)


@pytest.mark.parametrize("opinion, thought", [
    pytest.param(30.0, "interviewed", id="a-friend-enjoys-it"),
    pytest.param(0.0, "interviewed", id="a-neutral-guest-enjoys-it"),
    pytest.param(-30.0, "grilled", id="a-foe-feels-grilled"),
])
def test_the_interviewee_takes_it_by_how_they_regard_the_interviewer(opinion: float, thought: str) -> None:
    held = [(item["kind"], item["about"]) for item in actor(interview(opinion), "cid")["thoughts"]
            if item["kind"] in ("interviewed", "grilled")]
    assert held == [(thought, "ada")]


def test_one_interview_is_one_logged_act() -> None:
    acts = [item for item in interview()["events"] if item["type"] == "signature_act"]
    assert [(item["verb"], item["item"], item["subject"], item["message"]) for item in acts] == [
        ("interview_guest", "microphone", ["cid"], "Ada sticks a microphone in Cid's face")]


def test_the_world_refuses_an_interview_without_a_microphone() -> None:
    world = evening(microphone=0)
    assert start_action(world, "ada", command("interview_guest", "cid"))["reason"] == "No microphone in inventory"
