"""Recorded model calls: what a record keeps, how it replays, and what it costs."""

import asyncio
from collections.abc import Callable, Sequence
from itertools import count
import json
from typing import Any

import pytest

from tavern.jev import JevError
from tavern.recording import (Record, cost_by_kind, format_record, parse_records, record_calls, replay_calls,
                              request_key)

WAIT = [{"id": "wait", "verb": "wait", "target_id": None}]
CHOICES = [{"id": "wait", "verb": "wait", "target_id": None}, {"id": "inspect", "verb": "inspect", "target_id": None}]
SECRET = {"typesafe_api_key": "test-secret", "model": "jev-latest", "timeout": 2.0}


def view(name: str = "Ada") -> dict[str, Any]:
    """Build a small evaluator view of one guest."""
    return {"situation": f"{name} has just arrived.", "options": {"wait": "wait"}, "self": {"name": name}}


def scoring(usage: dict[str, int] | None = None) -> Callable[..., Any]:
    """Build a fake metered evaluator whose scores change with every call, like a sampling model."""
    calls = count(1)

    async def evaluate(observation: Any, candidates: Sequence[Any], config: Any) -> Any:
        turn = next(calls)
        return {action["id"]: round(1 / (turn + index), 3) for index, action in enumerate(candidates)}, usage
    return evaluate


async def timing_out(observation: Any, candidates: Any, config: Any) -> Any:
    """Fail like the Jev adapter does on a timeout."""
    raise JevError("Jev request timed out")


def ticking() -> Callable[[], float]:
    """A fake clock that advances a quarter second per reading."""
    readings = count(0.0, 0.25)
    return lambda: next(readings)


def record(views: Sequence[dict[str, Any]], usage: dict[str, int] | None = None,
           kind: str = "actions") -> tuple[list[Record], list[dict[str, float]]]:
    """Ask a recorded fake once per view; return the records and the scores the caller got."""
    records: list[Record] = []
    evaluate = record_calls(kind, scoring(usage), records.append, ticking(), JevError)
    scores = [asyncio.run(evaluate(item, CHOICES, SECRET)) for item in views]
    return records, scores


@pytest.mark.parametrize("left, right, same", [
    pytest.param(("actions", {"b": 1, "a": [1, 2]}), ("actions", {"a": [1, 2], "b": 1}), True,
                 id="key-order-does-not-matter"),
    pytest.param(("actions", {"a": 1}), ("seats", {"a": 1}), False, id="kind-is-part-of-the-key"),
    pytest.param(("actions", {"a": 1}), ("actions", {"a": 2}), False, id="request-is-part-of-the-key"),
    pytest.param(("actions", {}), ("actions", {}), True, id="empty-requests"),
])
def test_request_key_hashes_kind_and_canonical_request(
        left: tuple[str, dict[str, Any]], right: tuple[str, dict[str, Any]], same: bool) -> None:
    assert (request_key(*left) == request_key(*right), len(request_key(*left))) == (same, 64)


@pytest.mark.parametrize("views, usage", [
    pytest.param([], {"input_tokens": 9, "output_tokens": 1}, id="empty-no-calls"),
    pytest.param([view()], {"input_tokens": 9, "output_tokens": 1}, id="single-call"),
    pytest.param([view(), view()], {"input_tokens": 9, "output_tokens": 1}, id="duplicate-requests"),
    pytest.param([view("Ada"), view("Bea")], None, id="usage-not-reported"),
])
def test_every_call_is_kept_as_a_record(views: list[dict[str, Any]], usage: dict[str, int] | None) -> None:
    records, scores = record(views, usage)
    requests = [{"observation": item, "candidates": CHOICES} for item in views]
    assert records == [{"kind": "actions", "key": request_key("actions", request), "request": request,
                        "response": answer, "error": None, "usage": usage, "latency": 0.25}
                       for request, answer in zip(requests, scores)]
    assert "test-secret" not in json.dumps(records)


def test_failed_call_is_recorded_and_still_raised() -> None:
    records: list[Record] = []
    evaluate = record_calls("seats", timing_out, records.append, ticking(), JevError)
    with pytest.raises(JevError, match="timed out"):
        asyncio.run(evaluate(view(), WAIT, SECRET))
    assert [(item["kind"], item["response"], item["error"], item["usage"]) for item in records] == [
        ("seats", None, "Jev request timed out", None)]


@pytest.mark.parametrize("views", [
    pytest.param([], id="empty-recording"),
    pytest.param([view()], id="single-call"),
    pytest.param([view(), view(), view()], id="duplicates-answer-in-recorded-order"),
    pytest.param([view("Ada"), view("Bea")], id="distinct-requests"),
])
def test_replay_answers_like_the_recording_without_a_model(views: list[dict[str, Any]]) -> None:
    records, scores = record(views)
    evaluate = replay_calls("actions", parse_records("".join(map(format_record, records))), JevError)
    assert [asyncio.run(evaluate(item, CHOICES, {})) for item in views] == scores


def test_replayed_failure_raises_the_recorded_error() -> None:
    records: list[Record] = []
    with pytest.raises(JevError):
        asyncio.run(record_calls("actions", timing_out, records.append, ticking(), JevError)(view(), WAIT, SECRET))
    with pytest.raises(JevError, match="^Jev request timed out$"):
        asyncio.run(replay_calls("actions", records, JevError)(view(), WAIT, {}))


@pytest.mark.parametrize("asked, kind", [
    pytest.param([view("Bea")], "actions", id="request-never-recorded"),
    pytest.param([view(), view()], "actions", id="duplicate-beyond-the-recording"),
    pytest.param([view()], "seats", id="same-request-of-another-kind"),
])
def test_replay_of_an_unrecorded_request_fails_loudly(asked: list[dict[str, Any]], kind: str) -> None:
    records, _scores = record([view()])
    evaluate = replay_calls(kind, records, JevError)
    with pytest.raises(LookupError, match="recorded"):
        for item in asked:
            asyncio.run(evaluate(item, CHOICES, {}))


@pytest.mark.parametrize("response", [
    pytest.param({"wait": 0.5}, id="scores-for-other-candidates"),
    pytest.param({"wait": 0.5, "inspect": 1.5}, id="score-outside-the-rubric"),
    pytest.param({"wait": 0.5, "inspect": "high"}, id="malformed-score"),
])
def test_replay_rejects_recorded_scores_that_do_not_fit_the_request(response: dict[str, Any]) -> None:
    records, _scores = record([view()])
    with pytest.raises(ValueError, match="scores"):
        asyncio.run(replay_calls("actions", [{**records[0], "response": response}], JevError)(view(), CHOICES, {}))


@pytest.mark.parametrize("views", [
    pytest.param([], id="empty-file"),
    pytest.param([view()], id="single-line"),
    pytest.param([view(), view()], id="duplicate-lines"),
])
def test_records_survive_json_lines(views: list[dict[str, Any]]) -> None:
    records, _scores = record(views)
    text = "".join(format_record(item) for item in records)
    assert (parse_records(text), text.count("\n")) == (records, len(records))


def corrupt(change: Callable[[dict[str, Any]], Any]) -> Callable[[], str]:
    """Write one valid recorded call as a JSON line, then corrupt it."""
    def text() -> str:
        records, _scores = record([view()])
        line = json.loads(format_record(records[0]))
        change(line)
        return json.dumps(line) + "\n"
    return text


@pytest.mark.parametrize("text", [
    pytest.param(lambda: "not json\n", id="malformed-json"),
    pytest.param(lambda: "[]\n", id="not-an-object"),
    pytest.param(lambda: "\n", id="blank-line"),
    pytest.param(corrupt(lambda line: line.pop("latency")), id="missing-field"),
    pytest.param(corrupt(lambda line: line.update(extra=1)), id="unknown-field"),
    pytest.param(corrupt(lambda line: line.update(kind="")), id="empty-kind"),
    pytest.param(corrupt(lambda line: line["request"].update(candidates=[])), id="key-does-not-match-request"),
    pytest.param(corrupt(lambda line: line.update(latency=-1)), id="negative-latency"),
    pytest.param(corrupt(lambda line: line.update(usage={"input_tokens": "9", "output_tokens": 1})),
                 id="malformed-usage"),
    pytest.param(corrupt(lambda line: line.update(response=None)), id="answer-missing-without-error"),
    pytest.param(corrupt(lambda line: line.update(error=7)), id="malformed-error"),
])
def test_malformed_recordings_are_rejected(text: Callable[[], str]) -> None:
    with pytest.raises(ValueError, match="line 1"):
        parse_records(text())


def call(kind: str, input_tokens: int | None, output_tokens: int = 0, error: str | None = None) -> Record:
    """Build a recorded call with the given usage, for costing."""
    usage = None if input_tokens is None else {"input_tokens": input_tokens, "output_tokens": output_tokens}
    request = {"observation": {}, "candidates": WAIT}
    return {"kind": kind, "key": request_key(kind, request), "request": request,
            "response": None if error else {"wait": 1.0}, "error": error, "usage": usage, "latency": 0.5}


def cost(calls: int, failures: int, missing: int, tokens: tuple[int, int], usd: float) -> dict[str, Any]:
    """Build an expected cost summary of one call kind."""
    return {"calls": calls, "failures": failures, "missing_usage": missing,
            "input_tokens": tokens[0], "output_tokens": tokens[1], "usd": pytest.approx(usd)}


@pytest.mark.parametrize("records, expected", [
    pytest.param([], {}, id="empty-no-calls"),
    pytest.param([call("actions", 1_000_000, 500)], {"actions": cost(1, 0, 0, (1_000_000, 500), 0.042)},
                 id="single-call-output-is-free"),
    pytest.param([call("seats", 2_000), call("seats", 3_000)], {"seats": cost(2, 0, 0, (5_000, 0), 0.00021)},
                 id="duplicate-kind-adds-up"),
    pytest.param([call("seats", 10), call("actions", 20)],
                 {"actions": cost(1, 0, 0, (20, 0), 20 * 0.042e-6), "seats": cost(1, 0, 0, (10, 0), 10 * 0.042e-6)},
                 id="each-kind-separately"),
    pytest.param([call("actions", None), call("actions", None, error="Jev HTTP 500")],
                 {"actions": cost(2, 1, 1, (0, 0), 0.0)}, id="failures-and-unreported-usage-are-counted"),
])
def test_cost_is_summed_per_call_kind(records: list[Record], expected: dict[str, Any]) -> None:
    assert cost_by_kind(records, 0.042) == expected


@pytest.mark.parametrize("price", [
    pytest.param(-0.01, id="negative-price"),
    pytest.param(float("nan"), id="malformed-price"),
])
def test_invalid_tariff_fails_loudly(price: float) -> None:
    with pytest.raises(ValueError, match="price"):
        cost_by_kind([call("actions", 10)], price)
