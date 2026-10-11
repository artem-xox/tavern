"""Claude calls are recorded, replayed and priced like Jev calls, with cache reads and writes."""

import asyncio
from collections.abc import Callable, Sequence
from itertools import count
import json
from typing import Any

import pytest

from tavern.adapters.claude import HAIKU_4_5, HAIKU_5_5, ClaudeError
from tavern.mind.questions import Question
from tavern.evening.recording import (Record, Tariff, cost_by_kind, format_record, parse_records, record_questions,
                              replay_questions, request_key)

USAGE = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 4000,
         "cache_creation_input_tokens": 0}


def question(content: str = "Ada's card text") -> Question:
    """A small card question."""
    return Question(system=["Rules."], content=content, schema={"type": "object"}, max_tokens=100)


def answering(usage: dict[str, int] = USAGE) -> Callable[..., Any]:
    """A fake metered Claude whose answer changes with every call, like a sampling model."""
    calls = count(1)

    async def ask(asked: Question) -> Any:
        return {"temper": round(1 / next(calls), 3)}, usage
    return ask


async def refusing(asked: Question) -> Any:
    """Fail like the Claude adapter does on a refusal."""
    raise ClaudeError("Claude stopped early: refusal")


def ticking() -> Callable[[], float]:
    """A fake clock that advances a quarter second per reading."""
    readings = count(0.0, 0.25)
    return lambda: next(readings)


def record(questions: Sequence[Question]) -> tuple[list[Record], list[dict[str, Any]]]:
    """Ask a recorded fake once per question; return the records and the answers the caller got."""
    records: list[Record] = []
    ask = record_questions("card", answering(), records.append, ticking(), ClaudeError)
    return records, [asyncio.run(ask(item)) for item in questions]


@pytest.mark.parametrize("questions", [
    pytest.param([], id="empty-no-calls"),
    pytest.param([question()], id="single-call"),
    pytest.param([question(), question()], id="duplicate-questions"),
])
def test_every_question_is_kept_as_a_record(questions: list[Question]) -> None:
    records, answers = record(questions)
    assert records == [{"kind": "card", "key": request_key("card", dict(item)), "request": dict(item),
                        "response": answer, "error": None, "usage": USAGE, "latency": 0.25}
                       for item, answer in zip(questions, answers)]


def test_failed_question_is_recorded_and_still_raised() -> None:
    records: list[Record] = []
    with pytest.raises(ClaudeError, match="refusal"):
        asyncio.run(record_questions("card", refusing, records.append, ticking(), ClaudeError)(question()))
    with pytest.raises(ClaudeError, match="^Claude stopped early: refusal$"):
        asyncio.run(replay_questions("card", records, ClaudeError)(question()))


@pytest.mark.parametrize("questions", [
    pytest.param([], id="empty-recording"),
    pytest.param([question()], id="single-call"),
    pytest.param([question(), question(), question()], id="duplicates-answer-in-recorded-order"),
    pytest.param([question("Ada"), question("Bea")], id="distinct-questions"),
])
def test_replay_answers_like_the_recording(questions: list[Question]) -> None:
    records, answers = record(questions)
    ask = replay_questions("card", parse_records("".join(map(format_record, records))), ClaudeError)
    assert [asyncio.run(ask(item)) for item in questions] == answers


@pytest.mark.parametrize("asked, kind, response", [
    pytest.param([question("Bea")], "card", None, id="question-never-recorded"),
    pytest.param([question(), question()], "card", None, id="duplicate-beyond-the-recording"),
    pytest.param([question()], "turn", None, id="same-question-of-another-kind"),
])
def test_replay_of_an_unrecorded_question_fails_loudly(asked: list[Question], kind: str, response: Any) -> None:
    records, _answers = record([question()])
    ask = replay_questions(kind, records, ClaudeError)
    with pytest.raises(LookupError, match="recorded"):
        for item in asked:
            asyncio.run(ask(item))


def test_replay_rejects_a_recorded_answer_that_is_not_an_object() -> None:
    records, _answers = record([question()])
    with pytest.raises(ValueError, match="answer"):
        asyncio.run(replay_questions("card", [{**records[0], "response": [1]}], ClaudeError)(question()))


def call(kind: str, usage: dict[str, int] | None, error: str | None = None) -> Record:
    """Build a recorded call with the given usage, for costing."""
    request = dict(question())
    return {"kind": kind, "key": request_key(kind, request), "request": request,
            "response": None if error else {"temper": 0.5}, "error": error, "usage": usage, "latency": 0.5}


def tokens(inputs: int, outputs: int, reads: int, writes: int) -> dict[str, int]:
    """Claude usage counters."""
    return {"input_tokens": inputs, "output_tokens": outputs, "cache_read_input_tokens": reads,
            "cache_creation_input_tokens": writes}


def claude_cost(calls: int, failures: int, missing: int, used: dict[str, int], usd: float) -> dict[str, Any]:
    """Build an expected cost summary of one Claude call kind."""
    return {"calls": calls, "failures": failures, "missing_usage": missing, **used, "usd": pytest.approx(usd)}


@pytest.mark.parametrize("records, expected", [
    pytest.param([], {}, id="empty-no-calls"),
    pytest.param([call("card", tokens(1_000_000, 0, 0, 0))], {"card": claude_cost(1, 0, 0, tokens(1_000_000, 0, 0, 0), 1.0)},
                 id="input"),
    pytest.param([call("card", tokens(0, 1_000_000, 0, 0))], {"card": claude_cost(1, 0, 0, tokens(0, 1_000_000, 0, 0), 5.0)},
                 id="output"),
    pytest.param([call("card", tokens(0, 0, 1_000_000, 0))], {"card": claude_cost(1, 0, 0, tokens(0, 0, 1_000_000, 0), 0.1)},
                 id="cache-read"),
    pytest.param([call("card", tokens(0, 0, 0, 1_000_000))],
                 {"card": claude_cost(1, 0, 0, tokens(0, 0, 0, 1_000_000), 1.25)}, id="cache-write"),
    pytest.param([call("card", tokens(100, 20, 4000, 0)), call("card", tokens(100, 20, 4000, 0))],
                 {"card": claude_cost(2, 0, 0, tokens(200, 40, 8000, 0), 0.0012)}, id="duplicate-calls-add-up"),
    pytest.param([call("card", None), call("card", None, error="Claude HTTP 529")],
                 {"card": claude_cost(2, 1, 1, tokens(0, 0, 0, 0), 0.0)}, id="failures-and-unreported-usage"),
])
def test_claude_calls_are_priced_by_their_tariff(records: list[Record], expected: dict[str, Any]) -> None:
    assert cost_by_kind(records, 0.042, {"card": HAIKU_4_5}) == expected


def test_jev_kinds_keep_their_input_price_beside_claude_kinds() -> None:
    jev = call("actions", {"input_tokens": 1_000_000, "output_tokens": 9})
    summary = cost_by_kind([jev, call("card", tokens(0, 1_000_000, 0, 0))], 0.042, {"card": HAIKU_4_5})
    assert (summary["actions"]["usd"], summary["card"]["usd"], "cache_read_input_tokens" in summary["actions"]) == (
        pytest.approx(0.042), pytest.approx(5.0), False)


@pytest.mark.parametrize("tariff", [
    pytest.param(Tariff(input=-1, output=5, cache_read=0.1, cache_write=1.25), id="negative-price"),
    pytest.param(Tariff(input=1, output=float("nan"), cache_read=0.1, cache_write=1.25), id="malformed-price"),
])
def test_invalid_claude_tariff_fails_loudly(tariff: Tariff) -> None:
    with pytest.raises(ValueError, match="price"):
        cost_by_kind([call("card", tokens(1, 1, 1, 1))], 0.042, {"card": tariff})


def test_records_never_hold_the_key() -> None:
    records, _answers = record([question()])
    assert "test-secret" not in json.dumps(records)


@pytest.mark.parametrize("used, usd", [
    pytest.param(tokens(1_000_000, 0, 0, 0), 0.10, id="input"),
    pytest.param(tokens(0, 1_000_000, 0, 0), 0.50, id="output"),
    pytest.param(tokens(0, 0, 1_000_000, 0), 0.01, id="cache-read"),
    pytest.param(tokens(0, 0, 0, 1_000_000), 0.125, id="cache-write"),
])
def test_haiku_5_5_calls_cost_a_tenth_of_haiku_4_5(used: dict[str, int], usd: float) -> None:
    assert cost_by_kind([call("turn", used)], 0.042, {"turn": HAIKU_5_5})["turn"]["usd"] == pytest.approx(usd)
