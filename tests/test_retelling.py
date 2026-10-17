"""Retelling: an evening's moments and talk laid out for a storyteller, whose cited chapters are checked."""

import asyncio
from typing import Any

import pytest

from tavern.evening.retelling import MAX_CHAPTERS, MAX_CHAPTER_TEXT, MAX_LINES, parse_retelling, retell, retelling_question, told
from tavern.evening.story_score import WEIGHTS, story_moments, story_score


def event(kind: str, message: str, time: float = 65.0, actor_id: str = "ada") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


def score(events: list[dict[str, Any]]) -> Any:
    """The story score of an event log."""
    return story_score(story_moments(events), WEIGHTS)


def lines_of(events: list[dict[str, Any]]) -> list[str]:
    """The event lines in the question's content."""
    return [line for line in retelling_question(events, score(events))["content"].splitlines() if line.startswith("[")]


def chapter(text: str = "Ada dozed off. 💤", cites: Any = (0,)) -> dict[str, Any]:
    """Build a chapter as the storyteller answers it."""
    return {"text": text, "events": list(cites)}


def answer(*chapters: dict[str, Any], title: str = "A Night 🍺") -> dict[str, Any]:
    """Build the storyteller's answer."""
    return {"title": title, "chapters": list(chapters)}


@pytest.mark.parametrize("events, expected", [
    pytest.param([event("quarrel", "Ada quarreled with Bram")], ["[#0 01:05] Ada quarreled with Bram"],
                 id="a-moment-with-its-position-in-the-log-and-its-time"),
    pytest.param([event("turn", "Ada to Bram (greet): Well met", 3.0), event("quarrel", "Ada quarreled with Bram", 9.0)],
                 ["[#0 00:03] Ada to Bram (greet): Well met", "[#1 00:09] Ada quarreled with Bram"],
                 id="talk-and-moments-in-order"),
    pytest.param([event("action_completed", "Ada completed sit"), event("quarrel", "Ada quarreled with Bram")],
                 ["[#1 01:05] Ada quarreled with Bram"], id="bookkeeping-events-are-not-story-but-keep-the-ids-of-the-log"),
    pytest.param([event("quarrel", "Ada quarreled with Bram"), event("quarrel", "Ada quarreled with Bram")],
                 ["[#0 01:05] Ada quarreled with Bram"], id="duplicate-participant-events-tell-once"),
])
def test_the_question_tells_what_happened_with_ids(events: list[dict[str, Any]], expected: list[str]) -> None:
    assert lines_of(events) == expected


def test_the_talk_around_a_moment_comes_before_the_rest() -> None:
    far = [event("turn", f"Ada to Bram (chat): far {number}", float(number)) for number in range(2 * MAX_LINES)]
    near = [event("turn", "Ada to Bram (greet): near", 500.0), event("quarrel", "Ada quarreled with Bram", 501.0),
            event("turn", "Ada to Bram (apologize): sorry", 502.0)]
    shown = [line.split("] ", 1)[1] for line in lines_of([*far, *near])]
    assert len(shown) <= MAX_LINES
    assert {"Ada to Bram (greet): near", "Ada quarreled with Bram", "Ada to Bram (apologize): sorry"} <= set(shown)


def test_every_moment_stays_when_the_talk_is_thinned() -> None:
    talk = [event("turn", f"Ada to Bram (chat): line {number}", float(number)) for number in range(3 * MAX_LINES)]
    moment = event("fight_started", "Ada and Bram came to blows", 77.5)
    shown = lines_of([*talk, moment])
    assert len(shown) <= MAX_LINES and f"[#{3 * MAX_LINES} 01:17] Ada and Bram came to blows" in shown


def test_the_question_gives_the_score_counts() -> None:
    events = [event("fight_started", "Ada and Bram came to blows")]
    content = retelling_question(events, score(events))["content"]
    assert "fight: 1" in content and "quarrel: 0" in content


def test_the_question_asks_for_chapters_that_cite_events() -> None:
    events = [event("dozed_off", "Ada fell asleep at the table")]
    asked = retelling_question(events, score(events))
    chapters = asked["schema"]["properties"]["chapters"]["items"]
    assert asked["schema"]["required"] == ["title", "chapters"] and chapters["required"] == ["text", "events"]
    assert asked["max_tokens"] > 0 and asked["system"]


def test_a_rejected_answer_is_named_in_the_second_question() -> None:
    events = [event("dozed_off", "Ada fell asleep at the table")]
    again = retelling_question(events, score(events), "chapter 2 cites #99, which is not in the list")
    assert "chapter 2 cites #99" in again["content"]


def test_an_empty_log_has_nothing_to_tell() -> None:
    with pytest.raises(ValueError, match="nothing to retell"):
        retelling_question([], score([]))


def test_told_lines_are_keyed_by_their_position_in_the_log() -> None:
    events = [event("action_completed", "x"), event("dozed_off", "Ada fell asleep at the table")]
    assert told(events) == {1: events[1]}


@pytest.mark.parametrize("given, expected", [
    pytest.param(answer(chapter()), {"title": "A Night 🍺", "chapters": [{"text": "Ada dozed off. 💤", "events": [0],
                                                                         "actors": ["ada"]}]}, id="one-cited-chapter"),
    pytest.param(answer(chapter(" Padded. ", [0]), title="  T  "), {"title": "T", "chapters": [
        {"text": "Padded.", "events": [0], "actors": ["ada"]}]}, id="trimmed"),
    pytest.param(answer(chapter("Two of them.", [1, 0, 1])), {"title": "A Night 🍺", "chapters": [
        {"text": "Two of them.", "events": [1, 0], "actors": ["bram", "ada"]}]},
        id="duplicate-citations-once-and-the-faces-in-order-of-citing"),
])
def test_a_cited_retelling_is_accepted(given: Any, expected: dict[str, Any]) -> None:
    shown = {0: event("dozed_off", "Ada dozed", actor_id="ada"), 1: event("quarrel", "Bram quarreled", actor_id="bram")}
    assert parse_retelling(given, shown) == expected


def test_an_event_without_an_actor_has_no_face() -> None:
    shown = {0: {**event("last_call", "Hob called out"), "actor_id": None}}
    assert parse_retelling(answer(chapter(cites=[0])), shown)["chapters"][0]["actors"] == []


@pytest.mark.parametrize("bad", [
    pytest.param({}, id="empty-answer"),
    pytest.param(["title", "chapters"], id="not-an-object"),
    pytest.param({"title": "T"}, id="no-chapters"),
    pytest.param({"chapters": [chapter()]}, id="no-title"),
    pytest.param(answer(chapter(), title=""), id="empty-title"),
    pytest.param(answer(), id="empty-chapter-list"),
    pytest.param(answer(*[chapter()] * (MAX_CHAPTERS + 1)), id="too-many-chapters"),
    pytest.param(answer(chapter("   ")), id="blank-chapter-text"),
    pytest.param(answer(chapter(7)), id="chapter-text-not-a-string"),
    pytest.param(answer(chapter("x" * (MAX_CHAPTER_TEXT + 1))), id="chapter-too-long"),
    pytest.param(answer(chapter(cites=[])), id="chapter-cites-nothing"),
    pytest.param(answer(chapter(cites=[99])), id="chapter-cites-an-event-that-was-never-shown"),
    pytest.param(answer(chapter(cites=["0"])), id="citation-not-an-integer"),
    pytest.param(answer(chapter(cites=[True])), id="citation-a-boolean"),
    pytest.param(answer({"text": "x", "events": [0], "moral": "y"}), id="unknown-chapter-key"),
    pytest.param({**answer(chapter()), "moral": "y"}, id="unknown-answer-key"),
    pytest.param(answer("a chapter"), id="chapter-not-an-object"),
])
def test_a_retelling_that_breaks_the_rules_is_rejected(bad: Any) -> None:
    with pytest.raises(ValueError):
        parse_retelling(bad, {0: event("dozed_off", "Ada dozed")})


def teller(*answers: Any) -> Any:
    """A fake storyteller port: each call gives the next answer (an exception is raised); it keeps its questions."""
    asked: list[Any] = []

    async def ask(question: Any) -> Any:
        asked.append(question)
        given = answers[min(len(asked), len(answers)) - 1]
        if isinstance(given, Exception):
            raise given
        return given
    ask.asked = asked  # type: ignore[attr-defined]
    return ask


LOG = [event("dozed_off", "Ada fell asleep at the table"), event("quarrel", "Ada quarreled with Bram", actor_id="bram")]


def test_the_evening_is_retold_in_one_question_when_the_chapters_are_cited() -> None:
    ask = teller(answer(chapter(cites=[0]), chapter("Then a quarrel. 😡", [1])))
    told_story = asyncio.run(retell(LOG, score(LOG), ask))
    assert [item["events"] for item in told_story["chapters"]] == [[0], [1]] and len(ask.asked) == 1


def test_a_claim_without_an_event_is_asked_again_once() -> None:
    ask = teller(answer(chapter(cites=[99])), answer(chapter(cites=[1])))
    told_story = asyncio.run(retell(LOG, score(LOG), ask))
    assert told_story["chapters"][0]["events"] == [1] and len(ask.asked) == 2
    assert "#99" in ask.asked[1]["content"]


def test_after_the_second_try_only_the_cited_chapters_are_shown() -> None:
    ask = teller(answer(chapter(cites=[99])), answer(chapter("Made up. 🐉", [99]), chapter("Real. 💤", [0])))
    told_story = asyncio.run(retell(LOG, score(LOG), ask))
    assert [item["text"] for item in told_story["chapters"]] == ["Real. 💤"] and len(ask.asked) == 2


def test_a_storyteller_with_no_cited_chapter_left_tells_nothing() -> None:
    with pytest.raises(ValueError, match="cites"):
        asyncio.run(retell(LOG, score(LOG), teller(answer(chapter(cites=[99])))))


def test_the_storytellers_own_failure_is_not_hidden() -> None:
    with pytest.raises(RuntimeError, match="down"):
        asyncio.run(retell(LOG, score(LOG), teller(RuntimeError("down"))))
