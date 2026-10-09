"""Sleeping at the table: who is asleep, who nods off, and which sound wakes a sleeper."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.body.drunkenness import drunk_stage
from tavern.body.expression import show_emote
from tavern.body.hearing import Stimulus, heard_loudness
from tavern.hall.chance import roll
from tavern.hall.closing import closing_called, inn_closed
from tavern.hall.state import Actor, World
from tavern.social.scenes import conversation_of


def nodding_off(world: World, elapsed: float) -> list[Actor]:
    """Find the wasted visitors who nod off at their table this tick, and log it.

    Only someone sitting in their seat, not talking and doing nothing they would not break
    off, can doze, and nobody does once the barkeep has called closing time. Each such wasted visitor nods off with
    `doze_per_second` per second.

    Args:
        world: World with the seed, tick and `drunkenness` rules.
        elapsed: Game seconds since the last tick.

    Returns:
        The visitors who nod off; the world starts their `doze`, which logs it.
    """
    if inn_closed(world) or closing_called(world):
        return []
    chance = 1 - math.exp(-world["rules"]["drunkenness"]["doze_per_second"] * elapsed)
    dozers = []
    for actor in world["actors"]:
        if drunk_stage(actor["drunkenness"]).name != "wasted" or not _can_doze(world, actor):
            continue
        # Seeded by the evening, tick and visitor, so a replay or a reloaded save dozes alike.
        if roll(world, actor["id"], "doze") < chance:
            dozers.append(actor)
    return dozers


def asleep(actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor is asleep.

    Args:
        actor: Visitor.

    Returns:
        True while their action is one that sleeps (`Activity.asleep`).
    """
    action = actor["action"]
    return action is not None and ACTIVITIES[action["verb"]].asleep


def waking_sound(world: Mapping[str, Any], stimuli: Sequence[Stimulus], sleeper: Mapping[str, Any]) -> Stimulus | None:
    """Find the sound that wakes a sleeper, if any.

    A sound as loud at its source as `attention.interrupt` and heard at all (walls damp it but do not stop
    it) always wakes a sleeper, whoever they are and whoever made it. A quieter one never does, not even
    with a glance. A sleeper does not wake to their own noise.

    Args:
        world: World with the map and the `attention` rules.
        stimuli: The sounds made since the last tick.
        sleeper: The visitor asleep.

    Returns:
        The first such sound, or None.
    """
    rules = world["rules"]["attention"]
    cell = (sleeper["x"], sleeper["y"])
    return next((item for item in stimuli if item["loudness"] >= rules["interrupt"]
                 and sleeper["id"] not in item["sources"]
                 and heard_loudness(world["map"], item, cell, rules["wall_damping"]) > 0), None)


def show_sleep(world: World) -> None:
    """Show the sleep emote above every sleeper who has no other emote.

    Args:
        world: World whose sleepers are updated in place; a livelier emote is never hidden.
    """
    for actor in world["actors"]:
        if asleep(actor) and not actor["emote"]:
            show_emote(actor, "sleep", world["time"] + world["rules"]["emote_seconds"]["sleep"])


def _can_doze(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    action = actor["action"]
    busy = asleep(actor) or (action is not None and not ACTIVITIES[action["verb"]].interruptible)
    return bool(actor.get("seat_id")) and not busy and conversation_of(world, actor["id"]) is None
