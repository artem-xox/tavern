"""The Haiku stage writer: the cached prefix, the question per claim, and the answer checked at the boundary."""

import asyncio
from typing import Any

import pytest

from tavern.mind.haiku_stage import RejectedStage, claude_stage_writer, parse_stage, stage_question
from tavern.mind.stage_prompt import shared_prefix
from tavern.mind.world_now import WORLD_NOW
from tavern.social.stage_lines import stage_claims
from test_stage_lines import NUMBER, heckled, on_stage, performed


def view_of(make: Any, kind: str) -> dict[str, Any]:
    """The view of the claim of a kind waiting in a world."""
    return next(item["view"] for item in stage_claims(make()) if item["kind"] == kind)


def test_the_prefix_is_long_enough_to_cache_and_the_same_for_every_claim() -> None:
    # Haiku caches prefixes of 4096 tokens or more; the turn writer's 16,500 characters keep that margin.
    number, heckle = stage_question(view_of(on_stage, "number")), stage_question(view_of(performed, "heckle"))
    assert (len(shared_prefix()) >= 16_500, number["system"][0] == heckle["system"][0] == shared_prefix()) == (True, True)


@pytest.mark.parametrize("phrase", [
    pytest.param("satire with no brakes", id="the-tone"),
    pytest.param(WORLD_NOW, id="the-news-of-the-day"),
    pytest.param("The counter-charge", id="the-comic-moves"),
    pytest.param("toast", id="numbers"),
    pytest.param("heckle", id="heckles"),
    pytest.param("comeback", id="comebacks"),
])
def test_the_prefix_shares_the_world_and_teaches_the_stage(phrase: str) -> None:
    assert phrase in shared_prefix()


@pytest.mark.parametrize("make, kind, phrases", [
    pytest.param(on_stage, "number", ["You are Ada", "a pitch to the whole room", "Cid", "2 or 3 lines"], id="a-number"),
    pytest.param(performed, "heckle", ["You are Cid", "Ada", NUMBER[0], "one line"], id="a-heckle"),
    pytest.param(heckled, "comeback", ["You are Ada", "Cid", "Sit down, you fraud!", "one line"], id="a-comeback"),
])
def test_the_question_names_the_speaker_the_room_and_the_task(make: Any, kind: str, phrases: list[str]) -> None:
    question = stage_question(view_of(make, kind))
    assert [phrase for phrase in phrases if phrase not in question["content"]] == []


def test_the_card_is_the_second_cached_block() -> None:
    assert "A loud showman" in stage_question(view_of(on_stage, "number"))["system"][1]


@pytest.mark.parametrize("make, kind, answer", [
    pytest.param(on_stage, "number", {"lines": NUMBER}, id="a-number-of-two-lines"),
    pytest.param(on_stage, "number", {"lines": ["One.", "Two.", "Three."]}, id="a-number-of-three"),
    pytest.param(performed, "heckle", {"lines": ["Sit down!"]}, id="a-heckle-of-one"),
    # Live seeds 1 and 5 (2026-10-25): every line over the first limit of 120 was a good one of 122-155 characters.
    pytest.param(performed, "heckle", {"lines": ["x" * 155]}, id="a-long-shout-a-bubble-cuts-in-pieces"),
])
def test_an_answer_in_the_documented_shape_passes(make: Any, kind: str, answer: dict[str, Any]) -> None:
    assert parse_stage(view_of(make, kind), answer) == answer["lines"]


@pytest.mark.parametrize("make, kind, answer", [
    pytest.param(on_stage, "number", {"lines": ["Only one."]}, id="a-number-too-short"),
    pytest.param(on_stage, "number", {"lines": ["1.", "2.", "3.", "4."]}, id="a-number-too-long"),
    pytest.param(performed, "heckle", {"lines": ["Sit down!", "And stay down!"]}, id="a-heckle-of-two"),
    pytest.param(on_stage, "number", {"lines": ["*bows* Friends!", "Hello."]}, id="a-stage-direction"),
    pytest.param(on_stage, "number", {"lines": ["x" * 161, "Hello."]}, id="a-line-over-160-characters"),
    pytest.param(on_stage, "number", {"lines": ["", "Hello."]}, id="a-blank-line"),
    pytest.param(on_stage, "number", {"lines": NUMBER, "act": "boast"}, id="a-field-too-many"),
    pytest.param(on_stage, "number", ["Friends!", "Hello."], id="not-an-object"),
])
def test_a_malformed_answer_is_rejected(make: Any, kind: str, answer: Any) -> None:
    with pytest.raises(RejectedStage):
        parse_stage(view_of(make, kind), answer)


def test_the_writer_asks_once_and_checks_the_answer() -> None:
    asked: list[Any] = []

    async def ask(question: Any) -> dict[str, Any]:
        asked.append(question)
        return {"lines": NUMBER}
    lines = asyncio.run(claude_stage_writer(ask)(view_of(on_stage, "number"), {}))
    assert (lines, len(asked)) == (NUMBER, 1)
