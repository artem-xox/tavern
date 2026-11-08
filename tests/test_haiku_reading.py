"""Haiku's reading of a player's line: the question it is asked, and the boundary that parses its answer."""

import asyncio
from typing import Any

import pytest

from tavern.mind.haiku_reading import RejectedReading, claude_reader, parse_reading, reading_question
from tavern.mind.haiku_turns import turn_question
from tavern.mind.turn_view import turn_view
from tavern.social.scenes import conversation_of
from test_haiku_turns import scene_world

TEXT = "Salt is cheaper in the south, Bea, and you know it."
GOOD = {"act": "small_talk", "addressee": "Bea", "topic": "salt prices", "invitation": None, "fact_id": None}


def played_view() -> dict[str, Any]:
    """The view of Ada, the played guest, in her talk with Bea."""
    world = scene_world()
    return turn_view(world, conversation_of(world, "ada"), "ada")


def test_the_question_shares_the_writers_cached_prefix_and_adds_reading_rules() -> None:
    view = played_view()
    question = reading_question(view, TEXT, "auto")
    assert question["system"][0] == turn_question(view)["system"][0]
    assert len(question["system"]) == 2


@pytest.mark.parametrize("to", [
    pytest.param("auto", id="auto"),
    pytest.param("everyone", id="everyone"),
    pytest.param("bea", id="a-guest"),
])
def test_the_question_holds_the_text_and_the_offered_acts(to: str) -> None:
    view = played_view()
    content = reading_question(view, TEXT, to)["content"]
    assert TEXT in content
    assert all(act in content for act in view["acts"])


def test_who_it_is_to_changes_the_question() -> None:
    view = played_view()
    contents = {to: reading_question(view, TEXT, to)["content"] for to in ("auto", "everyone", "bea")}
    assert len(set(contents.values())) == 3


def test_the_question_never_shows_anyones_internal_id() -> None:
    view = played_view()
    news = [{"id": "fact-7", "topic": "the tap", "told_as": "The tap is by the wall.", "heard_from": None,
             "confidence": 0.9}]
    view["speaker"]["news"] = news
    content = reading_question(view, TEXT, "bea")["content"]
    assert "fact-7" in content  # News is named by its fact_id: the reading must say which one it tells.
    assert all(f'"{actor}"' not in content for actor in ("ada", "bea"))


def test_the_schema_enumerates_what_the_view_offers() -> None:
    view = {**played_view(), "invitations": ["dice_together"]}
    view["speaker"] = {**view["speaker"], "news": [{"id": "f1", "topic": "t", "told_as": "w", "heard_from": None,
                                                    "confidence": 0.9}]}
    properties = reading_question(view, TEXT, "auto")["schema"]["properties"]
    assert properties["act"]["enum"] == list(view["acts"])
    assert {"type": "string", "enum": ["Bea"]} in properties["addressee"]["anyOf"]
    assert {"type": "string", "enum": ["dice_together"]} in properties["invitation"]["anyOf"]
    assert {"type": "string", "enum": ["f1"]} in properties["fact_id"]["anyOf"]


def test_the_schema_offers_no_invitation_or_news_when_there_is_none() -> None:
    view = {**played_view(), "invitations": []}
    properties = reading_question(view, TEXT, "auto")["schema"]["properties"]
    assert (properties["invitation"]["type"], properties["fact_id"]["type"]) == ("null", "null")


@pytest.mark.parametrize("answer, expected", [
    pytest.param(GOOD, {"act": "small_talk", "addressee": "bea", "topic": "salt prices"}, id="as-asked"),
    pytest.param({**GOOD, "addressee": None}, {"act": "small_talk", "addressee": None, "topic": "salt prices"},
                 id="to-everyone"),
    pytest.param({**GOOD, "addressee": "bea"}, {"act": "small_talk", "addressee": "bea", "topic": "salt prices"},
                 id="a-stray-id-still-means-its-guest"),
])
def test_a_sound_answer_is_parsed_into_a_reading(answer: dict[str, Any], expected: dict[str, Any]) -> None:
    assert parse_reading(played_view(), TEXT, answer) == expected


@pytest.mark.parametrize("answer", [
    pytest.param("small_talk", id="not-an-object"),
    pytest.param({}, id="empty"),
    pytest.param({**GOOD, "act": "dance"}, id="unknown-act"),
    pytest.param({**GOOD, "act": "insult"}, id="act-not-offered-now"),
    pytest.param({**GOOD, "addressee": "Zed"}, id="addressee-outside"),
    pytest.param({**GOOD, "topic": " "}, id="empty-topic"),
    pytest.param({**GOOD, "topic": "t" * 61}, id="long-topic"),
    pytest.param({**GOOD, "act": "invite"}, id="invite-without-kind"),
    pytest.param({**GOOD, "line": "Words of its own."}, id="a-line-of-its-own"),
])
def test_a_malformed_answer_is_rejected(answer: Any) -> None:
    with pytest.raises(RejectedReading):
        parse_reading(played_view(), TEXT, answer)


def test_the_reader_asks_once_and_returns_the_parsed_reading() -> None:
    asked: list[Any] = []

    async def ask(question: Any) -> dict[str, Any]:
        asked.append(question)
        return GOOD
    reading = asyncio.run(claude_reader(ask)(played_view(), TEXT, "auto"))
    assert (len(asked), reading["act"], reading["addressee"]) == (1, "small_talk", "bea")
