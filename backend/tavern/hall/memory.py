"""The shared event log and each visitor's personal memories."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from tavern.body.expression import emote_event
from tavern.body.hearing import sound_event
from tavern.hall.state import Actor, World


def record_event(world: World, actor: Actor, kind: str, message: str,
                 outcome: str | None = None) -> dict[str, Any]:
    """Log an event for the room and remember it; it may be heard and show on the visitor's face.

    Args:
        world: World whose event log keeps the latest 200 events.
        actor: Visitor who keeps the latest 100 memories: about one evening of what they did and what befell them.
        kind: Event type.
        message: Human-readable description.
        outcome: How it came out, for the events that have one (a fight's `ENDINGS`), kept as a field so that
            nothing has to read it from the words.

    Returns:
        The event just logged, so a caller can add fields to it.
    """
    event = {"time": world["time"], "actor_id": actor["id"], "type": kind, "message": message}
    if outcome is not None:
        event["outcome"] = outcome
    world["events"].append(event)
    actor["memory"].append(deepcopy(event))
    sound_event(world, actor, event)
    emote_event(world, actor, kind)
    del world["events"][:-200]
    del actor["memory"][:-100]
    return event


def log_event(world: World, actor_id: str | None, kind: str, message: str) -> dict[str, Any]:
    """Log an event for the room only: no visitor remembers it, and nobody hears it.

    Args:
        world: World whose event log keeps the latest 200 events.
        actor_id: Visitor the event concerns, or None.
        kind: Event type.
        message: Human-readable description.

    Returns:
        The event just logged, so a caller can add fields to it.
    """
    event = {"time": world["time"], "actor_id": actor_id, "type": kind, "message": message}
    world["events"].append(event)
    del world["events"][:-200]
    return event


def fresh_events(events: Sequence[dict[str, Any]], last: Mapping[str, Any] | None) -> list[dict[str, Any]] | None:
    """Pick the events logged after the last one a runner has seen.

    Args:
        events: The world's event log, oldest first.
        last: The latest event the caller already took, or None when it has taken none.

    Returns:
        Every event after `last`, all of them when `last` is None, or None when `last` is no longer in the
        log (trimmed away). `last` is found by identity, scanning from the end, because equal events repeat.
    """
    if last is None:
        return list(events)
    for index in range(len(events) - 1, -1, -1):
        if events[index] is last:
            return list(events[index + 1:])
    return None
