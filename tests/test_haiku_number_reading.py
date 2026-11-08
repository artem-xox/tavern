"""Haiku's reading of the player's number on the stage: the question it is asked, and the boundary that parses it."""

import asyncio
from typing import Any

import pytest

from tavern.mind.haiku_reading import (RejectedReading, claude_number_reader, number_question, parse_number,
                                       reading_question)
from tavern.social.numbers import NUMBERS
from tavern.social.stage_lines import number_view
from test_haiku_reading import played_view
from test_stage_lines import on_stage

TEXT = "Cid, you charlatan, you sold this hall a roof it never had!"


def stage_view() -> dict[str, Any]:
    """What a model is shown of Ada on the stage, with Cid in the hall."""
    world = on_stage()
    return number_view(world, next(item for item in world["actors"] if item["id"] == "ada"))


def test_the_question_shares_the_line_readers_blocks_and_adds_the_number_rules() -> None:
    question = number_question(stage_view(), TEXT)
    line_reading = reading_question(played_view(), "Hello.", "auto")
    assert (question["system"][0] == line_reading["system"][0], len(question["system"])) == (True, 2)


def test_the_question_holds_the_text_every_kind_and_the_people_in_the_hall() -> None:
    content = number_question(stage_view(), TEXT)["content"]
    assert [item for item in (TEXT, "Cid", *NUMBERS) if item not in content] == []


def test_the_schema_enumerates_the_kinds_and_the_people_of_the_view() -> None:
    properties = number_question(stage_view(), TEXT)["schema"]["properties"]
    assert (properties["number"]["enum"], properties["target"]["anyOf"][0]["enum"]) == (list(NUMBERS), ["Cid"])


@pytest.mark.parametrize("answer, reading", [
    pytest.param({"number": "roast", "target": "Cid"}, {"number": "roast", "target": "cid"}, id="an-aimed-number"),
    pytest.param({"number": "pitch", "target": None}, {"number": "pitch", "target": None}, id="a-pitch"),
])
def test_an_answer_in_the_documented_shape_is_read_with_the_id_of_its_target(
        answer: dict[str, Any], reading: dict[str, Any]) -> None:
    assert parse_number(stage_view(), answer) == reading


@pytest.mark.parametrize("answer", [
    pytest.param({"number": "sermon", "target": None}, id="an-unknown-kind"),
    pytest.param({"number": "roast", "target": None}, id="an-aimed-kind-without-a-target"),
    pytest.param({"number": "pitch", "target": "Cid"}, id="a-pitch-with-a-target"),
    pytest.param({"number": "roast", "target": "Nobody"}, id="a-target-not-in-the-hall"),
    pytest.param({"number": "roast"}, id="a-field-missing"),
    pytest.param({"number": "roast", "target": "Cid", "act": "boast"}, id="a-field-too-many"),
    pytest.param(["roast", "Cid"], id="not-an-object"),
])
def test_a_malformed_answer_is_rejected(answer: Any) -> None:
    with pytest.raises(RejectedReading):
        parse_number(stage_view(), answer)


def test_the_reader_asks_once_and_checks_the_answer() -> None:
    asked: list[Any] = []

    async def ask(question: Any) -> dict[str, Any]:
        asked.append(question)
        return {"number": "toast", "target": "Cid"}
    reading = asyncio.run(claude_number_reader(ask)(stage_view(), TEXT))
    assert (reading, len(asked)) == ({"number": "toast", "target": "cid"}, 1)
