"""Answers in an evening: how many guests set out to answer what was done to them, to what, and how long after."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.social.responses import RESPONSES


class ResponseCounts(TypedDict):
    """Answers begun (`answered` events): in all, per kind of thought in the order of `RESPONSES`, and the mean game
    seconds from the thought to the answer (None without any). Unrounded."""

    answered: int
    by_kind: dict[str, int]
    mean_delay: float | None



def response_counts(events: Sequence[Mapping[str, Any]]) -> ResponseCounts:
    """Count the answers of an evening.

    Args:
        events: The complete event log.

    Returns:
        The answers by kind and their mean delay.

    Raises:
        ValueError: An `answered` event has no `response` of `RESPONSES` or no `after`.
    """
    found = []
    for event in events:
        if event["type"] != "answered":
            continue
        if event.get("response") not in RESPONSES or "after" not in event:
            raise ValueError(f"The answer {event['message']!r} has no known `response` and `after` fields")
        # Whole seconds, as the message shows them: the mean has always been taken over those.
        found.append((event["response"], round(event["after"])))
    by_kind = {kind: sum(item == kind for item, _ in found) for kind in RESPONSES}
    return {"answered": len(found), "by_kind": {kind: count for kind, count in by_kind.items() if count},
            "mean_delay": sum(seconds for _, seconds in found) / len(found) if found else None}
