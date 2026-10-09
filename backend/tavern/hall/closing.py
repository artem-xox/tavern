"""Closing time: the barkeep's call a little before the inn shuts, and the close itself, both called out in the event log."""

from collections.abc import Mapping
import math
from typing import Any

from tavern.body.hearing import EVENT_SOUNDS, emit
from tavern.hall.memory import log_event, record_event
from tavern.hall.staff import on_staff
from tavern.hall.state import World
from tavern.hall.validation import number

# What the barkeep says aloud at the call; the client shows it over his head (`WorldEvent.line`).
LAST_CALL_LINE = "Time, friends! The Last Inn is closing for the night. Finish your cups and get yourselves home safe."


def inn_closed(world: Mapping[str, Any]) -> bool:
    """Tell whether the inn has closed for the night.

    Args:
        world: World with `time` and `closes_at` in game seconds, or no closing time (None).
    Returns:
        True from closing time on; never for an evening without a closing time.
    """
    return world["closes_at"] is not None and world["time"] >= world["closes_at"]


def closing_called(world: Mapping[str, Any]) -> bool:
    """Tell whether the barkeep has called closing time, which comes before the close itself.

    Args:
        world: World with `time` and `last_call_at` in game seconds, or no call (None).
    Returns:
        True from the call on; never for an evening without one.
    """
    return world["last_call_at"] is not None and world["time"] >= world["last_call_at"]


def since_last_call(world: Mapping[str, Any]) -> float | None:
    """Tell how long ago the barkeep called closing time.

    Args:
        world: World with `time` and `last_call_at`.
    Returns:
        Game seconds since the call, or None before it (and for an evening without one).
    """
    return world["time"] - world["last_call_at"] if closing_called(world) else None


def call_last_orders(world: World, since: float) -> None:
    """Have the barkeep call closing time on the tick that reaches it.

    Args:
        world: World whose event log receives `last_call`, with the words in `line`, and whose stimuli receive the
            sound. The barkeep is the first staff member; with none, the innkeeper calls from the middle of the bar
            and the event belongs to nobody.
        since: World time before this tick; the tick covers (since, time].
    """
    last_call = world["last_call_at"]
    if last_call is None or not since < last_call <= world["time"]:
        return
    barkeep = next((actor for actor in world["actors"] if on_staff(actor)), None)
    if barkeep is None:
        message = f'The innkeeper called out: "{LAST_CALL_LINE}"'
        log_event(world, None, "last_call", message)
        emit(world, EVENT_SOUNDS["last_call"], [], _innkeeper(world["map"]), [], message, "last_call")
    else:
        record_event(world, barkeep, "last_call", f'{barkeep["name"]} called out: "{LAST_CALL_LINE}"')
    world["events"][-1]["line"] = LAST_CALL_LINE


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


def check_saved_last_call(world: Mapping[str, Any]) -> None:
    """Check the saved time of the barkeep's call.

    Args:
        world: Decoded save with `last_call_at` and `closes_at`.
    Raises:
        ValueError: The call is no number after the start and before closing time, or there is no closing time.
    """
    last_call = world["last_call_at"]
    if last_call is None:
        return
    if world["closes_at"] is None:
        raise ValueError("A saved last call needs a closing time")
    if not 0 < number(last_call, "Saved last call", 0, math.inf) < world["closes_at"]:
        raise ValueError("A saved last call must come after the start and before closing time")


def _innkeeper(world_map: Mapping[str, Any]) -> list[int]:
    # The innkeeper calls from the middle of the bar; a hall without a bar hears it from its middle.
    bar = next((item for item in world_map["objects"] if item["kind"] == "bar"), None)
    if bar is None:
        return [world_map["width"] // 2, world_map["height"] // 2]
    return [bar["x"] + bar.get("width", 1) // 2, bar["y"]]
