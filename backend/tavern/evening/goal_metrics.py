"""Goals and promises in an evening: how many guests set, reached, lost or let lapse, made, kept or broke."""

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict

from tavern.mind.goals import GOALS
from tavern.mind.intentions import CHASING


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


def _wording_pattern(wording: str) -> re.Pattern[str]:
    # What `goal_set` logs for a kind: "<name> set out to " and the wording with the person's name filled in.
    return re.compile(r"set out to " + ".+".join(re.escape(part) for part in wording.split("{name}")) + "$")


_GOAL_PATTERNS = {kind: _wording_pattern(goal.wording) for kind, goal in GOALS.items()}


def goal_kind_counts(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Count the evening's goals by kind.

    Args:
        events: The complete event log; each `goal_set` message ends in its kind's wording (`goals.GOALS`).

    Returns:
        Goals set per kind, for the kinds that were set.

    Raises:
        ValueError: A `goal_set` message is not in the words of any kind.
        KeyError: An event has no type.
    """
    kinds: Counter[str] = Counter()
    for event in events:
        if event["type"] != "goal_set":
            continue
        kind = next((name for name, pattern in _GOAL_PATTERNS.items() if pattern.search(event["message"])), None)
        if kind is None:
            raise ValueError(f"A goal set in words no kind of GOALS has: {event['message']!r}")
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
                        if event["type"] == "intention" and CHASING in event["message"]))
