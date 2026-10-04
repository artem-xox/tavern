"""Bartending: the barkeep's routine of pouring each guest's mug at the tap, in the order they come."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.lifecycle import activate, complete_action
from tavern.hall.memory import record_event
from tavern.hall.navigation import find_path
from tavern.hall.room import impassable_cells
from tavern.hall.staff import off_limits, on_staff, pour_cell, post_of
from tavern.hall.state import Actor, World, find_actor

POUR = {"id": "pour_beer", "verb": "pour_beer", "target_id": None}


def order_at(world: Mapping[str, Any], tap: Mapping[str, Any]) -> Actor | None:
    """Find the guest waiting at a tap for a mug.

    Args:
        world: Current world.
        tap: Tap, whose reservation the guest holds.

    Returns:
        The guest who holds the tap and has reached its spot to take a beer, or None.
    """
    guest = find_actor(world, tap["reserved_by"])
    action = None if guest is None else guest["action"]
    if guest is None or action is None or guest["status"] != "interacting":
        return None
    return guest if action["verb"] == "take_beer" and action["target_id"] == tap["id"] else None


def tend_bar(world: World) -> None:
    """Let each barkeep hand over the mug they have poured, or start pouring for a guest who waits.

    Args:
        world: World whose staff and guests are updated in place. A pour takes `durations.pour_beer` seconds
            and is started from the pour cell of the barkeep's bar, to which he walks over his staff cells
            first; it takes him out of any conversation. At its end the guest's own `take_beer` completes
            (the stock falls, the mug is theirs); a guest who went away meanwhile gets nothing and the
            stock stays.
    """
    for barkeep in [actor for actor in world["actors"] if on_staff(actor)]:
        action = barkeep["action"]
        if action is not None and action["verb"] == "pour_beer":
            if barkeep["status"] == "interacting" and barkeep["_remaining"] <= 0:
                _hand_over(world, barkeep)
        elif _waiting_guest(world) is not None:
            _start_pouring(world, barkeep)


def _waiting_guest(world: Mapping[str, Any]) -> Actor | None:
    taps = (item for item in world["map"]["objects"] if item["kind"] == "tap")
    return next((guest for guest in (order_at(world, tap) for tap in taps) if guest is not None), None)


def _hand_over(world: World, barkeep: Actor) -> None:
    guest = _waiting_guest(world)
    if guest is not None:
        complete_action(world, guest)
        record_event(world, barkeep, "served", f"{barkeep['name']} poured {guest['name']} a mug of ale")
    complete_action(world, barkeep)


def _start_pouring(world: World, barkeep: Actor) -> None:
    world_map, here = world["map"], (barkeep["x"], barkeep["y"])
    cell = pour_cell(world_map, post_of(world_map, barkeep))
    obstacles = impassable_cells(world_map) + off_limits(world_map, barkeep)
    path = find_path(here, cell, world_map["width"], world_map["height"], obstacles)
    if path:
        activate(world, barkeep, POUR, ([*cell], [list(step) for step in path[1:]]))
