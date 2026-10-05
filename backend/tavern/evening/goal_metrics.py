"""Goals, promises and doubts in an evening: set, reached, lost or lapsed; made, kept or broken; unsure."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class GoalCounts(TypedDict):
    """How the goals went: set, done, failed (their guest left) and expired; the rest were replaced by a
    newer intention or still open at closing."""

    set: int
    done: int
    failed: int
    expired: int


def goal_counts(events: Sequence[Mapping[str, Any]]) -> GoalCounts:
    """Count the evening's goals by how they ended.

    Args:
        events: The complete event log: `goal_set`, `goal_done`, `goal_failed` and `goal_expired`.

    Returns:
        The counts of those events.

    Raises:
        KeyError: An event has no type.
    """
    kinds = Counter(event["type"] for event in events)
    return {"set": kinds["goal_set"], "done": kinds["goal_done"], "failed": kinds["goal_failed"],
            "expired": kinds["goal_expired"]}


class PromiseCounts(TypedDict):
    """How promises went: made, kept, broken (late, or the promiser left) and void (the one promised left)."""

    made: int
    kept: int
    broken: int
    void: int


def promise_counts(events: Sequence[Mapping[str, Any]]) -> PromiseCounts:
    """Count the evening's promises by how they ended.

    Args:
        events: The complete event log: `promise_made`, `promise_kept`, `promise_broken` and `promise_void`.

    Returns:
        The counts of those events; a promise still open at the end is made but none of the others.

    Raises:
        KeyError: An event has no type.
    """
    kinds = Counter(event["type"] for event in events)
    return {"made": kinds["promise_made"], "kept": kinds["promise_kept"], "broken": kinds["promise_broken"],
            "void": kinds["promise_void"]}


def unsure_count(events: Sequence[Mapping[str, Any]]) -> int:
    """Count the times a guest could not tell what to do.

    Args:
        events: The complete event log: `unsure` events.

    Returns:
        How many there are.

    Raises:
        KeyError: An event has no type.
    """
    return sum(event["type"] == "unsure" for event in events)
