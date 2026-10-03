"""The operator's debug commands: pause, speed, refill the tap, block a cell, force an action."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from tavern.hall.room import object_cells
from tavern.hall.state import World
from tavern.hall.validation import integer, number
from tavern.hall.world import start_action


def set_paused(world: World, command: Mapping[str, Any]) -> None:
    """Pause or resume the world.

    Args:
        world: World updated in place.
        command: `paused`, a boolean.

    Raises:
        ValueError: `paused` is not a boolean.
    """
    if not isinstance(command.get("paused"), bool):
        raise ValueError("paused must be a boolean")
    world["paused"] = command["paused"]


def set_speed(world: World, command: Mapping[str, Any]) -> None:
    """Set the world's speed.

    Args:
        world: World updated in place.
        command: `value`, a number from 0.25 to 8.

    Raises:
        ValueError: `value` is not a number in range.
    """
    world["speed"] = number(command.get("value"), "Speed", 0.25, 8)


def refill_tap(world: World, command: Mapping[str, Any]) -> None:
    """Add beer to a tap.

    Args:
        world: World updated in place.
        command: `object_id` of a tap and `amount`, an integer from 1 to 1000.

    Raises:
        ValueError: The amount is out of range or the ID names no tap.
    """
    amount = integer(command.get("amount"), "Amount", 1, 1000)
    target = next((item for item in world["map"]["objects"]
                   if item["id"] == command.get("object_id") and item["kind"] == "tap"), None)
    if target is None:
        raise ValueError("Unknown beer tap")
    target["stock"] += amount


def toggle_block(world: World, permanent_walls: Sequence[Sequence[int]], command: Mapping[str, Any]) -> None:
    """Block or unblock a floor cell.

    Args:
        world: World updated in place.
        permanent_walls: The room's own blocked cells, which cannot be removed.
        command: `x` and `y` of the cell and `blocked`, a boolean.

    Raises:
        ValueError: The cell is outside the map, a permanent wall is being removed, or the cell is under a
            visitor or a piece of furniture.
    """
    x = integer(command.get("x"), "Cell x", 0, world["map"]["width"] - 1)
    y = integer(command.get("y"), "Cell y", 0, world["map"]["height"] - 1)
    if not isinstance(command.get("blocked"), bool):
        raise ValueError("blocked must be a boolean")
    _validate_block(world, permanent_walls, [x, y], command["blocked"])
    cells = world["map"]["blocked"]
    if command["blocked"] and [x, y] not in cells:
        cells.append([x, y])
    elif not command["blocked"] and [x, y] in cells:
        cells.remove([x, y])


def _validate_block(world: World, permanent_walls: Sequence[Sequence[int]], cell: list[int], blocked: bool) -> None:
    if cell in permanent_walls and not blocked:
        raise ValueError("Permanent walls cannot be removed")
    if any([actor["x"], actor["y"]] == cell for actor in world["actors"]):
        raise ValueError("Cannot change the cell under a visitor")
    if any(tuple(cell) in object_cells(item) for item in world["map"]["objects"]):
        raise ValueError("Furniture cells cannot be changed")


def forced_action(world: World, command: Mapping[str, Any]) -> tuple[World, str]:
    """Make a visitor do something, if the world accepts it.

    Args:
        world: Current world; it is not modified.
        command: `actor_id` and `action` (`id`, `verb` and an optional `target_id`).

    Returns:
        The world with the action started, and the visitor's ID; the caller swaps it in.

    Raises:
        ValueError: The command is malformed, the visitor is unknown, or the world refuses the action.
    """
    actor_id = command.get("actor_id")
    if not isinstance(actor_id, str) or not isinstance(command.get("action"), dict):
        raise ValueError("Expected actor_id and action")
    if not any(actor["id"] == actor_id for actor in world["actors"]):
        raise ValueError("Unknown visitor")
    action = command["action"]
    if not isinstance(action.get("verb"), str) or not isinstance(action.get("id"), str):
        raise ValueError("Action id and verb must be strings")
    if action.get("target_id") is not None and not isinstance(action["target_id"], str):
        raise ValueError("Action target must be an object ID or null")
    trial = deepcopy(world)
    result = start_action(trial, actor_id, action)
    if not result["accepted"]:
        raise ValueError(result["reason"])
    return trial, actor_id
