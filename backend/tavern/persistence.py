"""Atomic JSON snapshots of the authoritative world."""

import json
import math
from pathlib import Path
from typing import Any, Mapping

from tavern.activities import ACTIVITIES
from tavern.navigation import find_path
from tavern.scenario import Guest, parse_guest
from tavern.validation import number
from tavern.world import create_world


def save_world(world: Mapping[str, Any], path: Path) -> None:
    """Save all serializable simulation state atomically.

    Args:
        world: Current authoritative state, including ongoing actions.
        path: Destination snapshot file.
    Raises:
        ValueError: State cannot be serialized or the file cannot be written.
    """
    try:
        encoded = json.dumps(world, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(encoded + "\n")
        temporary.replace(path)
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"Could not save the world: {error}") from error


def _validate_clock(world: Mapping[str, Any]) -> None:
    for key in ("time", "speed", "tick"):
        value = world.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid saved {key}")
    if world["time"] < 0 or world["tick"] < 0 or not 0.25 <= world["speed"] <= 8:
        raise ValueError("Saved clock is outside supported limits")
    if not isinstance(world.get("paused"), bool):
        raise ValueError("Invalid saved pause state")


def _validate_actor_runtime(world: Mapping[str, Any]) -> None:
    actor_ids = {actor["id"] for actor in world["actors"]}
    verbs = set(world["rules"]["durations"])
    for actor in world["actors"]:
        if actor.get("status") not in {"idle", "walking", "interacting", "waiting"}:
            raise ValueError("Invalid saved actor status")
        action = actor.get("action")
        if action is not None and (not isinstance(action, dict) or action.get("verb") not in verbs):
            raise ValueError("Invalid saved actor action")
        if not all(isinstance(actor.get(key), dict) for key in ("knowledge", "inventory", "decision")):
            raise ValueError("Incomplete saved actor state")
        if not isinstance(actor.get("memory"), list):
            raise ValueError("Invalid saved memories")
        if not isinstance(actor.get("sprite"), str) or not actor["sprite"]:
            raise ValueError("Invalid saved sprite")
        knowledge = actor["knowledge"]
        if not isinstance(knowledge.get("objects"), dict) or not isinstance(knowledge.get("cells"), list):
            raise ValueError("Invalid saved knowledge")
        for cell in knowledge["cells"]:
            _validate_cell(cell, world["map"])
        _validate_known_objects(knowledge["objects"], world)
        _validate_progress(actor, world["map"])
        _validate_seat(actor, world)
        _validate_visit(actor.get("visit"))
    for item in world["map"]["objects"]:
        if item.get("reserved_by") is not None and item["reserved_by"] not in actor_ids:
            raise ValueError("Saved reservation belongs to an unknown actor")


def _validate_known_objects(objects: Mapping[str, Any], world: Mapping[str, Any]) -> None:
    object_ids = {item["id"] for item in world["map"]["objects"]}
    for identifier, item in objects.items():
        if not isinstance(item, dict) or identifier not in object_ids or item.get("id") != identifier:
            raise ValueError("Invalid remembered object")
        if item.get("kind") not in {"tap", "toilet", "chair", "table", "bar", "darts", "door", "window", "fireplace"}:
            raise ValueError("Invalid remembered object kind")
        seen = item.get("last_seen")
        if type(seen) not in (int, float) or not math.isfinite(seen) or not 0 <= seen <= world["time"]:
            raise ValueError("Invalid observation time")
        for spot in item["interaction_spots"]:
            _validate_cell(spot, world["map"])


def _validate_cell(cell: Any, world_map: Mapping[str, Any]) -> None:
    if not isinstance(cell, list) or len(cell) != 2:
        raise ValueError("Invalid saved cell")
    for value, limit in zip(cell, (world_map["width"], world_map["height"])):
        if type(value) is not int or not 0 <= value < limit:
            raise ValueError("Saved cell is outside the map")


def _validate_progress(actor: Mapping[str, Any], world_map: Mapping[str, Any]) -> None:
    for key in ("_remaining", "_move_elapsed", "_blocked_for"):
        value = actor.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid saved action timer")
    path = actor.get("path")
    if not isinstance(path, list):
        raise ValueError("Invalid saved route")
    previous = [actor["x"], actor["y"]]
    for cell in path:
        _validate_cell(cell, world_map)
        if abs(cell[0] - previous[0]) + abs(cell[1] - previous[1]) != 1:
            raise ValueError("Saved route contains a nonadjacent step")
        previous = cell
    if actor.get("_spot") is not None:
        _validate_cell(actor["_spot"], world_map)


def _validate_geometry(world: Mapping[str, Any]) -> None:
    world_map = world["map"]
    # Dynamic obstacles may cover a valid interaction spot at save time.
    # Validate object geometry separately, then validate all obstacle coordinates.
    create_world({**world_map, "blocked": [], "actors": world["actors"]})
    find_path((0, 0), (0, 0), world_map["width"], world_map["height"], world_map["blocked"])
    if any([actor["x"], actor["y"]] in world_map["blocked"] for actor in world["actors"]):
        raise ValueError("Saved visitor occupies a blocked cell")


def _validate_visit(visit: Any) -> None:
    if not isinstance(visit, dict) or not isinstance(visit.get("grievances"), list):
        raise ValueError("Invalid saved visit")
    # left_at appears only once the visitor has gone home.
    times = [visit.get("seconds"), visit.get("left_at", 0.0)]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in times):
        raise ValueError("Invalid saved visit time")
    if type(visit.get("beers")) is not int or visit["beers"] < 0:
        raise ValueError("Invalid saved beer count")
    if any(not isinstance(item, str) for item in visit["grievances"]):
        raise ValueError("Invalid saved grievance")


def _validate_departed(world: Mapping[str, Any]) -> None:
    departed = world.get("departed")
    if not isinstance(departed, list) or any(not isinstance(item, dict) for item in departed):
        raise ValueError("Invalid saved departures")
    ids = [item.get("id") for item in [*world["actors"], *departed]]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Saved visitors need unique IDs")
    for item in departed:
        _validate_visit(item.get("visit"))
        if "left_at" not in item["visit"]:
            raise ValueError("Departed visitor has no departure time")


def _validate_expected(world: Mapping[str, Any]) -> None:
    closes_at, expected = world.get("closes_at"), world.get("expected")
    if closes_at is not None:
        number(closes_at, "Saved closing time", 0, math.inf)
    if not isinstance(expected, list):
        raise ValueError("Invalid saved expected guests")
    guests = [_expected_guest(item, world) for item in expected]
    times = [item["arrives_at"] for item in guests]
    if times != sorted(times) or (closes_at is not None and any(time >= closes_at for time in times)):
        raise ValueError("Saved expected guests must arrive in order before closing")
    ids = [item["id"] for item in [*world["actors"], *world["departed"], *guests]]
    if len(set(ids)) != len(ids):
        raise ValueError("Saved visitors need unique IDs")


def _expected_guest(item: Any, world: Mapping[str, Any]) -> Guest:
    if not isinstance(item, dict) or not isinstance(item.get("needs"), dict):
        raise ValueError("Saved expected guest has no drawn needs")
    for need, value in item["needs"].items():
        if need not in world["rules"]["need_rates"]:
            raise ValueError(f"Unknown saved need {need!r}")
        number(value, need, 0, 100)
    return parse_guest({key: value for key, value in item.items() if key != "needs"})


def _validate_seat(actor: Mapping[str, Any], world: Mapping[str, Any]) -> None:
    chairs = {item["id"] for item in world["map"]["objects"] if item["kind"] == "chair"}
    if actor.get("favorite_seat_id") is not None and actor["favorite_seat_id"] not in chairs:
        raise ValueError("Invalid saved own seat")
    seat_id = actor.get("seat_id")
    if seat_id is None:
        return
    seat = next((item for item in world["map"]["objects"] if item["id"] == seat_id), None)
    if not seat or seat["kind"] != "chair" or seat.get("reserved_by") != actor["id"]:
        raise ValueError("Invalid saved seat reservation")
    if [actor["x"], actor["y"]] not in seat["interaction_spots"]:
        raise ValueError("Saved visitor is outside their seat")


def _validate_rules(world: Mapping[str, Any]) -> None:
    rules = world["rules"]
    values = [rules["move_seconds"], rules["blocked_timeout"], rules["quarrel_per_beer"], rules["quarrel_max"],
              *rules["durations"].values(), *rules["need_rates"].values()]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Invalid saved simulation rates")
    if type(rules["vision_radius"]) is not int or not 0 <= rules["vision_radius"] <= 100:
        raise ValueError("Invalid saved vision radius")
    if set(rules["durations"]) != {verb for verb, activity in ACTIVITIES.items() if activity.duration is not None}:
        raise ValueError("Invalid saved action definitions")
    if set(rules["need_rates"]) != {"thirst", "fatigue", "bladder", "social", "boredom"}:
        raise ValueError("Invalid saved needs")


def parse_world(encoded: str) -> dict[str, Any]:
    """Validate a serialized world before it replaces the running state.

    Args:
        encoded: JSON snapshot from a file or database.
    Returns:
        Complete world with action progress and memories preserved.
    Raises:
        ValueError: The snapshot is malformed or uses an unsupported state shape.
    """
    try:
        world = json.loads(encoded)
        if not isinstance(world, dict) or world.get("schema_version") != 2:
            raise ValueError("Unsupported snapshot version")
        json.dumps(world, allow_nan=False)
        _validate_clock(world)
        _validate_geometry(world)
        _validate_rules(world)
        _validate_actor_runtime(world)
        _validate_departed(world)
        _validate_expected(world)
        if not isinstance(world.get("events"), list):
            raise ValueError("Invalid saved event log")
        return world
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"Could not load the world: {error}") from error


def load_world(path: Path) -> dict[str, Any]:
    """Read and validate a saved world from disk.

    Args:
        path: Existing snapshot file.
    Returns:
        Validated world state.
    Raises:
        ValueError: The file is missing, unreadable, or invalid.
    """
    try:
        return parse_world(path.read_text())
    except OSError as error:
        raise ValueError(f"Could not load the world: {error}") from error
