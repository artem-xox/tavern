"""The lifecycle of an action: starting, walking, interacting, finishing or failing, and the lines and parts it joins."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.actions import action_error
from tavern.activities import ACTIVITIES
from tavern.hearing import sound_activity
from tavern.memory import record_event
from tavern.queues import join_line, leave_line, line_full, line_of, stay_in_line, step_line
from tavern.room import find_object, impassable_cells
from tavern.routes import gives_way, occupied_cells, replan, reserved_spots
from tavern.scenes import conversation_of, leave_conversation
from tavern.sight import refresh_knowledge, visible_cells
from tavern.state import Actor, World, find_actor


def _target(world: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any] | None:
    return find_object(world["map"], action.get("target_id"))


def clear_action(world: World, actor: Actor) -> None:
    """Drop a visitor's action: leave their line, release the places they held, and stand idle.

    Args:
        world: World whose places are updated in place.
        actor: Visitor, updated in place.
    """
    leave_line(world, actor)
    for target in world["map"]["objects"]:
        if target["reserved_by"] == actor["id"] and target["id"] != actor.get("seat_id"):
            target["reserved_by"] = None
    actor.update({"action": None, "status": "idle", "path": [], "_spot": None,
                  "_move_elapsed": 0.0, "_remaining": 0.0, "_blocked_for": 0.0})


def reject(world: World, actor: Actor, reason: str) -> dict[str, Any]:
    """Log a refused or failed action in the visitor's memory and let them look around.

    Args:
        world: World whose event log records it.
        actor: Visitor whose action was refused.
        reason: Why, in words.

    Returns:
        The refusal as `start_action` reports it: `accepted` False and the `reason`.
    """
    record_event(world, actor, "action_failed", reason)
    look(world, actor)
    return {"accepted": False, "reason": reason}


def talk_in_line(world: World, actor: Actor, action: Mapping[str, Any]) -> dict[str, Any]:
    """Talk to a neighbour while standing in line: it keeps the place, and eases the wait.

    Args:
        world: Current world.
        actor: Visitor in a line, validated by `tavern.actions`.
        action: Their `talk` or `join_conversation` command.

    Returns:
        Acceptance, as `start_action` reports it.

    Raises:
        ValueError: The visitor stands in no line, or the verb has no arrival effect.
    """
    found, activity = line_of(world, actor["id"]), ACTIVITIES[action["verb"]]
    if found is None or activity.on_arrival is None:
        raise ValueError(f"{action['verb']} cannot be done from a line")
    stay_in_line(world, found[0], actor, False)
    activity.on_arrival(world, actor, find_actor(world, action["target_id"]))
    if activity.sound:
        # The sound concerns the partner, as if the talk were the action they started.
        sound_activity(world, {**actor, "action": action}, activity.sound, activity.doing)
    return {"accepted": True, "reason": None}


def _part(world: World, actor: Actor, action: Mapping[str, Any]) -> None:
    # Starting anything but a part in a conversation takes a visitor out of theirs.
    if not ACTIVITIES[action["verb"]].partner:
        leave_conversation(world, actor)
        finish_parts(world)


def finish_parts(world: World) -> None:
    """End the part of every visitor whose conversation scene is over.

    Args:
        world: World whose visitors' actions are updated in place.
    """
    for actor in world["actors"]:
        action = actor["action"]
        if action and ACTIVITIES[action["verb"]].partner and conversation_of(world, actor["id"]) is None:
            record_event(world, actor, "action_completed", f"{actor['name']} completed {action['verb']}")
            clear_action(world, actor)


def line_up(world: World, actor: Actor, action: Mapping[str, Any],
            front: bool) -> dict[str, Any]:
    """Join the line of a busy place: stand up and walk to its end, or to its front when cutting in.

    Choosing the line they already stand in means waiting on.

    Args:
        world: Current world.
        actor: Visitor joining.
        action: Their command, targeting a place with a line.
        front: Whether they cut in.

    Returns:
        Acceptance, as `start_action` reports it; a full line refuses.

    Raises:
        ValueError: The action targets no place.
    """
    target = _target(world, action)
    if target is None:
        raise ValueError(f"Cannot line up for {action.get('target_id')!r}")
    found = line_of(world, actor["id"])
    if found is not None and found[0] is target:
        stay_in_line(world, target, actor, front)
        return {"accepted": True, "reason": None}
    full = line_full(target)
    if full:
        notice_target(world, actor, action)
        return reject(world, actor, full)
    _part(world, actor, action)
    actor["seat_id"] = None
    clear_action(world, actor)
    actor.update({"action": {key: action.get(key) for key in ("id", "verb", "target_id")}, "status": "queued",
                  "_remaining": world["rules"]["durations"][action["verb"]]})
    record_event(world, actor, "action_started", f"{actor['name']} chose {action['verb']}")
    join_line(world, target, actor, front)
    return {"accepted": True, "reason": None}


def notice_target(world: World, actor: Actor, action: Mapping[str, Any]) -> None:
    """Update a visitor's memory of the place they were turned away from.

    They learn why (it is busy or has run dry), so stale memories do not send them back again and
    again.

    Args:
        world: Current world.
        actor: Visitor, updated in place.
        action: The refused command.
    """
    target = _target(world, action)
    if target is not None and target["id"] in actor["knowledge"]["objects"]:
        actor["knowledge"]["objects"][target["id"]] = {**deepcopy(target), "last_seen": world["time"]}


def activate(world: World, actor: Actor, action: Mapping[str, Any],
             plan: tuple[list[int] | None, list[list[int]]]) -> None:
    """Start an accepted action: replace the current one, reserve the target and set off.

    Args:
        world: Current world.
        actor: Visitor, updated in place.
        action: Validated command.
        plan: Interaction spot and route to it from `routes.plan_route`; an empty route starts the
            interaction at once.
    """
    _part(world, actor, action)
    if plan[1] or ACTIVITIES[action["verb"]].leaves_seat:
        actor["seat_id"] = None
    clear_action(world, actor)
    actor.update({"action": {key: action.get(key) for key in ("id", "verb", "target_id")},
                  "_spot": plan[0], "path": plan[1], "status": "walking" if plan[1] else "interacting",
                  "_remaining": world["rules"]["durations"][action["verb"]]})
    target = _target(world, action)
    if target:
        target["reserved_by"] = actor["id"]
    record_event(world, actor, "action_started", f"{actor['name']} chose {action['verb']}")
    if not plan[1]:
        _begin_interaction(world, actor)


def _fail(world: World, actor: Actor, reason: str) -> None:
    clear_action(world, actor)
    reject(world, actor, reason)


def _yield_idle_occupant(world: World, actor: Actor, next_cell: tuple[int, int]) -> None:
    occupant = next((item for item in world["actors"] if (item["x"], item["y"]) == next_cell), None)
    if occupant is None or occupant["status"] != "idle" or occupant.get("seat_id"):
        return
    blocked = set(impassable_cells(world["map"]) + occupied_cells(world, occupant) + reserved_spots(world, occupant["id"]))
    x, y = next_cell
    cells = ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))
    free = next((cell for cell in cells if cell not in blocked and
                 0 <= cell[0] < world["map"]["width"] and 0 <= cell[1] < world["map"]["height"]), None)
    if free:
        activate(world, occupant, {"id": "yield", "verb": "wait", "target_id": None}, ([*free], [[*free]]))


def _move(world: World, actor: Actor, elapsed: float) -> None:
    actor["_move_elapsed"] += elapsed
    while actor["path"] and actor["_move_elapsed"] >= world["rules"]["move_seconds"]:
        next_cell = tuple(actor["path"][0])
        blocked = impassable_cells(world["map"]) + occupied_cells(world, actor) + reserved_spots(world, actor["id"])
        if next_cell in blocked:
            _yield_idle_occupant(world, actor, next_cell)
            _wait_for_route(world, actor, elapsed)
            return
        actor["x"], actor["y"] = actor["path"].pop(0)
        actor["_move_elapsed"] -= world["rules"]["move_seconds"]
        actor.update({"status": "walking", "_blocked_for": 0.0})
    if not actor["path"]:
        _begin_interaction(world, actor)


def _wait_for_route(world: World, actor: Actor, elapsed: float) -> None:
    actor.update({"status": "waiting", "_move_elapsed": 0.0})
    actor["_blocked_for"] += elapsed
    if gives_way(world, actor):
        return
    if replan(world, actor):
        actor["status"] = "walking"
    elif actor["_blocked_for"] >= world["rules"]["blocked_timeout"]:
        _fail(world, actor, "Route remained blocked; try again after the obstruction changes")


def _begin_interaction(world: World, actor: Actor) -> None:
    if line_of(world, actor["id"]) is not None:
        actor.update({"status": "queued", "_move_elapsed": 0.0, "_blocked_for": 0.0})
        return
    action = actor["action"]
    if action is None:
        raise ValueError(f"{actor['name']} has no action to begin")
    reason = action_error(world, actor, action)
    if reason:
        _fail(world, actor, reason)
    else:
        actor.update({"status": "interacting", "_move_elapsed": 0.0, "_blocked_for": 0.0})
        activity = ACTIVITIES[action["verb"]]
        if activity.on_arrival:
            partner = find_actor(world, action["target_id"]) if activity.partner else None
            activity.on_arrival(world, actor, partner or _target(world, action))
        if activity.sound:
            sound_activity(world, actor, activity.sound, activity.doing)


def _interaction_error(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    action = actor["action"]
    if action is None:
        raise ValueError(f"{actor['name']} has no action to carry on")
    reason = action_error(world, actor, action)
    if reason:
        return reason
    if (actor["x"], actor["y"]) in impassable_cells(world["map"]):
        return "Interaction cell is blocked"
    target = _target(world, action)
    if target and [actor["x"], actor["y"]] not in target["interaction_spots"]:
        return "Visitor is outside the interaction spot"
    return None


def _apply_effect(world: World, actor: Actor) -> None:
    action = actor["action"]
    if action is None:
        raise ValueError(f"{actor['name']} has no action to finish")
    activity = ACTIVITIES[action["verb"]]
    target = find_actor(world, action["target_id"]) if activity.partner else _target(world, action)
    if activity.effect:
        activity.effect(world, actor, target)
    for need, change in activity.needs.items():
        actor["needs"][need] = min(100, max(0, actor["needs"][need] + change))


def _interact(world: World, actor: Actor, elapsed: float) -> None:
    reason = _interaction_error(world, actor)
    if reason:
        _fail(world, actor, reason)
        return
    actor["_remaining"] -= elapsed
    # A part in a conversation lasts as long as the scene does (see `finish_parts`).
    action = actor["action"]
    if action is not None and actor["_remaining"] <= 0 and not ACTIVITIES[action["verb"]].partner:
        verb = action["verb"]
        _apply_effect(world, actor)
        record_event(world, actor, "action_completed", f"{actor['name']} completed {verb}")
        clear_action(world, actor)
        look(world, actor)


def step_actor(world: World, actor: Actor, elapsed: float) -> None:
    """Advance one visitor: their needs and visit clock, then their line, route or interaction.

    Args:
        world: Current world.
        actor: Visitor, updated in place.
        elapsed: Game seconds since the last tick.
    """
    for name, rate in world["rules"]["need_rates"].items():
        actor["needs"][name] = min(100, actor["needs"][name] + rate * elapsed)
    actor["visit"]["seconds"] += elapsed
    if actor["action"]:
        step_line(world, actor)
        if actor["status"] == "waiting":
            _wait_for_route(world, actor, elapsed)
        elif actor["status"] == "walking":
            _move(world, actor, elapsed)
        elif actor["status"] == "interacting":
            _interact(world, actor, elapsed)
    look(world, actor)


def look(world: Mapping[str, Any], actor: Actor) -> list[list[int]]:
    """Refresh what a visitor knows from where they stand.

    The world does this for every visitor each tick; only a decision needs the full, copied
    observation, so the copying stays in `world.observe_actor`.

    Args:
        world: Current world.
        actor: Visitor whose knowledge is updated in place.

    Returns:
        The cells they see.
    """
    visible = visible_cells(world, actor, world["rules"]["vision_radius"])
    refresh_knowledge(world, actor, visible)
    return visible
