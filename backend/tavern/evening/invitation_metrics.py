"""Invitations in an evening: how many were made, and how each was answered."""

from collections.abc import Mapping, Sequence
import re
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


# "Bea accepted an invitation to play a game of dice from Ada", "... declined an invitation to ... from ...", and
# "Bea turned down an invitation to ... and invited Ada to ... instead", as `invitations` logs them.
_WORDS = "|".join(re.escape(words) for words in KINDS.values())
_ANSWERED = re.compile(rf".* (?:accepted|declined) an invitation to (?P<kind>{_WORDS}) from .*")
_COUNTERED = re.compile(rf".* turned down an invitation to (?P<kind>{_WORDS}) and invited .* instead")
_BY_WORDS = {words: kind for kind, words in KINDS.items()}
_OUTCOME = {"invitation_accepted": "accepted", "invitation_declined": "declined", "invitation_countered": "countered"}


def invitation_counts(events: Sequence[Mapping[str, Any]]) -> InvitationCounts:
    """Count the invitations of an evening.

    Args:
        events: The complete event log: `turn` events worded "<speaker> to <listener> (<act>): <line>", and the
            `invitation_accepted`, `invitation_declined` and `invitation_countered` events.

    Returns:
        The counts. A kind is counted for an invitation by the kind that was asked.

    Raises:
        ValueError: An answer event does not say which kind of invitation it answered.
    """
    by_kind = {kind: {"accepted": 0, "declined": 0, "countered": 0} for kind in KINDS}
    made = 0
    for event in events:
        if event["type"] == "turn":
            made += "(invite):" in event["message"]
        elif event["type"] in _OUTCOME:
            match = (_COUNTERED if event["type"] == "invitation_countered" else _ANSWERED).fullmatch(event["message"])
            if match is None:
                raise ValueError(f"Cannot read the invitation in {event['message']!r}")
            by_kind[_BY_WORDS[match["kind"]]][_OUTCOME[event["type"]]] += 1
    return {"made": made, "accepted": sum(item["accepted"] for item in by_kind.values()),
            "declined": sum(item["declined"] for item in by_kind.values()),
            "countered": sum(item["countered"] for item in by_kind.values()),
            "by_kind": {kind: item for kind, item in by_kind.items() if any(item.values())}}
