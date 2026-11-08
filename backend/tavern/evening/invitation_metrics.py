"""Invitations in an evening: how many were made, and how each was answered."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.social.invitations import KINDS


class InvitationCounts(TypedDict):
    """Invitations made (`invite` lines), and answered in all and per kind of invitation, in the order of `KINDS`:
    accepted, declined, and countered (turned down for one of the invitee's own)."""

    made: int
    accepted: int
    declined: int
    countered: int
    by_kind: dict[str, dict[str, int]]


_OUTCOME = {"invitation_accepted": "accepted", "invitation_declined": "declined", "invitation_countered": "countered"}


def invitation_counts(events: Sequence[Mapping[str, Any]]) -> InvitationCounts:
    """Count the invitations of an evening.

    Args:
        events: The complete event log: `turn` events with their `act`, and the `invitation_accepted`,
            `invitation_declined` and `invitation_countered` events with their `invitation` kind.

    Returns:
        The counts. A kind is counted for an invitation by the kind that was asked.

    Raises:
        ValueError: An answer event carries no `invitation` kind, or one that is not in `KINDS`.
    """
    by_kind = {kind: {"accepted": 0, "declined": 0, "countered": 0} for kind in KINDS}
    made = 0
    for event in events:
        if event["type"] == "turn":
            made += event["act"] == "invite"
        elif event["type"] in _OUTCOME:
            if event.get("invitation") not in by_kind:
                raise ValueError(f"An invitation answer must carry its kind: {event!r}")
            by_kind[event["invitation"]][_OUTCOME[event["type"]]] += 1
    return {"made": made, "accepted": sum(item["accepted"] for item in by_kind.values()),
            "declined": sum(item["declined"] for item in by_kind.values()),
            "countered": sum(item["countered"] for item in by_kind.values()),
            "by_kind": {kind: item for kind, item in by_kind.items() if any(item.values())}}
