"""Sounds in the hall: the stimuli activities and events emit, and how loudly each reaches a listener."""

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.hall.state import World
from tavern.hall.validation import number, saved_cell


@dataclass(frozen=True)
class Sound:
    """How something sounds: what it is, how loud at its source, and how far it carries.

    Attributes:
        kind: Short name of the sound, such as `quarrel` or `thud`.
        loudness: Loudness at the source, 0–1.
        reach: Cells of open air over which it fades to silence.
        noun: How a listener names it, such as "a loud quarrel".
    """

    kind: str
    loudness: float
    reach: float
    noun: str

    def __post_init__(self) -> None:
        if not self.kind or not self.noun:
            raise ValueError(f"A sound needs a kind and a noun, not {self.kind!r} and {self.noun!r}")
        if not 0 <= self.loudness <= 1:
            raise ValueError(f"Loudness must be between 0 and 1, not {self.loudness!r}")
        if not 0 < self.reach < math.inf:
            raise ValueError(f"Reach must be a positive number of cells, not {self.reach!r}")


class Stimulus(TypedDict):
    """One sound in the hall, waiting for the listeners' attention on the next tick.

    `sources` are the visitors who made it (empty for a call from a place, such as the
    innkeeper's), `cell` where it came from, `about` the visitors it concerns without having
    made it, `cause` the message of the event or activity that caused it, and `event` that
    event's type, or None for an activity's sound.
    """

    id: int
    kind: str
    noun: str
    sources: list[str]
    cell: list[int]
    loudness: float
    reach: float
    time: float
    about: list[str]
    cause: str
    event: str | None


# Quiet sounds stay below 0.5 / 1.875 (the most relevance and curiosity can raise them), so
# they can only ever draw a glance; a quarrel or the closing call can interrupt.
EVENT_SOUNDS: Mapping[str, Sound] = MappingProxyType({
    "quarrel": Sound("quarrel", 1.0, 24.0, "a loud quarrel"),
    "arrival": Sound("door", 0.25, 20.0, "the front door"),
    "departure": Sound("door", 0.25, 20.0, "the front door"),
    "closing": Sound("closing_call", 1.0, 40.0, "the innkeeper's call"),
    "action_failed": Sound("grumble", 0.2, 4.0, "a muttered complaint"),
    # Below the interrupt level: it turns heads without breaking off what anyone is doing.
    "dice_won": Sound("cheer", 0.3, 12.0, "a whoop at the dice table"),
})


def emit(world: World, sound: Sound, sources: Sequence[str], cell: Sequence[int],
         about: Sequence[str], cause: str, event: str | None) -> Stimulus:
    """Make a sound in the hall; listeners attend to it at the end of the tick.

    Args:
        world: World whose pending `stimuli` receive it and whose `next_stimulus_id` numbers it.
        sound: What it sounds like.
        sources: Visitors making it; empty for a call from a place.
        cell: Where it comes from.
        about: Visitors it concerns without having made it.
        cause: Message of the event or activity behind it.
        event: Type of the event behind it, or None for an activity's sound.

    Returns:
        The pending stimulus. An event logged once per participant (a quarrel) is one sound:
        the later participants join the first one's stimulus as sources.
    """
    for pending in world["stimuli"]:
        if (pending["kind"], pending["time"], pending["cause"]) == (sound.kind, world["time"], cause):
            pending["sources"].extend(source for source in sources if source not in pending["sources"])
            return pending
    stimulus: Stimulus = {"id": world["next_stimulus_id"], "kind": sound.kind, "noun": sound.noun,
                          "sources": list(sources), "cell": list(cell), "loudness": sound.loudness,
                          "reach": sound.reach, "time": world["time"], "about": list(about), "cause": cause,
                          "event": event}
    world["next_stimulus_id"] += 1
    world["stimuli"].append(stimulus)
    return stimulus


def sound_event(world: World, actor: Mapping[str, Any], event: Mapping[str, Any]) -> None:
    """Let a logged event be heard if it makes a sound (see `EVENT_SOUNDS`).

    Args:
        world: World the sound is made in.
        actor: Visitor the event belongs to, who makes the sound where they stand.
        event: Logged event with `type` and `message`.
    """
    sound = EVENT_SOUNDS.get(event["type"])
    if sound is not None:
        emit(world, sound, [actor["id"]], [actor["x"], actor["y"]], [], event["message"], event["type"])


def sound_activity(world: World, actor: Mapping[str, Any], sound: Sound, doing: str | None) -> None:
    """Let an activity be heard as its interaction begins.

    Args:
        world: World the sound is made in.
        actor: Visitor beginning the interaction; a visitor they target is what it concerns.
        sound: The activity's sound.
        doing: How others see someone doing it, or None to name the sound instead.
    """
    target = actor["action"]["target_id"]
    about = [target] if any(item["id"] == target for item in world["actors"]) else []
    emit(world, sound, [actor["id"]], [actor["x"], actor["y"]], about,
         f"{actor['name']} is {doing or sound.kind}", None)


def heard_loudness(world_map: Mapping[str, Any], stimulus: Stimulus, cell: Sequence[int], damping: float) -> float:
    """Tell how loud a sound is where a listener stands.

    Args:
        world_map: Map whose `blocked` cells are walls.
        stimulus: The sound.
        cell: Listener's cell.
        damping: Factor each wall cell between them multiplies the loudness by, 0–1.

    Returns:
        Loudness × max(0, 1 − distance / reach) × damping per wall cell on the straight line
        between the two cells. Distance is Euclidean, in cells.

    Raises:
        ValueError: Damping is outside 0–1.
    """
    if not 0 <= damping <= 1:
        raise ValueError(f"Wall damping must be between 0 and 1, not {damping!r}")
    origin, target = (stimulus["cell"][0], stimulus["cell"][1]), (cell[0], cell[1])
    falloff = max(0.0, 1 - math.dist(origin, target) / stimulus["reach"])
    walls = set(map(tuple, world_map["blocked"]))
    crossed = sum(step in walls for step in _between(origin, target))
    return stimulus["loudness"] * falloff * damping ** crossed


def _between(origin: tuple[int, int], target: tuple[int, int]) -> Iterator[tuple[int, int]]:
    # The same integer Bresenham line as sight.line_visible, without either end cell.
    x, y = origin
    end_x, end_y = target
    dx, dy = abs(end_x - x), -abs(end_y - y)
    step_x, step_y = (1 if x < end_x else -1), (1 if y < end_y else -1)
    error = dx + dy
    while (x, y) != target:
        if (x, y) != origin:
            yield x, y
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y


def salience(world: Mapping[str, Any], stimulus: Stimulus, listener: Mapping[str, Any],
             friends: Collection[str]) -> float:
    """Tell how much a sound matters to a listener.

    Args:
        world: World with the map and the `attention.wall_damping` rule.
        stimulus: The sound.
        listener: Visitor who may hear it.
        friends: Visitors the listener cares about: a sound they make or that concerns them is
            relevant. Attention passes those the listener counts as friends (`thoughts.friends_of`).

    Returns:
        Heard loudness × relevance × temperament. Relevance is 1.5 when the sound concerns
        the listener, names them, or involves a friend, otherwise 1. Temperament is
        0.75 + 0.5 × curiosity, a missing trait counting as a middling 0.5, as in the
        briefing. A listener never hears their own noise (0).
    """
    if listener["id"] in stimulus["sources"]:
        return 0.0
    heard = heard_loudness(world["map"], stimulus, (listener["x"], listener["y"]),
                           world["rules"]["attention"]["wall_damping"])
    named = re.search(rf"\b{re.escape(listener['name'])}\b", stimulus["cause"]) is not None
    involves_friend = bool({*stimulus["sources"], *stimulus["about"]} & set(friends))
    relevant = listener["id"] in stimulus["about"] or named or involves_friend
    curiosity = listener["traits"].get("curiosity", 0.5)
    return heard * (1.5 if relevant else 1.0) * (0.75 + 0.5 * curiosity)


def check_saved_stimuli(world: Mapping[str, Any]) -> None:
    """Check the sounds waiting in a saved world.

    Args:
        world: Decoded save with `stimuli` and `next_stimulus_id`.
    Raises:
        ValueError: A stimulus is malformed, from the future, or its ID is repeated or not yet issued.
    """
    stimuli, issued = world.get("stimuli"), world.get("next_stimulus_id")
    if type(issued) is not int or issued < 0 or not isinstance(stimuli, list):
        raise ValueError("Invalid saved stimuli")
    for item in stimuli:
        _validate_stimulus(item, world)
    ids = [item["id"] for item in stimuli]
    if len(set(ids)) != len(ids) or any(type(value) is not int or not 0 <= value < issued for value in ids):
        raise ValueError("Saved stimuli need unique issued IDs")


def _validate_stimulus(item: Any, world: Mapping[str, Any]) -> None:
    keys = {"id", "kind", "noun", "sources", "cell", "loudness", "reach", "time", "about", "cause", "event"}
    if not isinstance(item, dict) or set(item) != keys:
        raise ValueError("Invalid saved stimulus")
    Sound(item["kind"], number(item["loudness"], "Saved loudness", 0, 1), item["reach"], item["noun"])
    number(item["time"], "Saved stimulus time", 0, world["time"])
    saved_cell(item["cell"], world["map"])
    for key in ("sources", "about"):
        if not isinstance(item[key], list) or any(not isinstance(value, str) for value in item[key]):
            raise ValueError(f"Invalid saved stimulus {key}")
    if not isinstance(item["cause"], str) or not isinstance(item["event"], (str, type(None))):
        raise ValueError("Invalid saved stimulus cause")
