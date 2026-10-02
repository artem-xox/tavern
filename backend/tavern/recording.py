"""Model calls kept as JSON-line records, to replay an evening and to price it."""

from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
import hashlib
import json
import math
from typing import Any, TypedDict, cast

from tavern.agents import Action, Evaluator

# A metered evaluator answers like an Evaluator and also returns the token usage its provider
# reported for the call, or None when it reported none (see `jev.evaluate_actions_metered`).
Metered = Callable[[Mapping[str, Any], Sequence[Action], Mapping[str, Any]],
                   Awaitable[tuple[dict[str, float], Mapping[str, int] | None]]]


class Record(TypedDict):
    """One model call, as a line of a recording.

    `kind` names the call (`actions`, `seats` and `family` are Jev's; a new model adds its own kind) and
    `key` hashes kind and request. `request` is what the model was asked, never credentials;
    `response` is its answer (Jev: scores by candidate ID), or None after a failure whose
    message is `error`. `usage` holds the provider's token counters, None when it reported
    none, and `latency` the wall-clock seconds the call took.
    """

    kind: str
    key: str
    request: dict[str, Any]
    response: Any
    error: str | None
    usage: dict[str, int] | None
    latency: float


class KindCost(TypedDict):
    """The calls of one kind: counts, reported tokens, and their cost in USD."""

    calls: int
    failures: int
    missing_usage: int
    input_tokens: int
    output_tokens: int
    usd: float


def request_key(kind: str, request: Mapping[str, Any]) -> str:
    """Identify a call so a replay finds its recorded answer.

    Args:
        kind: Call kind.
        request: What the model is asked.

    Returns:
        SHA-256 hex digest of the kind and the request as JSON with sorted keys.

    Raises:
        TypeError: The request is not JSON data.
        ValueError: The request holds NaN or infinity.
    """
    text = json.dumps({"kind": kind, "request": request}, sort_keys=True, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _request(observation: Mapping[str, Any], candidates: Sequence[Action]) -> dict[str, Any]:
    # Stored as plain JSON data, so a record compares equal to itself read back from its file.
    return json.loads(json.dumps({"observation": observation, "candidates": list(candidates)}, allow_nan=False))


def _record(kind: str, request: dict[str, Any], response: Any, error: str | None,
            usage: Mapping[str, int] | None, latency: float) -> Record:
    return {"kind": kind, "key": request_key(kind, request), "request": request, "response": response,
            "error": error, "usage": None if usage is None else dict(usage), "latency": latency}


def record_calls(kind: str, evaluate: Metered, keep: Callable[[Record], None], clock: Callable[[], float],
                 recoverable: type[Exception]) -> Evaluator:
    """Wrap a metered evaluator so every call is kept as a record.

    Args:
        kind: Call kind written into each record.
        evaluate: Metered evaluator that answers the calls.
        keep: Receives each record as soon as its call ends, e.g. a JSON-lines writer.
        clock: Monotonic seconds for measuring latency, e.g. `time.monotonic`.
        recoverable: Failure a decision falls back from (`JevError` for Jev); it is recorded,
            then raised again.

    Returns:
        An evaluator that answers as `evaluate` does.
    """
    async def recorded(observation: Mapping[str, Any], candidates: Sequence[Action],
                       config: Mapping[str, Any]) -> dict[str, float]:
        request, started = _request(observation, candidates), clock()
        try:
            scores, usage = await evaluate(observation, candidates, config)
        except recoverable as error:
            keep(_record(kind, request, None, str(error), None, clock() - started))
            raise
        keep(_record(kind, request, scores, None, usage, clock() - started))
        return scores
    return recorded


def replay_calls(kind: str, records: Sequence[Record], recoverable: type[Exception]) -> Evaluator:
    """Answer calls from a recording instead of a model.

    Args:
        kind: Call kind to answer; records of other kinds are not used.
        records: Recorded calls in the order they were made.
        recoverable: Failure type a recorded error is raised as.

    Returns:
        An evaluator returning the recorded scores of an identical request; identical
        requests get their recorded answers in order. The evaluator raises LookupError for a
        request without an unused recorded answer, ValueError when recorded scores do not
        score exactly the requested candidates on 0–1, and `recoverable` for a recorded failure.
    """
    answers: dict[str, deque[Record]] = {}
    for record in records:
        if record["kind"] == kind:
            answers.setdefault(record["key"], deque()).append(record)

    async def replayed(observation: Mapping[str, Any], candidates: Sequence[Action],
                       config: Mapping[str, Any]) -> dict[str, float]:
        key = request_key(kind, _request(observation, candidates))
        if not answers.get(key):
            raise LookupError(f"No recorded {kind} call is left for request {key}")
        record = answers[key].popleft()
        if record["error"] is not None:
            raise recoverable(record["error"])
        return _scores(record["response"], candidates)
    return replayed


def _scores(response: Any, candidates: Sequence[Action]) -> dict[str, float]:
    if not isinstance(response, Mapping) or set(response) != {action["id"] for action in candidates} or any(
            isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1
            for score in response.values()):
        raise ValueError(f"Recorded scores do not fit the requested candidates: {response!r}")
    return dict(response)


def format_record(record: Record) -> str:
    """Write a record as one JSON line.

    Args:
        record: Recorded call.

    Returns:
        JSON with sorted keys and a closing newline.

    Raises:
        ValueError: The record holds NaN or infinity.
    """
    return json.dumps(record, sort_keys=True, allow_nan=False) + "\n"


def parse_records(text: str) -> list[Record]:
    """Read a JSON-lines recording.

    Args:
        text: File contents, one record per line.

    Returns:
        Records in file order; empty text gives none.

    Raises:
        ValueError: A line is not a valid record; the message names its line number.
    """
    records = []
    for number, line in enumerate(text.splitlines(), 1):
        try:
            records.append(_parse_record(json.loads(line)))
        except ValueError as error:
            raise ValueError(f"Recording line {number}: {error}") from error
    return records


def _parse_record(data: Any) -> Record:
    if not isinstance(data, dict) or set(data) != set(Record.__annotations__):
        raise ValueError(f"a record has exactly the fields {', '.join(sorted(Record.__annotations__))}")
    if not isinstance(data["kind"], str) or not data["kind"]:
        raise ValueError("kind must be a nonempty string")
    if not isinstance(data["request"], dict) or data["key"] != request_key(data["kind"], data["request"]):
        raise ValueError("key does not match the kind and request")
    if data["error"] is not None and not isinstance(data["error"], str):
        raise ValueError("error must be text or null")
    if data["error"] is None and data["response"] is None:
        raise ValueError("a call without an error must have a response")
    _check_measures(data["usage"], data["latency"])
    return cast(Record, data)


def _check_measures(usage: Any, latency: Any) -> None:
    counted = isinstance(usage, dict) and {"input_tokens", "output_tokens"} <= set(usage) and all(
        isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in usage.values())
    if usage is not None and not counted:
        raise ValueError("usage must be null or nonnegative token counts with input and output tokens")
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or not 0 <= latency < math.inf:
        raise ValueError("latency must be a nonnegative number of seconds")


def cost_by_kind(records: Sequence[Record], input_usd_per_million: float) -> dict[str, KindCost]:
    """Sum calls, tokens and cost per call kind.

    Args:
        records: Recorded calls.
        input_usd_per_million: USD tariff per million input tokens. Every kind recorded so far
            is a Jev call, and Jev output tokens are free.

    Returns:
        Per kind, in name order: calls, failed calls, answered calls without reported usage,
        reported input and output tokens, and the unrounded cost in USD.

    Raises:
        ValueError: The price is negative or not finite.
    """
    if not 0 <= input_usd_per_million < math.inf:
        raise ValueError(f"Input price must be a nonnegative USD amount, not {input_usd_per_million!r}")
    summary: dict[str, KindCost] = {}
    for record in sorted(records, key=lambda item: item["kind"]):
        kind = summary.setdefault(record["kind"], {"calls": 0, "failures": 0, "missing_usage": 0,
                                                    "input_tokens": 0, "output_tokens": 0, "usd": 0.0})
        # Calls without reported usage add no tokens; `missing_usage` says how many there were.
        usage = record["usage"] or {"input_tokens": 0, "output_tokens": 0}
        kind["calls"] += 1
        kind["failures"] += record["error"] is not None
        kind["missing_usage"] += record["error"] is None and record["usage"] is None
        kind["input_tokens"] += usage["input_tokens"]
        kind["output_tokens"] += usage["output_tokens"]
        kind["usd"] = kind["input_tokens"] / 1_000_000 * input_usd_per_million
    return summary
