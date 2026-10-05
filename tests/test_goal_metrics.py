"""Goals in the evening metrics: set, done, failed and expired."""

from typing import Any

import pytest

from tavern.evening.goal_metrics import goal_counts


def event(kind: str) -> dict[str, Any]:
    """A logged event."""
    return {"time": 1.0, "actor_id": "ada", "type": kind, "message": f"ada: {kind}"}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"set": 0, "done": 0, "failed": 0, "expired": 0}, id="empty"),
    pytest.param([event("goal_set")], {"set": 1, "done": 0, "failed": 0, "expired": 0}, id="single"),
    pytest.param([event("goal_set"), event("goal_set"), event("goal_done"), event("goal_done")],
                 {"set": 2, "done": 2, "failed": 0, "expired": 0}, id="duplicates"),
    pytest.param([event("goal_failed"), event("turn"), event("goal_expired")],
                 {"set": 0, "done": 0, "failed": 1, "expired": 1}, id="mixed-with-other-events"),
])
def test_goals_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert goal_counts(events) == expected


def test_malformed_event_fails_loudly() -> None:
    with pytest.raises(KeyError):
        goal_counts([{"time": 1.0, "message": "no type"}])
