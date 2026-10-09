"""The guest who came in unwell: who they were, whether a remedy cured them, who gave it, and when."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class AilmentCounts(TypedDict):
    """How the evening's unwell guest fared: their name and arrival time, who cured them and when, and whether they
    were never cured. All None (and False) for an evening where nobody fell ill."""

    ailing: str | None
    arrived_at: float | None
    cured_by: str | None
    cured_at: float | None
    left_ailing: bool


def ailment_counts(events: Sequence[Mapping[str, Any]], names: Mapping[str, str]) -> AilmentCounts:
    """Find the unwell guest in the log and see whether they were cured.

    Args:
        events: The complete event log: `arrived_unwell` (logged for the unwell guest) and `cured` (logged for the
            giver and the receiver, so the guest who is not the unwell one gave the remedy).
        names: Every guest's name by ID, in the hall and gone.

    Returns:
        The counts. With no `arrived_unwell` event nobody fell ill; a second one (a second sick guest) is ignored.

    Raises:
        KeyError: An event has no type, time or actor, or a guest is missing from `names`.
    """
    arrived = next((event for event in events if event["type"] == "arrived_unwell"), None)
    if arrived is None:
        return {"ailing": None, "arrived_at": None, "cured_by": None, "cured_at": None, "left_ailing": False}
    sick = arrived["actor_id"]
    cures = [event for event in events if event["type"] == "cured"]
    # The first cure of the unwell guest: the receiver logs it too, so the giver's own record names who gave it.
    cure = next((event for event in cures if event["actor_id"] == sick), None)
    giver = None if cure is None else next(event["actor_id"] for event in cures
                                          if (event["time"], event["message"]) == (cure["time"], cure["message"])
                                          and event["actor_id"] != sick)
    return {"ailing": names[sick], "arrived_at": arrived["time"], "cured_by": None if giver is None else names[giver],
            "cured_at": None if cure is None else cure["time"], "left_ailing": cure is None}
