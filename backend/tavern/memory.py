"""The shared event log, each visitor's personal memories, and their grievances."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.expression import emote_event
from tavern.hearing import sound_event


def record_event(world: Mapping[str, Any], actor: dict[str, Any], kind: str, message: str) -> None:
    """Log an event for the room and remember it; it may be heard and show on the visitor's face.

    Args:
        world: World whose event log keeps the latest 200 events.
        actor: Visitor who keeps the latest 25 memories.
        kind: Event type.
        message: Human-readable description.
    """
    event = {"time": world["time"], "actor_id": actor["id"], "type": kind, "message": message}
    world["events"].append(event)
    actor["memory"].append(deepcopy(event))
    sound_event(world, actor, event)
    emote_event(world, actor, kind)
    del world["events"][:-200]
    del actor["memory"][:-25]


def grieve(actor: dict[str, Any], grievance: str) -> None:
    """Remember a wrong done to a visitor tonight, keeping the latest five.

    Args:
        actor: Wronged visitor.
        grievance: What happened, in their words.
    """
    actor["visit"]["grievances"].append(grievance)
    del actor["visit"]["grievances"][:-5]
