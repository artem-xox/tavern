"""Measures of the turn writer over a headless evening: calls, latency, cache hits and cost per turn."""

from typing import Any

import pytest

from tavern.claude import HAIKU_4_5
from tavern.lockstep import Evening
from tavern.metrics import evening_metrics, writer_stats
from tavern.recording import Record, Tariff, request_key

USAGE = {"input_tokens": 500, "output_tokens": 40, "cache_read_input_tokens": 4500, "cache_creation_input_tokens": 0}
WRITE = {"input_tokens": 500, "output_tokens": 40, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 5000}


def turn_call(latency: float, usage: dict[str, int] | None = USAGE, error: str | None = None,
              kind: str = "turn") -> Record:
    """Build a recorded turn call."""
    request = {"content": f"turn after {latency}"}
    return {"kind": kind, "key": request_key(kind, request), "request": request,
            "response": None if error else {"line": "Aye."}, "error": error, "usage": None if error else usage,
            "latency": latency}


def evening(turns: int, failures: int = 0) -> Evening:
    """An evening log with spoken turns and failed ones."""
    events = [{"time": 1.0, "actor_id": "ada", "type": "turn", "message": "Ada to Bea (greet): Hi"}] * turns
    events += [{"time": 1.0, "actor_id": None, "type": "turn_failed", "message": "failed"}] * failures
    return Evening(events, [], [], ["ada"], 10.0)


def per_call(usage: dict[str, int]) -> float:
    """USD of one call with the given usage at Haiku 4.5 prices."""
    return (usage["input_tokens"] * 1.0 + usage["output_tokens"] * 5.0 + usage["cache_read_input_tokens"] * 0.1
            + usage["cache_creation_input_tokens"] * 1.25) / 1_000_000


@pytest.mark.parametrize("night, calls, expected", [
    pytest.param(evening(0), [], {"turns": 0, "fallbacks": 0, "calls": 0, "failures": 0, "latency_p50": None,
                                  "latency_p95": None, "cache_hit_rate": None, "usd": 0.0, "usd_per_turn": None},
                 id="empty-evening"),
    pytest.param(evening(1), [turn_call(0.8)],
                 {"turns": 1, "fallbacks": 0, "calls": 1, "failures": 0, "latency_p50": 0.8, "latency_p95": 0.8,
                  "cache_hit_rate": 0.9, "usd": per_call(USAGE), "usd_per_turn": per_call(USAGE)}, id="single-turn"),
    pytest.param(evening(2), [turn_call(1.0, WRITE), turn_call(1.0)],
                 {"turns": 2, "fallbacks": 0, "calls": 2, "failures": 0, "latency_p50": 1.0, "latency_p95": 1.0,
                  "cache_hit_rate": 4500 / 10500, "usd": per_call(WRITE) + per_call(USAGE),
                  "usd_per_turn": (per_call(WRITE) + per_call(USAGE)) / 2}, id="duplicate-latencies-cache-write"),
    pytest.param(evening(3, 1), [turn_call(0.5), turn_call(2.0, error="Claude HTTP 529"), turn_call(1.0),
                                 turn_call(9.0, kind="card")],
                 {"turns": 3, "fallbacks": 1, "calls": 3, "failures": 1, "latency_p50": 1.0, "latency_p95": 2.0,
                  "cache_hit_rate": 0.9, "usd": 2 * per_call(USAGE), "usd_per_turn": 2 * per_call(USAGE) / 3},
                 id="failure-and-other-kinds"),
    pytest.param(evening(1), [turn_call(0.5, None)],
                 {"turns": 1, "fallbacks": 0, "calls": 1, "failures": 0, "latency_p50": 0.5, "latency_p95": 0.5,
                  "cache_hit_rate": None, "usd": 0.0, "usd_per_turn": 0.0}, id="malformed-call-without-usage"),
])
def test_writer_stats_summarize_the_turn_calls(night: Evening, calls: list[Record], expected: dict[str, Any]) -> None:
    stats = writer_stats(night, calls, "turn", HAIKU_4_5)
    assert {key: value is None for key, value in stats.items()} == {key: value is None for key, value in expected.items()}
    assert {key: stats[key] for key in expected if expected[key] is not None} == pytest.approx(
        {key: value for key, value in expected.items() if value is not None})


def test_p95_is_the_nearest_rank() -> None:
    stats = writer_stats(evening(20), [turn_call(float(second)) for second in range(1, 21)], "turn", HAIKU_4_5)
    assert (stats["latency_p50"], stats["latency_p95"]) == (10.0, 19.0)


def test_negative_tariff_fails_loudly() -> None:
    with pytest.raises(ValueError):
        writer_stats(evening(1), [turn_call(0.5)], "turn", Tariff(-1.0, 5.0, 0.1, 1.25))


def test_evening_cost_prices_claude_kinds_by_their_tariff() -> None:
    metrics = evening_metrics(evening(1), [turn_call(0.5)], 0.042, 3.0, {"turn": HAIKU_4_5})
    assert metrics["cost"]["turn"]["usd"] == pytest.approx(per_call(USAGE))
    assert metrics["cost"]["turn"]["cache_read_input_tokens"] == 4500
