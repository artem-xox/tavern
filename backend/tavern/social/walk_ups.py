"""Someone walking up to a guest who stands in the open, and the guest waiting for them."""

from collections.abc import Mapping
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.body.expression import facing_toward
from tavern.hall.state import Actor, World, find_actor
from tavern.social.scenes import at_table, conversation_of, pressed


def walker_toward(world: Mapping[str, Any], actor_id: str) -> Actor | None:
    """Tell who is walking up to a guest who stands in the open, if anyone.

    The one walked up to waits for them rather than deciding: they would only walk off and spoil the meeting. The wait
    ends when the walker gives up, is held up for `rules.long_wait`, or arrives (the scene then holds them both), and
    never holds someone a need presses on, who is on their way somewhere, sits, or is already talking.

    Args:
        world: Current world; the wait is derived from it, so nothing is saved.
        actor_id: Guest who may be waited for.

    Returns:
        The first visitor, in actor order, whose `approach` (any verb with `Activity.approaches`) targets them and who is
        walking toward them, or waiting on a blocked route for less than `rules.long_wait` seconds; None otherwise.
    """
    target = find_actor(world, actor_id)
    if (target is None or target.get("seat_id") or target["status"] == "walking" or target["path"]
            or at_table(world, target) is not None or conversation_of(world, actor_id) is not None
            or pressed(world, target)):
        return None
    limit = world["rules"]["long_wait"]
    for walker in world["actors"]:
        action = walker["action"]
        if action is None or action["target_id"] != actor_id or not ACTIVITIES[action["verb"]].approaches:
            continue
        if walker["status"] == "walking" or (walker["status"] == "waiting" and walker["_blocked_for"] < limit):
            return walker
    return None


def face_walkers(world: World) -> None:
    """Turn each guest being walked up to toward their walker, unless something else already holds their eyes.

    Args:
        world: World whose visitors' `facing` is updated in place; run after `expression.update_expression`, which
            leaves a guest facing nothing in particular (None) when no sound, hand-over or scene holds their eyes.
    """
    for actor in world["actors"]:
        walker = walker_toward(world, actor["id"]) if actor["facing"] is None else None
        if walker is not None:
            actor["facing"] = facing_toward((actor["x"], actor["y"]), (walker["x"], walker["y"]))
