"""Invitations in the evening metrics: made, and how each was answered."""

from typing import Any

import pytest

from tavern.evening.invitation_metrics import invitation_counts


def logged(kind: str, message: str) -> dict[str, Any]:
    """A logged event."""
    return {"time": 1.0, "actor_id": "bea", "type": kind, "message": message}


MADE = logged("turn", "Ada to Bea (invite): Fancy a game?")
YES = logged("invitation_accepted", "Bea accepted an invitation to play a game of dice from Ada")
NO = logged("invitation_declined", "Bea declined an invitation to play darts together from Ada")
COUNTER = logged("invitation_countered",
                 "Bea turned down an invitation to play a game of dice and invited Ada to play darts together instead")


def counts(made: int = 0, **by_kind: dict[str, int]) -> dict[str, Any]:
    """The counts of an evening, with the kinds given."""
    return {"made": made, "accepted": sum(item.get("accepted", 0) for item in by_kind.values()),
            "declined": sum(item.get("declined", 0) for item in by_kind.values()),
            "countered": sum(item.get("countered", 0) for item in by_kind.values()),
            "by_kind": {kind: {"accepted": 0, "declined": 0, "countered": 0, **item} for kind, item in by_kind.items()}}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], counts(), id="empty"),
    pytest.param([MADE], counts(1), id="made-and-unanswered"),
    pytest.param([MADE, YES], counts(1, dice_together={"accepted": 1}), id="accepted"),
    pytest.param([MADE, NO], counts(1, darts_together={"declined": 1}), id="declined"),
    pytest.param([MADE, COUNTER], counts(1, dice_together={"countered": 1}), id="countered-by-the-kind-asked"),
    pytest.param([MADE, MADE, YES, YES], counts(2, dice_together={"accepted": 2}), id="duplicates"),
    pytest.param([MADE, NO, YES], counts(1, darts_together={"declined": 1}, dice_together={"accepted": 1}),
                 id="kinds-in-table-order"),
    pytest.param([logged("turn", "Ada to Bea (greet): Evening.")], counts(), id="other-lines-ignored"),
])
def test_invitations_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    result = invitation_counts(events)
    assert (result, list(result["by_kind"])) == (expected, [k for k in ("darts_together", "dice_together") if k in expected["by_kind"]])


@pytest.mark.parametrize("event", [
    pytest.param(logged("invitation_accepted", "Bea said yes"), id="not-in-the-logged-form"),
    pytest.param(logged("invitation_declined", "Bea declined an invitation to do the waltz from Ada"), id="an-unknown-kind"),
])
def test_an_invitation_event_that_cannot_be_read_fails_loudly(event: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        invitation_counts([event])
