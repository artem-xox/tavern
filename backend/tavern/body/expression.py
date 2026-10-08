"""What a visitor's body shows: where they look and the emote above their head."""

from collections.abc import Mapping, Sequence
import math
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.hall.staff import facing_of
from tavern.hall.state import Actor, World
from tavern.hall.validation import number, saved_cell


class Gaze(TypedDict):
    """A visitor looking at a cell until a game time, because of a stimulus."""

    cell: list[int]
    until: float
    stimulus_id: int


class Emote(TypedDict):
    """A glyph above a visitor's head until a game time; `kind` is one of `EMOTES`."""

    kind: str
    until: float


# Sleep shows while a guest dozes (`tavern.body.dozing.show_sleep`); nothing shows affection yet.
EMOTES = ("alert", "confused", "angry", "affection", "sleep", "waiting")

EVENT_EMOTES: Mapping[str, str] = MappingProxyType({
    "action_failed": "confused", "quarrel": "angry", "seat_taken": "angry",
    "table_intruded": "angry"})


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


def look_at(actor: Actor, cell: Sequence[int], until: float, stimulus_id: int) -> None:
    """Turn a visitor's gaze to a cell for a while.

    Args:
        actor: Visitor, updated in place.
        cell: Cell to look at.
        until: Game time the gaze ends.
        stimulus_id: Stimulus that drew it.
    """
    actor["gaze"] = Gaze(cell=list(cell), until=until, stimulus_id=stimulus_id)


def show_emote(actor: Actor, kind: str, until: float) -> None:
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


def emote_event(world: Mapping[str, Any], actor: Actor, kind: str) -> None:
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
    """Expire gazes and emotes, show long waits, and face each visitor where they look.

    Args:
        world: World whose visitors are updated in place.
    """
    now, rules = world["time"], world["rules"]
    for actor in world["actors"]:
        if actor["gaze"] and actor["gaze"]["until"] <= now:
            actor["gaze"] = None
        if actor["emote"] and actor["emote"]["until"] <= now:
            actor["emote"] = None
        # A wait shows only once it is long, and never hides a livelier emote.
        if actor["status"] == "waiting" and actor["_blocked_for"] >= rules["long_wait"] and not actor["emote"]:
            show_emote(actor, "waiting", now + rules["emote_seconds"]["waiting"])
        actor["facing"] = _facing(world, actor)


def _facing(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    # A brief hand-over holds both eyes, then a sound turns heads before a conversation does; walkers
    # face their steps and the rest keep their seat's or their task's facing, which the client knows (None).
    if actor["status"] == "walking":
        return None
    origin = (actor["x"], actor["y"])
    party = _hand_over_party(world, actor)
    if party:
        return facing_toward(origin, (party["x"], party["y"]))
    if actor["gaze"]:
        return facing_toward(origin, actor["gaze"]["cell"])
    partner = _focus(world, actor)
    # Staff with nobody to look at face the hall, as their bar says.
    return facing_toward(origin, (partner["x"], partner["y"])) if partner else facing_of(world["map"], actor)


def _focus(world: Mapping[str, Any], actor: Mapping[str, Any]) -> Mapping[str, Any] | None:
    # In a scene (see `tavern.social.scenes`) everyone looks at the last speaker, who looks at whom
    # they addressed (or the next in the circle); before the first line, the two who started
    # it look at each other and anyone else at the starter.
    scene = next((item for item in world["conversations"] if actor["id"] in item["participants"]), None)
    if scene is None:
        # Someone doing something to another visitor, such as handing them something, faces them.
        target = (actor["action"] or {}).get("target_id")
        return next((item for item in world["actors"] if item["id"] == target), None)
    people = {item["id"]: item for item in world["actors"]}
    members = scene["participants"]
    last = scene["turns"][-1] if scene["turns"] else {"speaker": members[0], "addressee": members[1]}
    if last["speaker"] != actor["id"]:
        return people.get(last["speaker"])
    after = members[(members.index(actor["id"]) + 1) % len(members)]
    return people.get(last["addressee"] if last["addressee"] in members else after)


def _hand_over_party(world: Mapping[str, Any], actor: Mapping[str, Any]) -> Mapping[str, Any] | None:
    # Only an action that hands something over names an item (`Action.item`); the giver looks at the
    # receiver, and the receiver at whoever is holding something out to them.
    action = actor["action"] or {}
    if action.get("item"):
        return next((item for item in world["actors"] if item["id"] == action["target_id"]), None)
    return next((item for item in world["actors"] if item["status"] == "interacting"
                 and (item["action"] or {}).get("item") and item["action"]["target_id"] == actor["id"]), None)


def check_saved_expression(actor: Mapping[str, Any], world: Mapping[str, Any]) -> None:
    """Check a saved visitor's facing, gaze, emote and interruption time.

    Args:
        actor: Decoded visitor.
        world: Decoded save, for the map and the clock.
    Raises:
        ValueError: One of them is malformed or out of range.
    """
    if actor.get("facing") not in (None, "north", "south", "east", "west"):
        raise ValueError("Invalid saved facing")
    gaze, emote, interrupted_at = actor["gaze"], actor["emote"], actor["interrupted_at"]
    if gaze is not None:
        if not isinstance(gaze, dict) or set(gaze) != {"cell", "until", "stimulus_id"}:
            raise ValueError("Invalid saved gaze")
        saved_cell(gaze["cell"], world["map"])
        number(gaze["until"], "Saved gaze end", 0, math.inf)
        if type(gaze["stimulus_id"]) is not int:
            raise ValueError("Invalid saved gaze cause")
    if emote is not None:
        if not isinstance(emote, dict) or set(emote) != {"kind", "until"} or emote["kind"] not in EMOTES:
            raise ValueError("Invalid saved emote")
        number(emote["until"], "Saved emote end", 0, math.inf)
    if interrupted_at is not None:
        number(interrupted_at, "Saved interruption time", 0, world["time"])
