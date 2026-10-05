"""Giving in an evening: gifts by kind, refusals, and drink errands begun, done and failed."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.body.items import ITEMS
from tavern.evening.goal_metrics import GoalCounts, goal_counts


class ErrandCounts(TypedDict):
    """Drink errands, however they began: set out, brought, or ended without the drink handed over."""

    begun: int
    done: int
    failed: int


class GivingCounts(TypedDict):
    """How giving went: gifts taken by kind of item, gifts refused, drink errands, and the goals of bringing a drink."""

    gifts: dict[str, int]
    refused: int
    errands: ErrandCounts
    goals: GoalCounts


def giving_counts(events: Sequence[Mapping[str, Any]]) -> GivingCounts:
    """Count the evening's gifts, refusals and drink errands.

    Args:
        events: The complete event log: `gave` and `gift_refused` (both guests log each, so a gift counts once
            by its time and words), `fetch_begun`, `fetch_done` and `fetch_failed`, and the goal events that name
            the goal `bring_drink`.

    Returns:
        Gifts per kind in `ITEMS`, zeros too; refusals; the errands, where one still under way at the end is
        begun but neither done nor failed; and the goals of bringing a drink, set, done, failed and expired.

    Raises:
        KeyError: An event has no type, or a gift or refusal no time or words.
        ValueError: A gift names something that is not an item.
    """
    given = {(event["time"], event["message"]) for event in events if event["type"] == "gave"}
    refused = {(event["time"], event["message"]) for event in events if event["type"] == "gift_refused"}
    kinds = Counter(_kind_of(message) for _, message in given)
    errands = Counter(event["type"] for event in events)
    return {"gifts": {kind: kinds[kind] for kind in ITEMS}, "refused": len(refused),
            "errands": {"begun": errands["fetch_begun"], "done": errands["fetch_done"],
                        "failed": errands["fetch_failed"]},
            "goals": goal_counts([event for event in events if event.get("goal") == "bring_drink"])}


def _kind_of(message: str) -> str:
    # A gift is told as "<giver> gave <receiver> <the item>", the item in its table wording.
    for kind, item in ITEMS.items():
        if message.endswith(item.one):
            return kind
    raise ValueError(f"Cannot tell what was given in {message!r}")
