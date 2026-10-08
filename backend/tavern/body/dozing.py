"""Dozing off: wasted visitors nod off at their table for a while."""

from collections.abc import Mapping
import math
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.body.drunkenness import drunk_stage
from tavern.body.expression import show_emote
from tavern.hall.chance import roll
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social.scenes import conversation_of


def nodding_off(world: World, elapsed: float) -> list[Actor]:
    """Find the wasted visitors who nod off at their table this tick, and log it.

    Only someone sitting in their seat, not talking and doing nothing they would not break
    off, can doze. Each such wasted visitor nods off with `doze_per_second` per second.

    Args:
        world: World with the seed, tick and `drunkenness` rules; dozers' memories are updated.
        elapsed: Game seconds since the last tick.

    Returns:
        The visitors who nod off; the world starts their `doze`.
    """
    chance = 1 - math.exp(-world["rules"]["drunkenness"]["doze_per_second"] * elapsed)
    dozers = []
    for actor in world["actors"]:
        if drunk_stage(actor["drunkenness"]).name != "wasted" or not _can_doze(world, actor):
            continue
        # Seeded by the evening, tick and visitor, so a replay or a reloaded save dozes alike.
        if roll(world, actor["id"], "doze") < chance:
            record_event(world, actor, "dozed_off", f"{actor['name']} nodded off at the table")
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
