"""Dozing off: wasted visitors nod off at their table for a while."""

from collections.abc import Mapping
import math
from random import Random
from typing import Any

from tavern.activities import ACTIVITIES
from tavern.conversation import conversation_of
from tavern.drunkenness import drunk_stage
from tavern.memory import record_event


def nodding_off(world: Mapping[str, Any], elapsed: float) -> list[dict[str, Any]]:
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
        if Random(f"{world['seed']}:{world['tick']}:{actor['id']}:doze").random() < chance:
            record_event(world, actor, "dozed_off", f"{actor['name']} nodded off at the table")
            dozers.append(actor)
    return dozers


def _can_doze(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    action = actor["action"]
    busy = action is not None and (action["verb"] == "doze" or not ACTIVITIES[action["verb"]].interruptible)
    return bool(actor.get("seat_id")) and not busy and conversation_of(world, actor["id"]) is None
