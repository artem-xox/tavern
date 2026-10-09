"""The close of an evening: how many guests went home on the barkeep's call and how many were sent home at closing."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class ClosingCounts(TypedDict):
    """How guests took the close: those in the hall at the call, those of them who went home before closing time,
    those still in at closing time (sent home), and the time the last guest left."""

    last_call_at: float | None
    closes_at: float | None
    present_at_call: int
    left_after_call: int
    sent_home: int
    last_out: float | None


def closing_counts(departed: Sequence[Mapping[str, Any]], last_call_at: float | None,
                   closes_at: float | None) -> ClosingCounts:
    """Count how the guests left around the call and the close.

    Args:
        departed: The guests who went home, with `visit.seconds` (how long they stayed) and `visit.left_at`; a guest
            arrived `seconds` before they left.
        last_call_at: Game time of the barkeep's call, or None for an evening without one.
        closes_at: Closing time, or None for an evening that never closes.

    Returns:
        The call and closing times as given; `present_at_call` (in the hall when the call came, which counts a guest
        who left on its very tick), `left_after_call` (of those, gone before closing time) and `sent_home` (left at or
        after closing time); and `last_out`, when the last guest left, or None when nobody did. Without a call the first
        two are zero; without a closing time `sent_home` is.
    """
    stayed = [(guest["visit"]["left_at"] - guest["visit"]["seconds"], guest["visit"]["left_at"]) for guest in departed]
    present = [left for arrived, left in stayed if last_call_at is not None and arrived <= last_call_at <= left]
    return {"last_call_at": last_call_at, "closes_at": closes_at, "present_at_call": len(present),
            "left_after_call": sum(closes_at is None or left < closes_at for left in present),
            "sent_home": sum(closes_at is not None and left >= closes_at for _, left in stayed),
            "last_out": max((left for _, left in stayed), default=None)}
