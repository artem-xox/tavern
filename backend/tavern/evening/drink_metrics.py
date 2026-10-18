"""Drink in an evening: which guests got drunk or wasted, and how many beers each had."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class DrinkCounts(TypedDict):
    """Guests who reached `drunk` and `wasted` (by ID, in the order they first did) and the beers each had."""

    drunk: list[str]
    wasted: list[str]
    beers: dict[str, int]


def _first_times(events: Sequence[Mapping[str, Any]], kind: str) -> list[str]:
    return list(dict.fromkeys(event["actor_id"] for event in events if event["type"] == kind))


def drink_counts(events: Sequence[Mapping[str, Any]], guests: Sequence[Mapping[str, Any]]) -> DrinkCounts:
    """Count who got drunk and how much each guest drank.

    Args:
        events: The complete event log: `got_drunk` and `got_wasted` events (`activities._drink`).
        guests: Everyone who came in, still inside or departed, each with `id` and `visit.beers`.

    Returns:
        Guests who reached each stage, once each, in the order they first did, and every guest's beers.

    Raises:
        KeyError: An event has no type.
    """
    return {"drunk": _first_times(events, "got_drunk"), "wasted": _first_times(events, "got_wasted"),
            "beers": {guest["id"]: guest["visit"]["beers"] for guest in guests}}
