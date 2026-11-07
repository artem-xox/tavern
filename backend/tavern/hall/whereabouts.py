"""Where a visitor is: at which table or bar, and whom they can reach.

The functions are specified where their behavior is exercised: `tests/test_scenes.py`,
`tests/test_approach.py`, `tests/test_table_reach.py` and `tests/test_bar_chat.py`.
"""

from collections.abc import Mapping
from typing import Any

from tavern.hall.room import find_object
from tavern.hall.sightlines import line_visible
from tavern.hall.staff import on_staff


def table_of(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    """Tell at which table a visitor sits.

    Args:
        world: Current world.
        actor: Visitor.

    Returns:
        The table ID of their seat, or None when they are not seated at a table.
    """
    seat = find_object(world["map"], actor.get("seat_id"))
    return seat.get("table_id") if seat else None


def at_table(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    """Tell at which table a visitor is, seated or standing by it.

    Args:
        world: Current world.
        actor: Visitor.

    Returns:
        The table ID of their seat, else of the table on one of whose spots they stand, having arrived
        (the place to stand and talk with those seated there), else of the table whose chair they rest on
        without making it their seat, else None.
    """
    if actor.get("seat_id"):
        return table_of(world, actor)
    if actor["path"]:
        return None  # Still on the way: passing a spot is not standing at it.
    cell = [actor["x"], actor["y"]]
    # Someone merely passing over or standing on a chair's cell is not at its table; resting on it is.
    target = (actor.get("action") or {}).get("target_id")
    return next((str(item["id"]) if item["kind"] == "table" else str(item["table_id"])
                 for item in world["map"]["objects"]
                 if (item["kind"] == "table" or (item.get("table_id") and item["id"] == target))
                 and cell in item["interaction_spots"]), None)


def _lines(world: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
    # The place and position of everyone standing in a line (see `tavern.body.queues`).
    return {entry["actor_id"]: (item["id"], place) for item in world["map"]["objects"]
            for place, entry in enumerate(item.get("queue", []))}


def bar_of(world: Mapping[str, Any], person: Mapping[str, Any]) -> str | None:
    """Tell at which bar someone stands.

    Args:
        world: Current world.
        person: Visitor.

    Returns:
        The ID of the bar a guest stands on a spot of, or whose staff cells its staff member stands on;
        only those exact cells count, not the cells round them. None otherwise.
    """
    cell = [person["x"], person["y"]]
    for item in world["map"]["objects"]:
        if item["kind"] != "bar":
            continue
        if on_staff(person):
            cells = item.get("staff_cells", []) if person["post"] == item["id"] else []
        else:
            cells = item["interaction_spots"]
        if cell in cells:
            return str(item["id"])
    return None


def side_by_side(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Tell whether two standing visitors are close enough to talk.

    Args:
        world: Current world; `rules.conversation.reach` is how many cells apart they may stand.
        actor: One visitor.
        other: The other visitor.

    Returns:
        True when neither sits, and they stand next to each other in the same line, or both stand at
        the same bar (a guest on one of its spots, its staff member on a staff cell), however far apart, or
        neither is staff, walks or has steps left and they stand within reach of each other with no wall between.
    """
    if actor["id"] == other["id"] or actor.get("seat_id") or other.get("seat_id"):
        return False
    lines = _lines(world)
    mine, theirs = lines.get(actor["id"]), lines.get(other["id"])
    if mine and theirs:
        # Moving up one spot together keeps them side by side.
        return mine[0] == theirs[0] and abs(mine[1] - theirs[1]) == 1
    if "walking" in (actor["status"], other["status"]):
        return False
    at_bar = bar_of(world, actor)
    if at_bar is not None and at_bar == bar_of(world, other):
        return True
    if on_staff(actor) or on_staff(other) or actor["path"] or other["path"]:
        return False  # Staff meet guests only across their bar; a guest with steps left is still on their way.
    near = max(abs(actor["x"] - other["x"]), abs(actor["y"] - other["y"])) <= world["rules"]["conversation"]["reach"]
    return near and line_visible((actor["x"], actor["y"]), (other["x"], other["y"]),
                                 set(map(tuple, world["map"]["blocked"])))


def within_reach(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Tell whether two visitors are close enough to chat, hand something over or come to blows.

    Args:
        world: Current world.
        actor: One visitor.
        other: The other visitor.

    Returns:
        True when they are at one table, seated or standing by it (see `at_table`), or stand side by side
        (see `side_by_side`).
    """
    table = at_table(world, actor)
    return (table is not None and table == at_table(world, other)) or side_by_side(world, actor, other)
