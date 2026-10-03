"""Intentions in the evening metrics: how many were written or failed, and what their calls cost."""

from collections.abc import Sequence
from typing import Any

import pytest

from tavern.lockstep import Evening
from tavern.metrics import evening_metrics, intention_counts
from tavern.recording import Record, Tariff, request_key

HAIKU = Tariff(input=1.0, output=5.0, cache_read=0.10, cache_write=1.25)


def event(kind: str, actor_id: str = "ada", time: float = 1.0) -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": f"{actor_id}: {kind}"}


def night(events: Sequence[dict[str, Any]]) -> Evening:
    """A finished one-guest evening with no decisions."""
    return Evening(list(events), [], [], ["ada"], 100.0)


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"written": 0, "failed": 0}, id="empty"),
    pytest.param([event("intention")], {"written": 1, "failed": 0}, id="single"),
    pytest.param([event("intention"), event("intention")], {"written": 2, "failed": 0}, id="duplicates"),
    pytest.param([event("intention"), event("intention_failed", "bea"), event("turn")],
                 {"written": 1, "failed": 1}, id="mixed-with-other-events"),
])
def test_intentions_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert intention_counts(night(events)) == expected


def test_malformed_event_fails_loudly() -> None:
    with pytest.raises(KeyError):
        intention_counts(night([{"time": 1.0, "message": "no type"}]))


def asked(usage: dict[str, int]) -> Record:
    """A recorded intention call."""
    request = {"system": ["prefix", "card"], "content": "moment", "schema": {"type": "object"}, "max_tokens": 250}
    return {"kind": "intention", "key": request_key("intention", request), "request": request,
            "response": {"thought": "Hm.", "intention": "Go."}, "error": None, "usage": usage, "latency": 1.2}


def test_intention_calls_are_priced_with_their_own_tariff() -> None:
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 1_000_000,
             "cache_creation_input_tokens": 0}
    metrics = evening_metrics(night([event("intention")]), [asked(usage), asked(usage)], 0.042, 3.0,
                              {"intention": HAIKU})
    cost = metrics["cost"]["intention"]
    assert (cost["calls"], cost["cache_read_input_tokens"], cost["usd"]) == (2, 2_000_000, pytest.approx(3.2))
