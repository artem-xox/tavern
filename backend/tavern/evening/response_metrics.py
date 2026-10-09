"""Answers in an evening: how many guests set out to answer what was done to them, to what, and how long after."""

from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict

from tavern.social.responses import RESPONSES
from tavern.social.thoughts import THOUGHTS


class ResponseCounts(TypedDict):
    """Answers begun (`answered` events): in all, per kind of thought in the order of `RESPONSES`, and the mean game
    seconds from the thought to the answer (None without any). Unrounded."""

    answered: int
    by_kind: dict[str, int]
    mean_delay: float | None


# "Ada went to answer Bea, who beat them at dice (30 s later)", as `responses.mark_answered` logs it.
_ANSWER = re.compile(r".* went to answer .*?, who (?P<reason>.+) \((?P<seconds>\d+) s later\)")
_KINDS = {THOUGHTS[kind].reason: kind for kind in RESPONSES}


def response_counts(events: Sequence[Mapping[str, Any]]) -> ResponseCounts:
    """Count the answers of an evening.

    Args:
        events: The complete event log.

    Returns:
        The answers by kind and their mean delay.

    Raises:
        ValueError: An `answered` event is not worded as `mark_answered` words it, or names a reason no thought of
            `RESPONSES` has.
    """
    found = []
    for event in events:
        if event["type"] != "answered":
            continue
        match = _ANSWER.fullmatch(event["message"])
        if match is None or match["reason"] not in _KINDS:
            raise ValueError(f"Cannot read the answer {event['message']!r}")
        found.append((_KINDS[match["reason"]], int(match["seconds"])))
    by_kind = {kind: sum(item == kind for item, _ in found) for kind in RESPONSES}
    return {"answered": len(found), "by_kind": {kind: count for kind, count in by_kind.items() if count},
            "mean_delay": sum(seconds for _, seconds in found) / len(found) if found else None}
