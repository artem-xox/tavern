"""Recap: an evening's moments and talk laid out as a question for a storyteller, and its answer checked."""

import asyncio
from typing import Any

import pytest

from tavern.evening.recap import MAX_LINES, MAX_TEXT, parse_recap, recap_question, retell
from tavern.evening.story_score import WEIGHTS, story_moments, story_score


def event(kind: str, message: str, time: float = 65.0) -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": "ada", "type": kind, "message": message}


def question(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the recap question of an event log."""
    return dict(recap_question(events, story_score(story_moments(events), WEIGHTS)))


def lines_of(events: list[dict[str, Any]]) -> list[str]:
    """The event lines in the question's content."""
    return [line for line in question(events)["content"].splitlines() if line.startswith("[")]


@pytest.mark.parametrize("events, expected", [
    pytest.param([event("quarrel", "Ada quarreled with Bram")], ["[01:05] Ada quarreled with Bram"],
                 id="a-moment-with-its-time-as-minutes-and-seconds"),
    pytest.param([event("turn", "Ada to Bram (greet): Well met", 3.0), event("quarrel", "Ada quarreled with Bram", 9.0)],
                 ["[00:03] Ada to Bram (greet): Well met", "[00:09] Ada quarreled with Bram"], id="talk-and-moments-in-order"),
    pytest.param([event("action_completed", "Ada completed sit")], [],
                 id="bookkeeping-events-are-not-story"),
    pytest.param([event("quarrel", "Ada quarreled with Bram"), event("quarrel", "Ada quarreled with Bram")],
                 ["[01:05] Ada quarreled with Bram"], id="duplicate-participant-events-tell-once"),
])
def test_the_question_tells_what_happened_in_order(events: list[dict[str, Any]], expected: list[str]) -> None:
    padded = events + [event("arrival", "Cai came in", 99.0)]
    assert lines_of(padded)[:-1] == expected


def test_the_question_gives_the_score_counts() -> None:
    content = question([event("fight_started", "Ada and Bram came to blows")])["content"]
    assert "fight: 1" in content and "quarrel: 0" in content


def test_every_moment_stays_when_the_talk_is_thinned() -> None:
    talk = [event("turn", f"Ada to Bram (chat): line {number}", float(number)) for number in range(3 * MAX_LINES)]
    moment = event("fight_started", "Ada and Bram came to blows", 77.5)
    told = lines_of([*talk, moment])
    assert len(told) <= MAX_LINES and "[01:17] Ada and Bram came to blows" in told


def test_the_question_asks_for_a_title_and_a_text() -> None:
    asked = question([event("dozed_off", "Ada fell asleep at the table")])
    assert asked["schema"]["required"] == ["title", "text"] and asked["max_tokens"] > 0 and asked["system"]


def test_an_empty_log_has_nothing_to_tell() -> None:
    with pytest.raises(ValueError, match="nothing to retell"):
        question([])


@pytest.mark.parametrize("answer, expected", [
    pytest.param({"title": "The Night of Dice 🎲", "text": "Ada won. 🍺"}, {"title": "The Night of Dice 🎲", "text": "Ada won. 🍺"},
                 id="valid"),
    pytest.param({"title": "  Padded  ", "text": " Story. "}, {"title": "Padded", "text": "Story."}, id="trimmed"),
])
def test_a_good_recap_is_accepted(answer: dict[str, Any], expected: dict[str, str]) -> None:
    assert parse_recap(answer) == expected


@pytest.mark.parametrize("answer", [
    pytest.param({}, id="empty-answer"),
    pytest.param({"title": "T"}, id="no-text"),
    pytest.param({"text": "S"}, id="no-title"),
    pytest.param({"title": "", "text": "S"}, id="empty-title"),
    pytest.param({"title": "T", "text": "   "}, id="blank-text"),
    pytest.param({"title": "T", "text": 7}, id="text-not-a-string"),
    pytest.param({"title": "T", "text": "S", "moral": "x"}, id="unknown-key"),
    pytest.param({"title": "T", "text": "x" * (MAX_TEXT + 1)}, id="too-long"),
    pytest.param(["title", "text"], id="not-an-object"),
])
def test_a_malformed_recap_is_rejected(answer: Any) -> None:
    with pytest.raises(ValueError):
        parse_recap(answer)


def storyteller(answer: Any) -> Any:
    """A fake storyteller port that answers with the given object, and keeps the questions it was asked."""
    asked: list[Any] = []

    async def ask(put: Any) -> Any:
        asked.append(put)
        return answer
    ask.asked = asked  # type: ignore[attr-defined]
    return ask


def test_the_evening_is_retold_by_the_storyteller() -> None:
    events = [event("quarrel", "Ada quarreled with Bram")]
    ask = storyteller({"title": "Tonight 🍺", "text": "They quarreled. 😡"})
    assert asyncio.run(retell(events, story_score(story_moments(events), WEIGHTS), ask)) == {"title": "Tonight 🍺",
                                                                                        "text": "They quarreled. 😡"}
    assert len(ask.asked) == 1


def test_a_retelling_the_storyteller_breaks_the_rules_of_is_rejected() -> None:
    events = [event("quarrel", "Ada quarreled with Bram")]
    with pytest.raises(ValueError, match="title and a text"):
        asyncio.run(retell(events, story_score(story_moments(events), WEIGHTS), storyteller({"story": "x"})))
