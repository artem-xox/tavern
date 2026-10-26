"""Speeches in an evening: how many were given, and how the room took them."""

from typing import Any

import pytest

from tavern.evening.speech_metrics import speech_counts, stage_counts
from tavern.evening.story_score import WEIGHTS, story_moments, story_score
from dice_hall import advance, guest, start, table_hall


def event(kind: str, message: str, time: float = 1.0, actor_id: str = "ada") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


def test_a_speech_is_a_story_moment_weighted_between_a_quarrel_and_a_fight() -> None:
    moments = story_moments([event("gave_speech", 'Ada gave a speech: "Hear me!"')])
    assert [item["moment"] for item in moments] == ["speech"]
    assert WEIGHTS["gift"] < WEIGHTS["speech"] < WEIGHTS["fight"]
    assert story_score(moments, WEIGHTS)["score"] == WEIGHTS["speech"]


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"speeches": 0, "speakers": [], "admired": 0, "groaned": 0}, id="no-speeches"),
    pytest.param([event("gave_speech", "Ada gave a speech"), event("speech_reaction", "Ada's speech: 3 admired it, 1 groaned")],
                 {"speeches": 1, "speakers": ["ada"], "admired": 3, "groaned": 1}, id="one-speech"),
    pytest.param([event("gave_speech", "a", actor_id="ada"), event("gave_speech", "b", time=9.0, actor_id="ada"),
                  event("gave_speech", "c", time=5.0, actor_id="bea")],
                 {"speeches": 3, "speakers": ["ada", "bea"], "admired": 0, "groaned": 0}, id="two-speakers-one-twice"),
])
def test_speeches_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert speech_counts(events) == expected


def test_a_speech_in_the_hall_logs_how_it_was_taken() -> None:
    world = table_hall(guest("ada", (17, 9), card={"persona": "x"}, intention={"thought": "I must speak.", "intention": "Speak.", "goal": None, "written_at": 0.0, "trigger": {"kind": "arrival", "text": "x", "time": 0.0}, "obsession": 0}), guest("bea", (15, 7), traits={"sociability": 0.9}))
    assert start(world, "ada", "give_speech", "stage")["accepted"]
    advance(world, 8)
    assert speech_counts(world["events"]) == {"speeches": 1, "speakers": ["ada"], "admired": 1, "groaned": 0}


def number(kind: str | None, time: float = 1.0) -> dict[str, Any]:
    """A number given from the stage, of a kind (None for one logged before numbers had kinds)."""
    return {**event("gave_speech", "Ada gave a speech", time), **({"number": kind} if kind else {})}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"numbers": {}, "heckles": 0, "comebacks": 0, "fallbacks": 0}, id="no-stage-tonight"),
    pytest.param([number("roast"), event("stage_fallback", "Ada spoke scripted words: too long", 2.0)],
                 {"numbers": {"roast": 1}, "heckles": 0, "comebacks": 0, "fallbacks": 1}, id="scripted-words-counted"),
    pytest.param([number("roast"), event("heckled", "Bea heckled Ada", 3.0, "bea"),
                  event("heckle_answered", "Ada answered Bea", 5.0)],
                 {"numbers": {"roast": 1}, "heckles": 1, "comebacks": 1, "fallbacks": 0}, id="a-roast-heckled-and-answered"),
    pytest.param([number("toast"), number("toast", 90.0), number("confession", 200.0)],
                 {"numbers": {"toast": 2, "confession": 1}, "heckles": 0, "comebacks": 0, "fallbacks": 0}, id="kinds-counted-apart"),
    # Before S2-14 every speech addressed the room with the speaker's own cause.
    pytest.param([number(None)], {"numbers": {"pitch": 1}, "heckles": 0, "comebacks": 0, "fallbacks": 0}, id="an-old-log-was-pitches"),
])
def test_numbers_heckles_and_comebacks_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert stage_counts(events) == expected


def test_a_heckle_is_a_story_moment_worth_a_gift_and_less_than_the_number() -> None:
    moments = story_moments([event("heckled", 'Bea heckled Ada: "Sit down!"', actor_id="bea")])
    assert ([item["moment"] for item in moments], WEIGHTS["gift"] <= WEIGHTS["heckle"] < WEIGHTS["speech"]) == (
        ["heckle"], True)
