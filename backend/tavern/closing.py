"""Closing time: when the inn shuts for the night, called out in the event log."""

from collections.abc import Mapping
from typing import Any

from tavern.hearing import EVENT_SOUNDS, emit
from tavern.state import World


def inn_closed(world: Mapping[str, Any]) -> bool:
    """Tell whether the inn has closed for the night.

    Args:
        world: World with `time` and `closes_at` in game seconds, or no closing time (None).
    Returns:
        True from closing time on; never for an evening without a closing time.
    """
    return world["closes_at"] is not None and world["time"] >= world["closes_at"]


def call_closing(world: World, since: float) -> None:
    """Log closing time on the tick that reaches it, called out loud from the bar.

    Args:
        world: World whose event log keeps the latest 200 events and whose stimuli receive the call.
        since: World time before this tick; the tick covers (since, time].
    """
    closes_at = world["closes_at"]
    if closes_at is None or not since < closes_at <= world["time"]:
        return
    message = "Closing time: the innkeeper calls for every guest to head home"
    world["events"].append({"time": world["time"], "actor_id": None, "type": "closing", "message": message})
    del world["events"][:-200]
    emit(world, EVENT_SOUNDS["closing"], [], _innkeeper(world["map"]), [], message, "closing")


def _innkeeper(world_map: Mapping[str, Any]) -> list[int]:
    # The innkeeper calls from the middle of the bar; a hall without a bar hears it from its middle.
    bar = next((item for item in world_map["objects"] if item["kind"] == "bar"), None)
    if bar is None:
        return [world_map["width"] // 2, world_map["height"] // 2]
    return [bar["x"] + bar.get("width", 1) // 2, bar["y"]]
