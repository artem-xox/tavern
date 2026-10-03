"""What a visitor can see from their cell, and what they learn by seeing it."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.names import called
from tavern.room import find_object
from tavern.scenes import conversation_of, pressed, side_by_side
from tavern.state import Actor, find_actor


def line_visible(origin: tuple[int, int], target: tuple[int, int], blocked: set[tuple[int, int]]) -> bool:
    """Tell whether a straight line between two cells passes no blocked cell.

    Args:
        origin: Viewer's cell.
        target: Cell looked at.
        blocked: Cells that hide what lies behind them.
    Returns:
        True when nothing blocks the view between the cells.
    """
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


def visible_cells(world: Mapping[str, Any], actor: Mapping[str, Any], radius: int) -> list[list[int]]:
    """List the cells a visitor sees within a walking-distance radius.

    Args:
        world: Current world; only walls hide cells.
        actor: Viewer.
        radius: Maximum Manhattan distance.
    Returns:
        Visible cells in row order.
    """
    origin = actor["x"], actor["y"]
    # Low tables and chairs block feet, but do not hide seated company.
    blocked = set(map(tuple, world["map"]["blocked"]))
    return [[x, y] for y in range(max(0, origin[1] - radius), min(world["map"]["height"], origin[1] + radius + 1))
            for x in range(max(0, origin[0] - radius), min(world["map"]["width"], origin[0] + radius + 1))
            if abs(x - origin[0]) + abs(y - origin[1]) <= radius and line_visible(origin, (x, y), blocked)]


def look_around(world: Mapping[str, Any], actor: Actor) -> None:
    """Let a visitor stepping in through the door take in the whole hall.

    Args:
        world: Current world; walls still hide what lies behind them.
        actor: Newcomer whose knowledge is updated in place.
    """
    radius = world["map"]["width"] + world["map"]["height"]
    refresh_knowledge(world, actor, visible_cells(world, actor, radius))


def refresh_knowledge(world: Mapping[str, Any], actor: Actor, visible: list[list[int]]) -> None:
    """Remember the cells seen and the current state of every object anchored in them.

    A line is seen where it stands: a place whose queue spot is in sight is remembered too,
    with who waits for it, even when the place itself (a WC round a corner) is not.

    Args:
        world: Current world.
        actor: Viewer whose knowledge is updated in place.
        visible: Cells seen now.
    """
    cells = set(map(tuple, visible))
    remembered = set(map(tuple, actor["knowledge"]["cells"]))
    actor["knowledge"]["cells"] = [list(cell) for cell in sorted(remembered | cells)]
    for item in world["map"]["objects"]:
        if (item["x"], item["y"]) in cells or any(tuple(spot) in cells for spot in item.get("queue_spots", [])):
            record = deepcopy(item)
            record["last_seen"] = world["time"]
            actor["knowledge"]["objects"][item["id"]] = record


def people_in_sight(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[dict[str, Any]]:
    """List everyone a visitor can see and what they are visibly doing.

    Args:
        world: Current world; it is not modified.
        actor: Visitor doing the looking.

    Returns:
        Public facts about each visible person (see `world.observe_people`): ID, name as the
        viewer calls them, cell, seat and table, whether they are free to talk, their
        conversation, whether they stand beside the viewer, and their current verb and target name.
    """
    walls = set(map(tuple, world["map"]["blocked"]))
    people = []
    for visitor in world["actors"]:
        # People in the hall are in plain sight from anywhere in it, so walls alone hide them.
        # What someone is doing is public; their needs, purse and memories are not.
        if visitor["id"] == actor["id"] or not line_visible(
                (actor["x"], actor["y"]), (visitor["x"], visitor["y"]), walls):
            continue
        seat, action = find_object(world["map"], visitor.get("seat_id")), visitor["action"] or {}
        target = find_object(world["map"], action.get("target_id")) or find_actor(world, action.get("target_id"))
        # A stranger is known by their looks until the viewer learns their name.
        people.append({**{key: visitor[key] for key in ("id", "x", "y", "seat_id")}, "name": called(actor, visitor)})
        scene = conversation_of(world, visitor["id"])
        people[-1].update(table_id=seat.get("table_id") if seat else None,
                          available=scene is None and not pressed(world, visitor),
                          conversation=scene["id"] if scene else None,
                          beside=side_by_side(world, actor, visitor),
                          doing=action.get("verb"), target=target["name"] if target else None)
    return people
