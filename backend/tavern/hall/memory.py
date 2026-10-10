"""The shared event log and each visitor's personal memories."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.body.expression import emote_event
from tavern.body.hearing import sound_event
from tavern.hall.state import Actor, World


def record_event(world: World, actor: Actor, kind: str, message: str) -> None:
    """Log an event for the room and remember it; it may be heard and show on the visitor's face.

    Args:
        world: World whose event log keeps the latest 200 events.
        actor: Visitor who keeps the latest 100 memories: about one evening of what they did and what befell them.
        kind: Event type.
        message: Human-readable description.
    """
    event = {"time": world["time"], "actor_id": actor["id"], "type": kind, "message": message}
    world["events"].append(event)
    actor["memory"].append(deepcopy(event))
    sound_event(world, actor, event)
    emote_event(world, actor, kind)
    del world["events"][:-200]
    del actor["memory"][:-100]


def log_event(world: World, actor_id: str | None, kind: str, message: str) -> None:
    """Log an event for the room only: no visitor remembers it, and nobody hears it.

    Args:
        world: World whose event log keeps the latest 200 events.
        actor_id: Visitor the event concerns, or None.
        kind: Event type.
        message: Human-readable description.
    """
    world["events"].append({"time": world["time"], "actor_id": actor_id, "type": kind, "message": message})
    del world["events"][:-200]
