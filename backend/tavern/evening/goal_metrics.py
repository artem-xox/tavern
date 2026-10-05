"""Goals in an evening: how many guests set, reached, lost or let lapse."""

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
