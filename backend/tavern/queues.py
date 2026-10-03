"""Lines at places used one visitor at a time: joining, moving up, patience, giving up, cutting in.

A place with `queue_spots` keeps its line in `queue`, front first, as entries of `actor_id` and
`since`, the game time they joined or last chose to keep waiting. Whoever stands in line keeps the
place's action as their own; the place's reservation goes to the front of the line only once the
place is free and nobody stands on the way in, so a visitor walking out is never met head-on.
"""

from collections.abc import Mapping
from typing import Any, TypedDict

from tavern.activities import ACTIVITIES
from tavern.memory import record_event
from tavern.names import called
from tavern.thoughts import think
from tavern.room import find_object, line_approach
from tavern.routes import plan_route, replan


class LineEntry(TypedDict):
    """One visitor's place in a line: who, and since when they wait (game seconds)."""

    actor_id: str
    since: float


def check_lines(world: Mapping[str, Any]) -> None:
    """Check that every place with a line has a need that sets how long people wait for it.

    Args:
        world: New world with validated map and rules.
    Raises:
        ValueError: A place with a line has a kind without a need in `rules.queue_needs`.
    """
    for item in world["map"]["objects"]:
        if "queue" in item and item["kind"] not in world["rules"]["queue_needs"]:
            raise ValueError(f"No need sets the patience for a line at a {item['kind']}")


def line_of(world: Mapping[str, Any], actor_id: str) -> tuple[dict[str, Any], int] | None:
    """Find the line a visitor stands in.

    Args:
        world: Current world.
        actor_id: Visitor looked for.
    Returns:
        The place and their place in its line (0 is the front), or None when they are in no line.
    """
    for item in world["map"]["objects"]:
        for place, entry in enumerate(item.get("queue", [])):
            if entry["actor_id"] == actor_id:
                return item, place
    return None


def _free_for(world: Mapping[str, Any], item: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    # Someone still standing on the spot or on the way in, such as a guest leaving the WC, keeps
    # the place busy until they have walked clear of it.
    if item["reserved_by"] not in (None, actor["id"]):
        return False
    if item["queue"] and item["queue"][0]["actor_id"] != actor["id"]:
        return False
    way_in = set(line_approach(world["map"], item))
    return not any((other["x"], other["y"]) in way_in for other in world["actors"] if other["id"] != actor["id"])


def must_wait(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    """Tell whether a visitor starting an action has to stand in line for it.

    Args:
        world: Current world.
        actor: Visitor starting the action.
        action: Validated action.
    Returns:
        True when its target has a line and the visitor already stands in it, or the place is
        not free for them: in use, someone is on the way in or out, or others are waiting.
    """
    item = find_object(world["map"], action.get("target_id"))
    if item is None or "queue" not in item:
        return False
    found = line_of(world, actor["id"])
    return (found is not None and found[0] is item) or not _free_for(world, item, actor)


def line_full(item: Mapping[str, Any]) -> str | None:
    """Tell why nobody else can join a line.

    Args:
        item: Place with a line.
    Returns:
        A refusal reason when every queue spot is taken, else None.
    """
    return f"The line for {item['name']} is full" if len(item["queue"]) >= len(item["queue_spots"]) else None


def _cut(world: dict[str, Any], item: Mapping[str, Any], actor: dict[str, Any], passed: list[str]) -> None:
    people = {other["id"]: other for other in world["actors"]}
    if passed:
        record_event(world, actor, "line_cut", f"{actor['name']} cut in line for {item['name']}")
    for actor_id in passed:
        victim = people[actor_id]
        message = f"{actor['name']} cut in line ahead of {victim['name']} at {item['name']}"
        record_event(world, victim, "line_cut", message)
        think(victim, "line_cut", world["time"], f"{called(victim, actor)} cut in line ahead of me at {item['name']}",
              message, about=actor)


def join_line(world: dict[str, Any], item: dict[str, Any], actor: dict[str, Any], front: bool) -> None:
    """Put a visitor at the end of a line, or at its front when they cut in.

    Args:
        world: World whose event log records it.
        item: Place with a line that is not full.
        actor: Visitor not in this line.
        front: Whether they cut in ahead of everyone waiting, who are wronged by it.
    """
    passed = [entry["actor_id"] for entry in item["queue"]] if front else []
    entry: LineEntry = {"actor_id": actor["id"], "since": world["time"]}
    item["queue"].insert(0 if front else len(item["queue"]), entry)
    record_event(world, actor, "joined_line", f"{actor['name']} joined the line for {item['name']}")
    _cut(world, item, actor, passed)


def stay_in_line(world: dict[str, Any], item: dict[str, Any], actor: dict[str, Any], front: bool) -> None:
    """Keep a visitor in their line with renewed patience, moving them to the front if they cut in.

    Args:
        world: Current world.
        item: Place whose line they stand in.
        actor: Visitor in that line.
        front: Whether they push past everyone ahead of them.
    """
    found = line_of(world, actor["id"])
    if found is None:
        raise ValueError(f"{actor['name']} does not stand in a line")
    entry = item["queue"].pop(found[1])
    entry["since"] = world["time"]
    passed = [ahead["actor_id"] for ahead in item["queue"][:found[1]]] if front else []
    item["queue"].insert(0 if front else found[1], entry)
    _cut(world, item, actor, passed)


def leave_line(world: dict[str, Any], actor: dict[str, Any]) -> None:
    """Take a visitor out of the line they stand in, if any: they gave up or were called away.

    Args:
        world: World whose event log records it.
        actor: Visitor leaving.
    """
    found = line_of(world, actor["id"])
    if found is not None:
        del found[0]["queue"][found[1]]
        record_event(world, actor, "left_line", f"{actor['name']} left the line for {found[0]['name']}")


def out_of_patience(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor in line has waited as long as they are willing to.

    Args:
        world: Current world; `rules.queue_patience` holds the seconds anyone waits (`base`),
            plus seconds per unit of the `patience` trait, plus seconds per unit of `urgency`,
            how pressing the need the place relieves is (`rules.queue_needs`), from 0 to 1.
        actor: Visitor.
    Returns:
        True once that time has passed since they joined or last chose to keep waiting; False
        for anyone not in a line.
    """
    found = line_of(world, actor["id"])
    if found is None:
        return False
    item, place = found
    rules = world["rules"]["queue_patience"]
    urgency = actor["needs"][world["rules"]["queue_needs"][item["kind"]]] / 100
    limit = rules["base"] + rules["patience"] * actor["traits"].get("patience", 0.5) + rules["urgency"] * urgency
    return world["time"] - item["queue"][place]["since"] >= limit


def step_line(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    """Move a visitor in line up to their queue spot, or from the front to the place once it is free.

    Args:
        world: Current world.
        actor: Visitor with an action; nothing happens unless they stand in a line.
    """
    found = line_of(world, actor["id"])
    if found is None:
        return
    item, place = found
    if place == 0 and _free_for(world, item, actor):
        plan = plan_route(world, actor, actor["action"])
        if plan is not None:
            del item["queue"][0]
            item["reserved_by"] = actor["id"]
            actor.update(_spot=plan[0], path=plan[1], status="walking", _move_elapsed=0.0, _blocked_for=0.0)
            return
    spot = item["queue_spots"][place]
    if actor["_spot"] == spot:
        return
    # A spot someone still stands on is tried again on the next tick.
    previous, actor["_spot"] = actor["_spot"], spot
    if replan(world, actor):
        actor.update(status="walking", _blocked_for=0.0)
    else:
        actor["_spot"] = previous


def cut_in(world: Mapping[str, Any], action: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Read a `cut_in_line` action as the use of the place whose line it jumps.

    Args:
        world: Current world.
        action: Action with any verb.
    Returns:
        The action with the verb that uses the place (others unchanged), and a refusal reason
        when a cut targets no place with a line.
    """
    if action.get("verb") != "cut_in_line":
        return dict(action), None
    item = find_object(world["map"], action.get("target_id"))
    if item is None:
        return dict(action), "Target no longer exists"
    if "queue" not in item:
        return dict(action), "Target does not support this action"
    verb = next(verb for verb, activity in ACTIVITIES.items()
                if item["kind"] in activity.target_kinds and activity.duration is not None)
    return {**action, "verb": verb}, None
