"""Routes to interaction spots around furniture, other visitors, and their reservations."""

from collections.abc import Mapping
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.hall.navigation import find_path, select_interaction_spot
from tavern.hall.room import find_object, impassable_cells
from tavern.hall.staff import off_limits
from tavern.hall.state import Actor, find_actor
from tavern.social.scenes import at_table, side_by_side, within_reach


def reserved_spots(world: Mapping[str, Any], actor_id: str) -> list[tuple[int, int]]:
    """List cells other visitors hold: their seats and the spots they are heading for.

    Args:
        world: Current world.
        actor_id: Visitor whose own reservations are excluded.
    Returns:
        Seat cells of seated visitors, then interaction spots of targeted actions in progress.
    """
    seats = [(item["x"], item["y"]) for item in world["actors"]
             if item["id"] != actor_id and item.get("seat_id")]
    return seats + [tuple(item["_spot"]) for item in world["actors"]
            if item["id"] != actor_id and item.get("_spot") and item.get("action")
            and item["action"].get("target_id") is not None]


def _other_reservations(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    # A visitor already occupying an incoming reserved spot must be able to leave.
    return [cell for cell in reserved_spots(world, actor["id"])
            if cell != (actor["x"], actor["y"])]


def plan_route(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> tuple[list[int] | None, list[list[int]]] | None:
    """Choose the interaction spot for an action and the steps to reach it.

    Args:
        world: Current world.
        actor: Visitor who will walk.
        action: Validated action; `inspect` heads for unexplored or long-unseen places.
    Returns:
        The chosen spot and the cells to walk, excluding the start; (None, []) when the
        target vanished or there is nothing to inspect; None when no spot is reachable.
    """
    world_map = world["map"]
    obstacles = impassable_cells(world_map) + off_limits(world_map, actor) + _other_reservations(world, actor)
    start = (actor["x"], actor["y"])
    if action["verb"] == "inspect":
        return _inspection_plan(world, actor, obstacles)
    if ACTIVITIES[action["verb"]].approaches:
        partner = find_actor(world, action.get("target_id"))
        in_the_open = partner is not None and at_table(world, partner) is None
        return (_walk_up_plan if in_the_open else _approach_plan)(world, actor, action, obstacles)
    if ACTIVITIES[action["verb"]].closes_in:
        return _closing_plan(world, actor, action, obstacles)
    target = find_object(world_map, action.get("target_id"))
    if target is None:
        return None, []
    selected = select_interaction_spot(start, target["interaction_spots"], world_map["width"], world_map["height"], obstacles)
    return ([*selected[0]], [list(cell) for cell in selected[1][1:]]) if selected else None


def _approach_plan(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any],
                   obstacles: list[tuple[int, int]]) -> tuple[list[int] | None, list[list[int]]] | None:
    # A spot at the table the partner sits at that nobody stands on; the nearest by walking distance.
    world_map = world["map"]
    partner = find_actor(world, action.get("target_id"))
    table = find_object(world_map, at_table(world, partner)) if partner else None
    if table is None:
        return None, []
    standing = set(occupied_cells(world, actor))
    spots = [spot for spot in table["interaction_spots"] if tuple(spot) not in standing]
    selected = select_interaction_spot((actor["x"], actor["y"]), spots, world_map["width"], world_map["height"],
                                       obstacles)
    return ([*selected[0]], [list(cell) for cell in selected[1][1:]]) if selected else None


def _walk_up_plan(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any],
                  obstacles: list[tuple[int, int]]) -> tuple[list[int] | None, list[list[int]]] | None:
    # A free cell beside someone standing in the open: next to them if one is free, else within the reach of a chat;
    # either way a cell from which they would be side by side (no wall between), nearest by walking.
    world_map, partner = world["map"], find_actor(world, action.get("target_id"))
    if partner is None:
        return None, []
    taken = set(occupied_cells(world, actor)) | set(obstacles)
    reach = world["rules"]["conversation"]["reach"]
    for radius in range(1, reach + 1):
        cells = [(x, y) for x in range(partner["x"] - radius, partner["x"] + radius + 1)
                 for y in range(partner["y"] - radius, partner["y"] + radius + 1)
                 if 0 <= x < world_map["width"] and 0 <= y < world_map["height"] and (x, y) not in taken
                 and max(abs(x - partner["x"]), abs(y - partner["y"])) == radius
                 and side_by_side(world, {**actor, "x": x, "y": y, "path": [], "status": "idle", "seat_id": None}, partner)]
        selected = select_interaction_spot((actor["x"], actor["y"]), cells, world_map["width"], world_map["height"],
                                           obstacles)
        if selected:
            return [*selected[0]], [list(cell) for cell in selected[1][1:]]
    return None


def _closing_plan(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any],
                  obstacles: list[tuple[int, int]]) -> tuple[list[int] | None, list[list[int]]] | None:
    # Someone already within reach acts where they stand; otherwise they walk to a free spot at the table the person sits at.
    person = find_actor(world, action.get("target_id"))
    if person is not None and within_reach(world, actor, person):
        return None, []
    return _approach_plan(world, actor, action, obstacles)


def _inspection_plan(world: Mapping[str, Any], actor: Mapping[str, Any], obstacles: list[tuple[int, int]]) -> tuple[list[int] | None, list[list[int]]]:
    world_map = world["map"]
    explored = set(map(tuple, actor["knowledge"]["cells"]))
    start = (actor["x"], actor["y"])
    occupied = set(occupied_cells(world, actor)) | {
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


def occupied_cells(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    """List the cells where other visitors stand right now.

    Args:
        world: Current world.
        actor: Visitor excluded from the list.
    Returns:
        Every other visitor's cell.
    """
    return [(item["x"], item["y"]) for item in world["actors"] if item["id"] != actor["id"]]


def replan(world: Mapping[str, Any], actor: Actor) -> bool:
    """Find a new way around people blocking the route to the chosen spot.

    Args:
        world: Current world.
        actor: Walking visitor; their path is replaced when a new route exists.
    Returns:
        Whether a route was found.
    """
    if actor["_spot"] is None:
        return False
    world_map = world["map"]
    obstacles = (impassable_cells(world_map) + off_limits(world_map, actor) + occupied_cells(world, actor)
                 + _other_reservations(world, actor))
    path = find_path((actor["x"], actor["y"]), actor["_spot"], world_map["width"], world_map["height"], obstacles)
    if path:
        actor["path"] = [list(cell) for cell in path[1:]]
    return bool(path)


def gives_way(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether a blocked walker should hold still rather than sidestep.

    Args:
        world: Current world.
        actor: Blocked walker.
    Returns:
        True while another walker blocks the next cell and has the earlier-sorting ID.
    """
    # Two walkers meeting head-on would sidestep in mirror image forever: the one whose ID sorts
    # later holds still for up to a second while the other steps around it.
    if not actor["path"] or actor["_blocked_for"] >= 1.0:
        return False
    occupant = next((item for item in world["actors"] if [item["x"], item["y"]] == list(actor["path"][0])), None)
    return occupant is not None and occupant["status"] in ("walking", "waiting") and occupant["id"] < actor["id"]
