"""Closing time: when the inn shuts for the night, called out in the event log."""

from collections.abc import Mapping
from typing import Any


def inn_closed(world: Mapping[str, Any]) -> bool:
    """Tell whether the inn has closed for the night.

    Args:
        world: World with `time` and `closes_at` in game seconds, or no closing time (None).
    Returns:
        True from closing time on; never for an evening without a closing time.
    """
    return world["closes_at"] is not None and world["time"] >= world["closes_at"]


def call_closing(world: dict[str, Any], since: float) -> None:
    """Log closing time on the tick that reaches it.

    Args:
        world: World whose event log keeps the latest 200 events.
        since: World time before this tick; the tick covers (since, time].
    """
    closes_at = world["closes_at"]
    if closes_at is None or not since < closes_at <= world["time"]:
        return
    world["events"].append({"time": world["time"], "actor_id": None, "type": "closing",
                            "message": "Closing time: the innkeeper calls for every guest to head home"})
    del world["events"][:-200]
