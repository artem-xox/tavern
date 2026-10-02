"""Serializable authoritative tavern state and physical action execution."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.activities import ACTIVITIES
from tavern.arrival import admit_arrivals, arrival_ranges, arriving, create_actor
from tavern.closing import call_closing, inn_closed
from tavern.hearing import sound_activity
from tavern.memory import record_event
from tavern.room import create_map, find_object, impassable_cells
from tavern.routes import gives_way, occupied_cells, plan_route, replan, reserved_spots
from tavern.sight import line_visible, look_around, refresh_knowledge, visible_cells
from tavern.validation import number, unique_ids


def create_world(map_data: Mapping[str, Any], seed: int = 0) -> dict[str, Any]:
    """Create and validate an independently owned, serializable room snapshot.

    Args:
        map_data: Flat room definition with geometry, objects, and initial actors. An optional
            `arrival` section maps needs to [low, high] ranges: visitors then arrive with needs
            drawn from them and look around the hall as they come in.
        seed: Saved deterministic seed of the evening's arrivals and decision policy.

    Returns:
        New world state containing no references to the supplied room definition. Nobody
        else is expected and the inn never closes; `scenario.open_evening` sets both.

    Raises:
        ValueError: Layout, IDs, resources, arrival ranges, or actor values are invalid.
    """
    world_map = create_map(map_data)
    unique_ids(map_data.get("actors", []), "actor")
    ranges, listed = arrival_ranges(map_data), map_data.get("actors", [])
    actors = [create_actor(item, world_map)
              for item in (listed if ranges is None else arriving(listed, ranges, seed))]
    if len({(item["x"], item["y"]) for item in actors}) != len(actors):
        raise ValueError("Actors cannot overlap at startup")
    world = dict(schema_version=3, seed=seed, tick=0, time=0.0, paused=False, speed=1.0,
                 map=world_map, actors=actors, departed=[], expected=[], closes_at=None,
                 events=[], stimuli=[], next_stimulus_id=0, rules=_rules())
    for actor in actors:
        _look(world, actor)
        if ranges is not None:
            look_around(world, actor)
    return world


def _rules() -> dict[str, Any]:
    return {"move_seconds": 0.35, "blocked_timeout": 3.0, "vision_radius": 5,
            "need_rates": {"thirst": 0.18, "fatigue": 0.12, "bladder": 0.10,
                           "social": 0.18, "boredom": 0.25},
            "durations": {verb: activity.duration for verb, activity in ACTIVITIES.items()
                          if activity.duration is not None},
            # Each beer the pair has drunk beyond the first adds this much quarrel chance,
            # scaled by impatience (2 − both patience traits), up to quarrel_max.
            "quarrel_per_beer": 0.1, "quarrel_max": 0.5,
            # Salience at which a visitor glances at a sound, and at which it interrupts them;
            # each wall cell between a sound and a listener multiplies its loudness by wall_damping.
            "attention": {"glance": 0.15, "interrupt": 0.5, "wall_damping": 0.5,
                          "glance_seconds": 2.0, "turn_seconds": 3.0}}


def _actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any] | None:
    return next((item for item in world["actors"] if item["id"] == actor_id), None)


def _target(world: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any] | None:
    return find_object(world["map"], action.get("target_id"))


def _action_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    if not isinstance(action.get("id"), str) or not action["id"]:
        return "Action ID must be a nonempty string"
    verb = action.get("verb")
    if not isinstance(verb, str) or verb not in world["rules"]["durations"]:
        return "Unknown action verb"
    activity = ACTIVITIES[verb]
    if activity.partner:
        return _talk_error(world, actor, action)
    if activity.requires_item and actor["inventory"][activity.requires_item] <= 0:
        return f"No {activity.requires_item} in inventory"
    if activity.target_kinds:
        return _target_error(world, actor, action)
    if action.get("target_id") is not None:
        return "This action does not take a target"
    return None


def _target_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    target = _target(world, action)
    if target is None:
        return "Target no longer exists"
    activity = ACTIVITIES[action["verb"]]
    if target["kind"] not in activity.target_kinds:
        return "Target does not support this action"
    if target["reserved_by"] not in (None, actor["id"]):
        return "Target is reserved by another visitor"
    if activity.empty_target and target["stock"] <= 0:
        return activity.empty_target
    return None


def _seat(world: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any] | None:
    return _target(world, {"target_id": actor.get("seat_id")})


def _conversation(world: Mapping[str, Any], actor_id: str) -> dict[str, Any] | None:
    return next((item for item in world["actors"] if item.get("action")
                 and item["action"]["verb"] == "talk"
                 and actor_id in (item["id"], item["action"]["target_id"])), None)


def _talk_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    partner = _actor(world, action.get("target_id"))
    if partner is None or partner["id"] == actor["id"]:
        return "Choose another seated visitor to talk to"
    left, right = _seat(world, actor), _seat(world, partner)
    if not left or not right or not left.get("table_id") or left.get("table_id") != right.get("table_id"):
        return "Visitors must be seated at the same table"
    if abs(actor["x"] - partner["x"]) + abs(actor["y"] - partner["y"]) > 4:
        return "Conversation partner is too far away"
    conversation = _conversation(world, partner["id"])
    if conversation and conversation["id"] != actor["id"]:
        return "Visitor is already in a conversation"
    return None


def _clear_action(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    for target in world["map"]["objects"]:
        if target["reserved_by"] == actor["id"] and target["id"] != actor.get("seat_id"):
            target["reserved_by"] = None
    actor.update(action=None, status="idle", path=[], _spot=None,
                 _move_elapsed=0.0, _remaining=0.0, _blocked_for=0.0)


def _reject(world: Mapping[str, Any], actor: dict[str, Any], reason: str) -> dict[str, Any]:
    record_event(world, actor, "action_failed", reason)
    _look(world, actor)
    return {"accepted": False, "reason": reason}


def start_action(world: dict[str, Any], actor_id: str, action: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and start a physical action, replacing any current valid action.

    Args:
        world: Authoritative mutable world state.
        actor_id: Visitor to control.
        action: Nonempty ID, supported verb, and optional target ID.

    Returns:
        Acceptance flag and a human-readable refusal reason, or None on success.

    Raises:
        ValueError: Not raised for rejected commands; refusals are returned.
    """
    actor = _actor(world, actor_id)
    if actor is None:
        return {"accepted": False, "reason": "Unknown visitor"}
    reason = _action_error(world, actor, action)
    if reason:
        _notice_target(world, actor, action)
        return _reject(world, actor, reason)
    plan = plan_route(world, actor, action)
    if plan is None:
        return _reject(world, actor, "No reachable interaction spot")
    _activate(world, actor, action, plan)
    return {"accepted": True, "reason": None}


def _notice_target(world: Mapping[str, Any], actor: dict[str, Any], action: Mapping[str, Any]) -> None:
    # A visitor turned away from a known place learns why (it is busy or has run dry), so stale
    # memories do not send them back again and again.
    target = _target(world, action)
    if target is not None and target["id"] in actor["knowledge"]["objects"]:
        actor["knowledge"]["objects"][target["id"]] = {**deepcopy(target), "last_seen": world["time"]}


def _activate(world: Mapping[str, Any], actor: dict[str, Any], action: Mapping[str, Any],
              plan: tuple[list[int] | None, list[list[int]]]) -> None:
    if plan[1] or ACTIVITIES[action["verb"]].leaves_seat:
        actor["seat_id"] = None
    _clear_action(world, actor)
    actor.update(action={key: action.get(key) for key in ("id", "verb", "target_id")},
                 _spot=plan[0], path=plan[1], status="walking" if plan[1] else "interacting",
                 _remaining=world["rules"]["durations"][action["verb"]])
    target = _target(world, action)
    if target:
        target["reserved_by"] = actor["id"]
    record_event(world, actor, "action_started", f"{actor['name']} chose {action['verb']}")
    if not plan[1]:
        _begin_interaction(world, actor)


def _fail(world: Mapping[str, Any], actor: dict[str, Any], reason: str) -> None:
    _clear_action(world, actor)
    _reject(world, actor, reason)


def _yield_idle_occupant(world: Mapping[str, Any], actor: dict[str, Any], next_cell: tuple[int, int]) -> None:
    occupant = next((item for item in world["actors"] if (item["x"], item["y"]) == next_cell), None)
    if occupant is None or occupant["status"] != "idle" or occupant.get("seat_id"):
        return
    blocked = set(impassable_cells(world["map"]) + occupied_cells(world, occupant) + reserved_spots(world, occupant["id"]))
    x, y = next_cell
    cells = ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))
    free = next((cell for cell in cells if cell not in blocked and
                 0 <= cell[0] < world["map"]["width"] and 0 <= cell[1] < world["map"]["height"]), None)
    if free:
        _activate(world, occupant, {"id": "yield", "verb": "wait", "target_id": None}, ([*free], [[*free]]))


def _move(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
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
        actor.update(status="walking", _blocked_for=0.0)
    if not actor["path"]:
        _begin_interaction(world, actor)


def _wait_for_route(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
    actor.update(status="waiting", _move_elapsed=0.0)
    actor["_blocked_for"] += elapsed
    if gives_way(world, actor):
        return
    if replan(world, actor):
        actor["status"] = "walking"
    elif actor["_blocked_for"] >= world["rules"]["blocked_timeout"]:
        _fail(world, actor, "Route remained blocked; try again after the obstruction changes")


def _begin_interaction(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    reason = _action_error(world, actor, actor["action"])
    if reason:
        _fail(world, actor, reason)
    else:
        actor.update(status="interacting", _move_elapsed=0.0, _blocked_for=0.0)
        activity = ACTIVITIES[actor["action"]["verb"]]
        if activity.on_arrival:
            activity.on_arrival(world, actor, _target(world, actor["action"]))
        if activity.sound:
            sound_activity(world, actor, activity.sound, activity.doing)


def _interaction_error(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    action = actor["action"]
    reason = _action_error(world, actor, action)
    if reason:
        return reason
    if (actor["x"], actor["y"]) in impassable_cells(world["map"]):
        return "Interaction cell is blocked"
    target = _target(world, action)
    if target and [actor["x"], actor["y"]] not in target["interaction_spots"]:
        return "Visitor is outside the interaction spot"
    return None


def _apply_effect(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    action = actor["action"]
    activity = ACTIVITIES[action["verb"]]
    target = _actor(world, action["target_id"]) if activity.partner else _target(world, action)
    if activity.effect:
        activity.effect(world, actor, target)
    for need, change in activity.needs.items():
        actor["needs"][need] = min(100, max(0, actor["needs"][need] + change))


def _interact(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
    reason = _interaction_error(world, actor)
    if reason:
        _fail(world, actor, reason)
        return
    actor["_remaining"] -= elapsed
    if actor["_remaining"] <= 0:
        verb = actor["action"]["verb"]
        _apply_effect(world, actor)
        record_event(world, actor, "action_completed", f"{actor['name']} completed {verb}")
        _clear_action(world, actor)
        _look(world, actor)


def _step_actor(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
    for name, rate in world["rules"]["need_rates"].items():
        actor["needs"][name] = min(100, actor["needs"][name] + rate * elapsed)
    actor["visit"]["seconds"] += elapsed
    if actor["action"]:
        if actor["status"] == "waiting":
            _wait_for_route(world, actor, elapsed)
        elif actor["status"] == "walking":
            _move(world, actor, elapsed)
        elif actor["status"] == "interacting":
            _interact(world, actor, elapsed)
    _look(world, actor)


def step_world(world: dict[str, Any], dt: float) -> None:
    """Advance time, needs, movement, once-only action consequences, and arrivals.

    Args:
        world: Authoritative mutable world state.
        dt: Unscaled elapsed seconds; world speed is applied inside this function.

    Returns:
        None. Mutates the supplied world in place.

    Raises:
        ValueError: Delta time or speed is invalid.
    """
    elapsed = number(dt, "Delta time", 0, float("inf"))
    if world["paused"] or elapsed == 0:
        return
    elapsed *= number(world["speed"], "Speed", 0.01, 100)
    since = world["time"]
    world["time"] += elapsed
    world["tick"] += 1
    for actor in world["actors"]:
        _step_actor(world, actor, elapsed)
    _see_off(world)
    call_closing(world, since)
    admit_arrivals(world)


def _see_off(world: dict[str, Any]) -> None:
    # Visitors who stepped out keep their record, so the evening stays inspectable.
    for actor in [item for item in world["actors"] if "left_at" in item["visit"]]:
        world["actors"].remove(actor)
        world["departed"].append(actor)
        beers = actor["visit"]["beers"]
        record_event(world, actor, "departure",
                f"{actor['name']} left the inn after {beers} {'beer' if beers == 1 else 'beers'}")


def _look(world: Mapping[str, Any], actor: dict[str, Any]) -> list[list[int]]:
    # The world refreshes what each visitor knows every tick; only a decision needs the full,
    # copied observation, so the copying stays in observe_actor.
    visible = visible_cells(world, actor, world["rules"]["vision_radius"])
    refresh_knowledge(world, actor, visible)
    return visible


def observe_actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]:
    """Refresh and return a visitor's personal observation without private leaks.

    Args:
        world: World whose actor knowledge is refreshed in place.
        actor_id: Visitor making the observation.

    Returns:
        Own actor state, known object records, personal memories, map bounds, visible
        cells, and whether the inn has closed. Unseen resource changes remain remembered
        historical values.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = _actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    visible = _look(world, actor)
    return {"actor": deepcopy(actor), "objects": deepcopy(list(actor["knowledge"]["objects"].values())),
            "visitors": _visible_visitors(world, actor),
            "memory": deepcopy(actor["memory"][-10:]), "visible_cells": visible, "time": world["time"],
            "map": {"width": world["map"]["width"], "height": world["map"]["height"]},
            "closed": inn_closed(world)}


def _in_sight(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[dict[str, Any]]:
    walls = set(map(tuple, world["map"]["blocked"]))
    people = []
    for visitor in world["actors"]:
        # People in the hall are in plain sight from anywhere in it, so walls alone hide them.
        # What someone is doing is public; their needs, purse and memories are not.
        if visitor["id"] == actor["id"] or not line_visible(
                (actor["x"], actor["y"]), (visitor["x"], visitor["y"]), walls):
            continue
        seat, action = _seat(world, visitor), visitor["action"] or {}
        target = _target(world, action) or _actor(world, action.get("target_id"))
        people.append({key: visitor[key] for key in ("id", "name", "x", "y", "seat_id")})
        people[-1].update(table_id=seat.get("table_id") if seat else None,
                          available=_conversation(world, visitor["id"]) is None,
                          doing=action.get("verb"), target=target["name"] if target else None)
    return people


def _visible_visitors(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[dict[str, Any]]:
    # Only seated company is actionable in this small social demo.
    return [person for person in _in_sight(world, actor) if person["seat_id"]]


def observe_people(world: Mapping[str, Any], actor_id: str) -> list[dict[str, Any]]:
    """List everyone a visitor can see and what they are visibly doing.

    Args:
        world: Current world; it is not modified.
        actor_id: Visitor doing the looking.

    Returns:
        Public facts about each visible person: ID, name, cell, seat and table, whether they
        are free to talk, and their current action verb and target name. Needs, inventory,
        traits and memories stay private.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = _actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    return _in_sight(world, actor)
