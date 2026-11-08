"""Goals and promises in an evening: how many guests set, reached, lost or let lapse, made, kept or broke."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.mind.goals import GOALS


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


def goal_kind_counts(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Count the evening's goals by kind.

    Args:
        events: The complete event log; each `goal_set` carries its kind (a key of `goals.GOALS`) as `goal`.

    Returns:
        Goals set per kind, for the kinds that were set.

    Raises:
        ValueError: A `goal_set` has no `goal` field, or one that is not a key of `GOALS`.
        KeyError: An event has no type.
    """
    kinds: Counter[str] = Counter()
    for event in events:
        if event["type"] != "goal_set":
            continue
        kind = event.get("goal")
        if kind not in GOALS:
            raise ValueError(f"The goal event {event['message']!r} has no known `goal` field: {kind!r}")
        kinds[kind] += 1
    return dict(kinds)


def chased_counts(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Count, per guest, the intentions that served one of their obsessions.

    Args:
        events: The complete event log: `intention` events.

    Returns:
        Intentions that named an obsession, by the guest's ID, for the guests who had any.

    Raises:
        KeyError: An event has no type.
    """
    return dict(Counter(event["actor_id"] for event in events
                        if event["type"] == "intention" and "obsession" in event))
