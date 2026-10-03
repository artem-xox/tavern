"""What a visitor's body shows: where they look and the emote above their head."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, TypedDict


class Gaze(TypedDict):
    """A visitor looking at a cell until a game time, because of a stimulus."""

    cell: list[int]
    until: float
    stimulus_id: int


class Emote(TypedDict):
    """A glyph above a visitor's head until a game time; `kind` is one of `EMOTES`."""

    kind: str
    until: float


# Sleep shows while a guest dozes (E13); nothing shows affection yet.
EMOTES = ("alert", "confused", "angry", "affection", "sleep", "waiting")

EVENT_EMOTES: Mapping[str, str] = MappingProxyType({
    "action_failed": "confused", "quarrel": "angry", "seat_taken": "angry"})


def facing_toward(origin: Sequence[int], target: Sequence[int]) -> str | None:
    """Tell which cardinal direction faces a cell.

    Args:
        origin: Viewer's cell.
        target: Cell looked at; y grows southward, down the map.

    Returns:
        `north`, `south`, `east` or `west` along the longer axis, sideways on a diagonal tie
        (as the client faces interaction targets), or None for the viewer's own cell.
    """
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx != 0 and abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    if dy != 0:
        return "south" if dy > 0 else "north"
    return None


def look_at(actor: dict[str, Any], cell: Sequence[int], until: float, stimulus_id: int) -> None:
    """Turn a visitor's gaze to a cell for a while.

    Args:
        actor: Visitor, updated in place.
        cell: Cell to look at.
        until: Game time the gaze ends.
        stimulus_id: Stimulus that drew it.
    """
    actor["gaze"] = Gaze(cell=list(cell), until=until, stimulus_id=stimulus_id)


def show_emote(actor: dict[str, Any], kind: str, until: float) -> None:
    """Show an emote above a visitor, replacing any earlier one.

    Args:
        actor: Visitor, updated in place.
        kind: One of `EMOTES`.
        until: Game time it disappears.

    Raises:
        ValueError: The emote is unknown.
    """
    if kind not in EMOTES:
        raise ValueError(f"Unknown emote {kind!r}")
    actor["emote"] = Emote(kind=kind, until=until)


def emote_event(world: Mapping[str, Any], actor: dict[str, Any], kind: str) -> None:
    """Show the emote a logged event calls for, if any (see `EVENT_EMOTES`).

    Args:
        world: World with the time and `emote_seconds` lifetimes.
        actor: Visitor the event belongs to.
        kind: Event type.
    """
    if kind in EVENT_EMOTES:
        emote = EVENT_EMOTES[kind]
        show_emote(actor, emote, world["time"] + world["rules"]["emote_seconds"][emote])


def update_expression(world: Mapping[str, Any]) -> None:
    """Expire gazes and emotes, show long waits and dozing, and face each visitor where they look.

    Args:
        world: World whose visitors are updated in place.
    """
    now, rules = world["time"], world["rules"]
    for actor in world["actors"]:
        if actor["gaze"] and actor["gaze"]["until"] <= now:
            actor["gaze"] = None
        if actor["emote"] and actor["emote"]["until"] <= now:
            actor["emote"] = None
        # A wait shows only once it is long, and never hides a livelier emote; nor does sleep.
        if actor["status"] == "waiting" and actor["_blocked_for"] >= rules["long_wait"] and not actor["emote"]:
            show_emote(actor, "waiting", now + rules["emote_seconds"]["waiting"])
        if actor["action"] and actor["action"]["verb"] == "doze" and not actor["emote"]:
            show_emote(actor, "sleep", now + rules["emote_seconds"]["sleep"])
        actor["facing"] = _facing(world, actor)


def _facing(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    # A sound turns heads before a partner does; walkers face their steps and the rest keep
    # their seat's or their task's facing, which the client knows (None).
    if actor["status"] == "walking":
        return None
    origin = (actor["x"], actor["y"])
    if actor["gaze"]:
        return facing_toward(origin, actor["gaze"]["cell"])
    partner = _partner(world, actor)
    return facing_toward(origin, (partner["x"], partner["y"])) if partner else None


def _partner(world: Mapping[str, Any], actor: Mapping[str, Any]) -> Mapping[str, Any] | None:
    action = actor["action"]
    if action and action["verb"] == "talk":
        return next((item for item in world["actors"] if item["id"] == action["target_id"]), None)
    return next((item for item in world["actors"] if item["action"] and item["action"]["verb"] == "talk"
                 and item["action"]["target_id"] == actor["id"]), None)
