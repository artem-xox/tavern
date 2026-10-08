"""Manners in an evening: seats taken, tables sat down at without being welcome, and apologies."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class MannerCounts(TypedDict):
    """How an evening went in manners: the owners' seats taken, the hosts upset by a stranger at their table, and
    the apologies made."""

    seats_taken: int
    table_intrusions: int
    apologies: int


def manner_counts(events: Sequence[Mapping[str, Any]]) -> MannerCounts:
    """Count the evening's seats taken, intrusions and apologies.

    Args:
        events: The complete event log: `seat_taken` and `table_intruded` (logged once for the one wronged, so each
            counts as it stands) and `apologized` (both guests log it, so an apology counts once by its time and
            words).

    Returns:
        The three counts; zero for each that did not happen.

    Raises:
        KeyError: An event has no type, or an apology no time or words.
    """
    apologies = {(event["time"], event["message"]) for event in events if event["type"] == "apologized"}
    return {"seats_taken": sum(event["type"] == "seat_taken" for event in events),
            "table_intrusions": sum(event["type"] == "table_intruded" for event in events),
            "apologies": len(apologies)}
