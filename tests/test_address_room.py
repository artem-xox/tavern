"""The goal to address the room: a goal without a person, open while the hall has a stage."""

from typing import Any

import pytest

from tavern.hall.world import observe_actor, observe_people
from tavern.mind.goals import check_goal, open_alone, serving, settle_goals
from tavern.mind.intentions import parse_stance
from dice_hall import advance, guest, start, table_hall, who

ANSWER = {"thought": "I must speak.", "intention": "Tell them all.", "goal": "address_room", "target": None}


def minded(at: float = 0.0, **fields: Any) -> dict[str, Any]:
    """The hall where Ada, at the stage, holds the goal to address the room, written at a game time."""
    world = table_hall(guest("ada", (16, 9), card={"persona": "A loud showman"}, **fields), guest("bea", (15, 7)))
    who(world, "ada")["intention"] = {
        "thought": "Hm.", "intention": "Speak.", "goal": {"kind": "address_room", "target": None, "status": "active"},
        "written_at": at, "trigger": {"kind": "arrival", "text": "Ada came in", "time": at}}
    return world


def test_the_stage_opens_the_goal_to_address_the_room() -> None:
    world = minded()
    assert open_alone(world, who(world, "ada")) == ["address_room"]


def test_a_hall_without_a_stage_cannot_carry_it_out() -> None:
    world = minded()
    world["map"]["objects"] = [item for item in world["map"]["objects"] if item["kind"] != "stage"]
    assert open_alone(world, who(world, "ada")) == []


def test_the_mind_may_set_it_with_no_person() -> None:
    goal = parse_stance(ANSWER, {"bea": "Bea"}, alone=["address_room"])["goal"]
    assert goal == {"kind": "address_room", "target": None, "status": "active"}


@pytest.mark.parametrize("answer, alone", [
    pytest.param({**ANSWER, "target": "bea"}, ["address_room"], id="a-person-is-named"),
    pytest.param(ANSWER, [], id="no-stage"),
])
def test_a_malformed_address_goal_is_refused(answer: dict[str, Any], alone: list[str]) -> None:
    with pytest.raises(ValueError):
        parse_stance(answer, {"bea": "Bea"}, alone=alone)


def test_a_goal_with_a_person_is_refused_without_one() -> None:
    with pytest.raises(ValueError):
        check_goal("talk_to", None, {"bea": "Bea"})


def test_giving_the_speech_serves_the_goal_and_waiting_does_not() -> None:
    world = minded()
    ada = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
    assert serving(ada, {"id": "give_speech:stage", "verb": "give_speech", "target_id": "stage"})
    assert not serving(ada, {"id": "wait", "verb": "wait", "target_id": None})


@pytest.mark.parametrize("speak, seconds, status", [
    pytest.param(True, 8, "done", id="the-speech-was-given"),
    pytest.param(False, 250, "expired", id="nobody-got-up"),
    pytest.param(False, 5, "active", id="still-time"),
])
def test_the_goal_is_done_when_the_log_shows_the_speech(speak: bool, seconds: float, status: str) -> None:
    world = minded()
    if speak:
        assert start(world, "ada", "give_speech", "stage")["accepted"]
    advance(world, seconds)
    settle_goals(world)
    assert who(world, "ada")["intention"]["goal"]["status"] == status


def test_an_ordinary_guest_has_no_wish_to_address_the_room() -> None:
    world = table_hall(guest("ada", (16, 9)))
    assert open_alone(world, who(world, "ada")) == []
