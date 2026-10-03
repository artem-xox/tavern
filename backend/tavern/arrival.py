"""Visitors arriving for the evening: validated actor records, freshly drawn needs, the way in."""

from collections.abc import Mapping, Sequence
from random import Random
from typing import Any

from tavern.memory import record_event
from tavern.room import impassable_cells
from tavern.routes import reserved_spots
from tavern.sight import look_around
from tavern.validation import number, position


def create_actor(data: Mapping[str, Any], world_map: Mapping[str, Any]) -> dict[str, Any]:
    """Build a fresh visitor record with an empty evening ahead.

    Args:
        data: Actor definition with ID, cell, and optional name, color, sprite, needs, traits, beer,
            and the character card and ties of a scenario guest (validated by `scenario.parse_guest`).
            A visitor without a sprite of their own looks like the generic `visitor`.
        world_map: Validated map the visitor stands in.
    Returns:
        Serializable visitor state.
    Raises:
        ValueError: The cell is blocked or sprite, needs, traits, or beer are invalid.
    """
    x, y = position(data, world_map["width"], world_map["height"])
    if (x, y) in impassable_cells(world_map):
        raise ValueError("Actors must start on walkable cells")
    needs = {name: number(data.get("needs", {}).get(name, 30), name, 0, 100)
             for name in ("thirst", "fatigue", "bladder", "social", "boredom")}
    traits = {name: number(value, name, 0, 1) for name, value in data.get("traits", {}).items()}
    beer, sprite = data.get("inventory", {}).get("beer", 0), data.get("sprite", "visitor")
    if type(beer) is not int or beer < 0:
        raise ValueError("Inventory beer must be a nonnegative integer")
    if not isinstance(sprite, str) or not sprite:
        raise ValueError("Actor sprite must be a nonempty string")
    return dict(id=data["id"], name=data.get("name", data["id"]), color=data.get("color", "#d8ad68"),
                sprite=sprite, x=x, y=y, traits=traits, card=data.get("card"), ties=list(data.get("ties", [])),
                needs=needs, inventory={"beer": beer}, status="idle",
                action=None, path=[], seat_id=None, favorite_seat_id=None,
                visit={"seconds": 0.0, "beers": 0, "grievances": []},
                knowledge={"objects": {}, "cells": []}, memory=[],
                decision={"source": "local", "scores": {}, "error": None},
                facing=None, gaze=None, emote=None, interrupted_at=None,
                _move_elapsed=0.0, _remaining=0.0, _blocked_for=0.0, _spot=None)


def arrival_ranges(map_data: Mapping[str, Any]) -> dict[str, tuple[float, float]] | None:
    """Read the optional ranges arriving visitors' needs are drawn from.

    Args:
        map_data: Room definition with an optional `arrival.needs` section.
    Returns:
        [low, high] per need, or None without an arrival section.
    Raises:
        ValueError: The section names unknown needs or holds invalid ranges.
    """
    if "arrival" not in map_data:
        return None
    arrival = map_data["arrival"]
    if not isinstance(arrival, Mapping) or not isinstance(arrival.get("needs"), Mapping):
        raise ValueError("Arrival must map needs to [low, high] ranges")
    ranges = {}
    for need, bounds in arrival["needs"].items():
        if need not in ("thirst", "fatigue", "bladder", "social", "boredom"):
            raise ValueError("Arrival ranges must name known needs")
        if not isinstance(bounds, Sequence) or isinstance(bounds, str) or len(bounds) != 2:
            raise ValueError("Arrival need range must be [low, high]")
        low, high = (number(value, need, 0, 100) for value in bounds)
        if low > high:
            raise ValueError("Arrival need range must not be reversed")
        ranges[need] = (low, high)
    return ranges


def arriving(actors: Sequence[Mapping[str, Any]], ranges: Mapping[str, tuple[float, float]],
             seed: int) -> list[dict[str, Any]]:
    """Draw each visitor's needs for tonight.

    Args:
        actors: Actor definitions.
        ranges: [low, high] per need.
        seed: Evening seed.
    Returns:
        Copies of the definitions with drawn needs.
    """
    # Each evening draws fresh needs from its own seed; unlisted needs keep the room's values.
    rng = Random(seed)
    return [{**item, "needs": {**item.get("needs", {}),
                               **{need: rng.uniform(low, high) for need, (low, high) in ranges.items()}}}
            for item in actors]


def admit_arrivals(world: dict[str, Any]) -> None:
    """Let in the expected guests whose time has come, while a door spot is free for them.

    Args:
        world: World whose `expected` guests, kept in order of arrival, step onto a free
            interaction spot of a door, join its actors, and look around the hall.
    """
    # Guests queue outside in arrival order: the first waits for a free spot and holds back
    # those behind, so nobody ever appears on top of another visitor.
    while world["expected"] and world["expected"][0]["arrives_at"] <= world["time"]:
        cell = _free_entry(world, world["expected"][0]["id"])
        if cell is None:
            return
        guest = world["expected"].pop(0)
        actor = create_actor({**guest, "x": cell[0], "y": cell[1]}, world["map"])
        world["actors"].append(actor)
        record_event(world, actor, "arrival", f"{actor['name']} came in")
        look_around(world, actor)


def _free_entry(world: Mapping[str, Any], guest_id: str) -> tuple[int, int] | None:
    # Door spots are tried in the room's listed order. A spot is taken while someone stands on
    # it or walks there to use it, or while the operator has blocked it.
    taken = {(item["x"], item["y"]) for item in world["actors"]}
    taken.update(impassable_cells(world["map"]), reserved_spots(world, guest_id))
    spots = [(x, y) for item in world["map"]["objects"] if item["kind"] == "door"
             for x, y in item["interaction_spots"]]
    return next((spot for spot in spots if spot not in taken), None)
