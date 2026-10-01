"""Serializable authoritative tavern state and physical action execution."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import isfinite
from typing import Any

from tavern.navigation import find_path, select_interaction_spot


def _number(value: Any, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return float(value)


def _coordinate(value: Any, limit: int) -> int:
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError("Cell coordinates must be integers inside the map")
    return value


def _position(record: Mapping[str, Any], width: int, height: int) -> tuple[int, int]:
    return _coordinate(record.get("x"), width), _coordinate(record.get("y"), height)


def _unique(records: Sequence[Mapping[str, Any]], label: str) -> None:
    identifiers = [item.get("id") for item in records]
    if any(not isinstance(item, str) or not item for item in identifiers):
        raise ValueError(f"{label} require nonempty string IDs")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"Duplicate {label} IDs")


def _create_map(data: Mapping[str, Any]) -> dict[str, Any]:
    width, height = data.get("width"), data.get("height")
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("Map dimensions must be positive integers")
    result = {key: deepcopy(data.get(key, [])) for key in ("blocked", "objects")}
    result.update(width=width, height=height, tile_size=data.get("tile_size", 32))
    if type(result["tile_size"]) is not int or result["tile_size"] <= 0:
        raise ValueError("Tile size must be a positive integer")
    _validate_objects(result)
    return result


def _obstacles(world_map: Mapping[str, Any]) -> list[tuple[int, int]]:
    return [tuple(cell) for cell in world_map["blocked"]] + [
        cell for item in world_map["objects"] if not item.get("walkable", False)
        for cell in object_cells(item)]


def object_cells(item: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Return the complete rectangular footprint of furniture.

    Args:
        item: Validated object with an anchor and optional width/height in cells.
    Returns:
        Every occupied cell, including walkable chair seats.
    """
    return [(x, y) for y in range(item["y"], item["y"] + item.get("height", 1))
            for x in range(item["x"], item["x"] + item.get("width", 1))]


def _validate_footprint(item: Mapping[str, Any], world_map: Mapping[str, Any]) -> None:
    _position(item, world_map["width"], world_map["height"])
    for name in ("width", "height"):
        if type(item.get(name, 1)) is not int or item.get(name, 1) <= 0:
            raise ValueError("Furniture dimensions must be positive integers")
    for x, y in object_cells(item):
        _coordinate(x, world_map["width"])
        _coordinate(y, world_map["height"])
    if type(item.get("walkable", False)) is not bool:
        raise ValueError("Furniture walkability must be a boolean")
    if item.get("walkable") and item.get("kind") != "chair":
        raise ValueError("Only chair seats may be walkable furniture")


def _validate_objects(world_map: dict[str, Any]) -> None:
    _unique(world_map["objects"], "object")
    occupied = set()
    for item in world_map["objects"]:
        _validate_footprint(item, world_map)
        cells = set(object_cells(item))
        if cells & (occupied | set(map(tuple, world_map["blocked"]))):
            raise ValueError("Objects must occupy distinct unblocked cells")
        if item.get("kind") not in ("tap", "chair", "toilet", "table", "bar", "darts"):
            raise ValueError("Unknown object kind")
        occupied.update(cells)
        item.setdefault("interaction_spots", [])
        item.setdefault("name", item["id"])
        item.update(stock=item.get("stock", 0), reserved_by=None)
        if type(item["stock"]) is not int or item["stock"] < 0:
            raise ValueError("Object stock must be a nonnegative integer")
    _validate_spots(world_map)


def _validate_spots(world_map: Mapping[str, Any]) -> None:
    obstacles = _obstacles(world_map)
    # find_path performs strict validation of every static obstacle coordinate.
    find_path((0, 0), (0, 0), world_map["width"], world_map["height"], obstacles)
    for item in world_map["objects"]:
        spots = item.get("interaction_spots", [])
        if not spots and item["kind"] not in ("table", "bar"):
            raise ValueError("Every object needs an interaction spot")
        for spot in spots:
            if not find_path(spot, spot, world_map["width"], world_map["height"], obstacles):
                raise ValueError("Interaction spots must be walkable")
        if item.get("table_id") is not None and not any(
                table["id"] == item["table_id"] and table["kind"] == "table"
                for table in world_map["objects"]):
            raise ValueError("Chair table must refer to an existing table")


def _create_actor(data: Mapping[str, Any], world_map: Mapping[str, Any]) -> dict[str, Any]:
    x, y = _position(data, world_map["width"], world_map["height"])
    if (x, y) in _obstacles(world_map):
        raise ValueError("Actors must start on walkable cells")
    needs = {name: _number(data.get("needs", {}).get(name, 30), name, 0, 100)
             for name in ("thirst", "fatigue", "bladder", "social", "boredom")}
    traits = {name: _number(value, name, 0, 1) for name, value in data.get("traits", {}).items()}
    beer = data.get("inventory", {}).get("beer", 0)
    if type(beer) is not int or beer < 0:
        raise ValueError("Inventory beer must be a nonnegative integer")
    return dict(id=data["id"], name=data.get("name", data["id"]), color=data.get("color", "#d8ad68"),
                x=x, y=y, traits=traits, needs=needs, inventory={"beer": beer}, status="idle",
                action=None, path=[], seat_id=None, knowledge={"objects": {}, "cells": []}, memory=[],
                decision={"source": "local", "scores": {}, "error": None},
                _move_elapsed=0.0, _remaining=0.0, _blocked_for=0.0, _spot=None)


def create_world(map_data: Mapping[str, Any], seed: int = 0) -> dict[str, Any]:
    """Create and validate an independently owned, serializable room snapshot.

    Args:
        map_data: Flat room definition with geometry, objects, and initial actors.
        seed: Saved deterministic decision-policy seed.

    Returns:
        New world state containing no references to the supplied room definition.

    Raises:
        ValueError: Layout, IDs, resources, or actor values are invalid.
    """
    world_map = _create_map(map_data)
    _unique(map_data.get("actors", []), "actor")
    actors = [_create_actor(item, world_map) for item in map_data.get("actors", [])]
    if len({(item["x"], item["y"]) for item in actors}) != len(actors):
        raise ValueError("Actors cannot overlap at startup")
    world = dict(schema_version=1, seed=seed, tick=0, time=0.0, paused=False, speed=1.0,
                 map=world_map, actors=actors, events=[], rules=_rules())
    for actor in actors:
        observe_actor(world, actor["id"])
    return world


def _rules() -> dict[str, Any]:
    return {"move_seconds": 0.35, "blocked_timeout": 3.0, "vision_radius": 5,
            "need_rates": {"thirst": 0.18, "fatigue": 0.12, "bladder": 0.10,
                           "social": 0.18, "boredom": 0.25},
            "durations": {"take_beer": 0.8, "drink": 3.0, "rest": 3.0, "sit": 14.0,
                          "talk": 8.0, "play_darts": 10.0,
                          "use_toilet": 2.0, "inspect": 0.8, "wait": 1.0}}


def _actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any] | None:
    return next((item for item in world["actors"] if item["id"] == actor_id), None)


def _target(world: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any] | None:
    return next((item for item in world["map"]["objects"] if item["id"] == action.get("target_id")), None)


def _record(world: Mapping[str, Any], actor: dict[str, Any], kind: str, message: str) -> None:
    event = {"time": world["time"], "actor_id": actor["id"], "type": kind, "message": message}
    world["events"].append(event)
    actor["memory"].append(deepcopy(event))
    del world["events"][:-200]
    del actor["memory"][:-25]


def _action_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    if not isinstance(action.get("id"), str) or not action["id"]:
        return "Action ID must be a nonempty string"
    verb = action.get("verb")
    if not isinstance(verb, str) or verb not in world["rules"]["durations"]:
        return "Unknown action verb"
    if verb == "talk":
        return _talk_error(world, actor, action)
    if verb == "drink" and actor["inventory"]["beer"] <= 0:
        return "No beer in inventory"
    if verb in ("take_beer", "rest", "sit", "use_toilet", "play_darts"):
        return _target_error(world, actor, action)
    if action.get("target_id") is not None:
        return "This action does not take a target"
    return None


def _target_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    target = _target(world, action)
    if target is None:
        return "Target no longer exists"
    kind = {"take_beer": "tap", "rest": "chair", "sit": "chair",
            "use_toilet": "toilet", "play_darts": "darts"}[action["verb"]]
    if target["kind"] != kind:
        return "Target does not support this action"
    if target["reserved_by"] not in (None, actor["id"]):
        return "Target is reserved by another visitor"
    if action["verb"] == "take_beer" and target["stock"] <= 0:
        return "Beer tap is empty"
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


def _reserved_spots(world: Mapping[str, Any], actor_id: str) -> list[tuple[int, int]]:
    seats = [(item["x"], item["y"]) for item in world["actors"]
             if item["id"] != actor_id and item.get("seat_id")]
    return seats + [tuple(item["_spot"]) for item in world["actors"]
            if item["id"] != actor_id and item.get("_spot") and item.get("action")
            and item["action"].get("target_id") is not None]


def _other_reservations(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    # A visitor already occupying an incoming reserved spot must be able to leave.
    return [cell for cell in _reserved_spots(world, actor["id"])
            if cell != (actor["x"], actor["y"])]


def _plan(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> tuple[list[int] | None, list[list[int]]] | None:
    world_map = world["map"]
    obstacles = _obstacles(world_map) + _other_reservations(world, actor)
    start = (actor["x"], actor["y"])
    if action["verb"] == "inspect":
        return _inspection_plan(world, actor, obstacles)
    target = _target(world, action)
    if target is None:
        return None, []
    selected = select_interaction_spot(start, target["interaction_spots"], world_map["width"], world_map["height"], obstacles)
    return ([*selected[0]], [list(cell) for cell in selected[1][1:]]) if selected else None


def _inspection_plan(world: Mapping[str, Any], actor: Mapping[str, Any], obstacles: list[tuple[int, int]]) -> tuple[list[int] | None, list[list[int]]]:
    world_map = world["map"]
    explored = set(map(tuple, actor["knowledge"]["cells"]))
    start = (actor["x"], actor["y"])
    occupied = set(_occupied(world, actor)) | {
        tuple(item["_spot"]) for item in world["actors"]
        if item["id"] != actor["id"] and item.get("_spot") and item.get("action")}
    cells = [(x, y) for y in range(world_map["height"]) for x in range(world_map["width"])
             if (x, y) not in explored and (x, y) not in obstacles and (x, y) not in occupied]
    selected = select_interaction_spot(start, cells, world_map["width"], world_map["height"], obstacles)
    if selected is None:
        selected = _remembered_route(world, actor, obstacles, occupied)
    return ([*selected[0]], [list(cell) for cell in selected[1][1:]]) if selected else (None, [])


def _remembered_route(world: Mapping[str, Any], actor: Mapping[str, Any], obstacles: list[tuple[int, int]],
                      occupied: set[tuple[int, int]]) -> tuple[tuple[int, int], list[tuple[int, int]]] | None:
    world_map = world["map"]
    known = sorted(actor["knowledge"]["objects"].values(), key=lambda item: item["last_seen"])
    for item in known:
        spots = [cell for cell in item["interaction_spots"] if tuple(cell) not in occupied]
        selected = select_interaction_spot((actor["x"], actor["y"]), spots,
                                            world_map["width"], world_map["height"], obstacles)
        if selected:
            return selected
    return None


def _clear_action(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    for target in world["map"]["objects"]:
        if target["reserved_by"] == actor["id"] and target["id"] != actor.get("seat_id"):
            target["reserved_by"] = None
    actor.update(action=None, status="idle", path=[], _spot=None,
                 _move_elapsed=0.0, _remaining=0.0, _blocked_for=0.0)


def _reject(world: Mapping[str, Any], actor: dict[str, Any], reason: str) -> dict[str, Any]:
    _record(world, actor, "action_failed", reason)
    observe_actor(world, actor["id"])
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
        return _reject(world, actor, reason)
    plan = _plan(world, actor, action)
    if plan is None:
        return _reject(world, actor, "No reachable interaction spot")
    _activate(world, actor, action, plan)
    return {"accepted": True, "reason": None}


def _activate(world: Mapping[str, Any], actor: dict[str, Any], action: Mapping[str, Any],
              plan: tuple[list[int] | None, list[list[int]]]) -> None:
    if plan[1] or action["verb"] in ("take_beer", "use_toilet", "play_darts"):
        actor["seat_id"] = None
    _clear_action(world, actor)
    actor.update(action={key: action.get(key) for key in ("id", "verb", "target_id")},
                 _spot=plan[0], path=plan[1], status="walking" if plan[1] else "interacting",
                 _remaining=world["rules"]["durations"][action["verb"]])
    target = _target(world, action)
    if target:
        target["reserved_by"] = actor["id"]
    _record(world, actor, "action_started", f"{actor['name']} chose {action['verb']}")
    if not plan[1]:
        _begin_interaction(world, actor)


def _fail(world: Mapping[str, Any], actor: dict[str, Any], reason: str) -> None:
    _clear_action(world, actor)
    _reject(world, actor, reason)


def _occupied(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    return [(item["x"], item["y"]) for item in world["actors"] if item["id"] != actor["id"]]


def _replan(world: Mapping[str, Any], actor: dict[str, Any]) -> bool:
    if actor["_spot"] is None:
        return False
    world_map = world["map"]
    obstacles = _obstacles(world_map) + _occupied(world, actor) + _other_reservations(world, actor)
    path = find_path((actor["x"], actor["y"]), actor["_spot"], world_map["width"], world_map["height"], obstacles)
    if path:
        actor["path"] = [list(cell) for cell in path[1:]]
    return bool(path)


def _yield_idle_occupant(world: Mapping[str, Any], actor: dict[str, Any], next_cell: tuple[int, int]) -> None:
    occupant = next((item for item in world["actors"] if (item["x"], item["y"]) == next_cell), None)
    if occupant is None or occupant["status"] != "idle" or occupant.get("seat_id"):
        return
    blocked = set(_obstacles(world["map"]) + _occupied(world, occupant) + _reserved_spots(world, occupant["id"]))
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
        blocked = _obstacles(world["map"]) + _occupied(world, actor) + _reserved_spots(world, actor["id"])
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
    if _replan(world, actor):
        actor["status"] = "walking"
    elif actor["_blocked_for"] >= world["rules"]["blocked_timeout"]:
        _fail(world, actor, "Route remained blocked; try again after the obstruction changes")


def _begin_interaction(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    reason = _action_error(world, actor, actor["action"])
    if reason:
        _fail(world, actor, reason)
    else:
        actor.update(status="interacting", _move_elapsed=0.0, _blocked_for=0.0)
        if actor["action"]["verb"] == "sit":
            actor["seat_id"] = actor["action"]["target_id"]


def _interaction_error(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    action = actor["action"]
    reason = _action_error(world, actor, action)
    if reason:
        return reason
    if (actor["x"], actor["y"]) in _obstacles(world["map"]):
        return "Interaction cell is blocked"
    target = _target(world, action)
    if target and [actor["x"], actor["y"]] not in target["interaction_spots"]:
        return "Visitor is outside the interaction spot"
    return None


def _apply_effect(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    verb = actor["action"]["verb"]
    if verb == "take_beer":
        _target(world, actor["action"])["stock"] -= 1
        actor["inventory"]["beer"] += 1
    elif verb == "drink":
        actor["inventory"]["beer"] -= 1
        actor["needs"]["thirst"] = max(0, actor["needs"]["thirst"] - 60)
        actor["needs"]["bladder"] = min(100, actor["needs"]["bladder"] + 25)
    elif verb in ("rest", "sit", "use_toilet"):
        need = "fatigue" if verb == "rest" else "bladder"
        if verb == "sit":
            need = "fatigue"
        actor["needs"][need] = max(0, actor["needs"][need] - 65)
    elif verb == "play_darts":
        actor["needs"]["boredom"] = max(0, actor["needs"]["boredom"] - 65)
    elif verb == "talk":
        _complete_conversation(world, actor)


def _complete_conversation(world: Mapping[str, Any], actor: dict[str, Any]) -> None:
    partner = _actor(world, actor["action"]["target_id"])
    topics = ("stories from the road", "the inn's beer", "their next journey", "a game of darts")
    count = sum(item["type"] == "conversation" for item in actor["memory"])
    topic = topics[count % len(topics)]
    _share_places(actor, partner)
    _share_places(partner, actor)
    for visitor in (actor, partner):
        visitor["needs"]["social"] = max(0, visitor["needs"]["social"] - 60)
        _record(world, visitor, "conversation", f"{actor['name']} and {partner['name']} chatted about {topic}")


def _share_places(speaker: Mapping[str, Any], listener: dict[str, Any]) -> None:
    for identifier, known in speaker["knowledge"]["objects"].items():
        if known["kind"] not in ("tap", "toilet", "darts") or identifier in listener["knowledge"]["objects"]:
            continue
        listener["knowledge"]["objects"][identifier] = {**deepcopy(known), "heard_from": speaker["id"]}


def _interact(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
    reason = _interaction_error(world, actor)
    if reason:
        _fail(world, actor, reason)
        return
    actor["_remaining"] -= elapsed
    if actor["_remaining"] <= 0:
        verb = actor["action"]["verb"]
        _apply_effect(world, actor)
        _record(world, actor, "action_completed", f"{actor['name']} completed {verb}")
        _clear_action(world, actor)
        observe_actor(world, actor["id"])


def _step_actor(world: Mapping[str, Any], actor: dict[str, Any], elapsed: float) -> None:
    for name, rate in world["rules"]["need_rates"].items():
        actor["needs"][name] = min(100, actor["needs"][name] + rate * elapsed)
    if actor["action"]:
        if actor["status"] == "waiting":
            _wait_for_route(world, actor, elapsed)
        elif actor["status"] == "walking":
            _move(world, actor, elapsed)
        elif actor["status"] == "interacting":
            _interact(world, actor, elapsed)
    observe_actor(world, actor["id"])


def step_world(world: dict[str, Any], dt: float) -> None:
    """Advance time, needs, movement, and once-only action consequences.

    Args:
        world: Authoritative mutable world state.
        dt: Unscaled elapsed seconds; world speed is applied inside this function.

    Returns:
        None. Mutates the supplied world in place.

    Raises:
        ValueError: Delta time or speed is invalid.
    """
    elapsed = _number(dt, "Delta time", 0, float("inf"))
    if world["paused"] or elapsed == 0:
        return
    elapsed *= _number(world["speed"], "Speed", 0.01, 100)
    world["time"] += elapsed
    world["tick"] += 1
    for actor in world["actors"]:
        _step_actor(world, actor, elapsed)


def _line_visible(origin: tuple[int, int], target: tuple[int, int], blocked: set[tuple[int, int]]) -> bool:
    # Integer Bresenham visibility treats the endpoint itself as visible furniture.
    x, y = origin
    end_x, end_y = target
    dx, dy = abs(end_x - x), -abs(end_y - y)
    step_x, step_y = (1 if x < end_x else -1), (1 if y < end_y else -1)
    error = dx + dy
    while (x, y) != target:
        if (x, y) != origin and (x, y) in blocked:
            return False
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y
    return True


def _visible_cells(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[list[int]]:
    radius = world["rules"]["vision_radius"]
    origin = actor["x"], actor["y"]
    # Low tables and chairs block feet, but do not hide seated company.
    blocked = set(map(tuple, world["map"]["blocked"]))
    return [[x, y] for y in range(max(0, origin[1] - radius), min(world["map"]["height"], origin[1] + radius + 1))
            for x in range(max(0, origin[0] - radius), min(world["map"]["width"], origin[0] + radius + 1))
            if abs(x - origin[0]) + abs(y - origin[1]) <= radius and _line_visible(origin, (x, y), blocked)]


def _refresh_knowledge(world: Mapping[str, Any], actor: dict[str, Any], visible: list[list[int]]) -> None:
    cells = set(map(tuple, visible))
    remembered = set(map(tuple, actor["knowledge"]["cells"]))
    actor["knowledge"]["cells"] = [list(cell) for cell in sorted(remembered | cells)]
    for item in world["map"]["objects"]:
        if (item["x"], item["y"]) in cells:
            record = deepcopy(item)
            record["last_seen"] = world["time"]
            actor["knowledge"]["objects"][item["id"]] = record


def observe_actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]:
    """Refresh and return a visitor's personal observation without private leaks.

    Args:
        world: World whose actor knowledge is refreshed in place.
        actor_id: Visitor making the observation.

    Returns:
        Own actor state, known object records, personal memories, map bounds, and
        visible cells. Unseen resource changes remain remembered historical values.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = _actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    visible = _visible_cells(world, actor)
    _refresh_knowledge(world, actor, visible)
    return {"actor": deepcopy(actor), "objects": deepcopy(list(actor["knowledge"]["objects"].values())),
            "visitors": _visible_visitors(world, actor, visible),
            "memory": deepcopy(actor["memory"][-10:]), "visible_cells": visible,
            "map": {"width": world["map"]["width"], "height": world["map"]["height"]}}


def _visible_visitors(world: Mapping[str, Any], actor: Mapping[str, Any], visible: list[list[int]]) -> list[dict[str, Any]]:
    cells = set(map(tuple, visible))
    visitors = []
    for visitor in world["actors"]:
        # Only observable seated company is actionable in this small social demo.
        if visitor["id"] == actor["id"] or not visitor.get("seat_id") or (visitor["x"], visitor["y"]) not in cells:
            continue
        seat = _seat(world, visitor)
        visitors.append({key: visitor[key] for key in ("id", "name", "x", "y", "seat_id")})
        visitors[-1].update(table_id=seat.get("table_id") if seat else None,
                            available=_conversation(world, visitor["id"]) is None)
    return visitors
