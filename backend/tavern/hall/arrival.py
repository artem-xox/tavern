"""Visitors arriving for the evening: validated actor records, freshly drawn needs, the way in, the staff at their posts."""

from collections.abc import Mapping, Sequence
import math
from random import Random
from typing import Any

from tavern.body.items import check_inventory, empty_inventory
from tavern.hall.memory import record_event
from tavern.hall.room import impassable_cells
from tavern.hall.routes import reserved_spots
from tavern.hall.sight import look_around
from tavern.hall.staff import pour_cell, post_of
from tavern.hall.state import Actor, World
from tavern.hall.validation import number, position
from tavern.social.facts import starting_facts
from tavern.social.thoughts import seed_relations


def create_actor(data: Mapping[str, Any], world_map: Mapping[str, Any]) -> Actor:
    """Build a fresh visitor record with an empty evening ahead.

    Args:
        data: Actor definition with ID, cell, and optional name, color, sprite, needs, traits, inventory,
            whether they come in `ailing` (see `tavern.body.ailment`), and the character card and ties of a
            scenario guest (validated by `scenario.parse_guest`).
            A visitor without a sprite of their own looks like the generic `visitor`.
        world_map: Validated map the visitor stands in.
    Returns:
        Serializable visitor state.
    Raises:
        ValueError: The cell is blocked or sprite, needs, traits, or inventory are invalid.
    """
    x, y = position(data, world_map["width"], world_map["height"])
    if (x, y) in impassable_cells(world_map):
        raise ValueError("Actors must start on walkable cells")
    needs = {name: number(data.get("needs", {}).get(name, 30), name, 0, 100)
             for name in ("thirst", "fatigue", "bladder", "social", "boredom")}
    traits = {name: number(value, name, 0, 1) for name, value in data.get("traits", {}).items()}
    inventory, sprite = {**empty_inventory(), **data.get("inventory", {})}, data.get("sprite", "visitor")
    check_inventory(inventory)
    if not isinstance(sprite, str) or not sprite:
        raise ValueError("Actor sprite must be a nonempty string")
    ailing = data.get("ailing", False)
    if type(ailing) is not bool:
        raise ValueError(f"Actor ailing must be true or false, not {ailing!r}")
    return Actor(id=data["id"], name=data.get("name", data["id"]), color=data.get("color", "#d8ad68"),
                sprite=sprite, post=data.get("post"), x=x, y=y, traits=traits, card=data.get("card"),
                ties=list(data.get("ties", [])),
                needs=needs, inventory=inventory, status="idle",
                action=None, path=[], seat_id=None, favorite_seat_id=None,
                visit={"seconds": 0.0, "beers": 0}, thoughts=[],
                relations=_relations(data["id"], data.get("name", data["id"]), data.get("ties", [])),
                drunkenness=0.0, ailing=ailing,
                knowledge={"objects": {}, "cells": [], "facts": {}}, memory=[], heard=[],
                decision={"source": "local", "scores": {}, "error": None},
                facing=None, gaze=None, emote=None, interrupted_at=None, intention=None,
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


def admit_arrivals(world: World) -> None:
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
        actor = create_actor({**guest, "x": cell[0], "y": cell[1], "inventory": guest.get("carries", {})}, world["map"])
        actor["knowledge"]["facts"] = starting_facts(world["news"], actor["id"], world["time"])
        world["actors"].append(actor)
        record_event(world, actor, "arrival", f"{actor['name']} came in")
        if actor["ailing"]:
            record_event(world, actor, "arrived_unwell", f"{actor['name']} came in looking pale and feverish")
        look_around(world, actor)


def take_posts(world: World, members: Sequence[Mapping[str, Any]]) -> None:
    """Put the staff at their bars, before the first guest comes in.

    Args:
        world: New world. Each member becomes a visitor with every need at 0, standing on the pour cell of
            their bar and facing as its staff do, and looks around the hall.
        members: Scenario staff (`scenario.StaffMember`): a guest's fields but `arrives_at`, and a `post`.

    Raises:
        ValueError: A post is no bar with staff cells, or a bar already has a staff member.
    """
    for member in members:
        bar = post_of(world["map"], member)
        if any(item["post"] == member["post"] for item in world["actors"]):
            raise ValueError(f"The {bar['name']} already has a staff member")
        x, y = pour_cell(world["map"], bar)
        actor = create_actor({**member, "x": x, "y": y, "needs": {need: 0 for need in world["rules"]["need_rates"]}},
                             world["map"])
        actor["facing"] = bar["staff_facing"]
        world["actors"].append(actor)
        record_event(world, actor, "on_duty", f"{actor['name']} took his place behind the {bar['name']}")
        look_around(world, actor)


def _free_entry(world: Mapping[str, Any], guest_id: str) -> tuple[int, int] | None:
    # Door spots are tried in the room's listed order. A spot is taken while someone stands on
    # it or walks there to use it, or while the operator has blocked it.
    taken = {(item["x"], item["y"]) for item in world["actors"]}
    taken.update(impassable_cells(world["map"]), reserved_spots(world, guest_id))
    spots = [(x, y) for item in world["map"]["objects"] if item["kind"] == "door"
             for x, y in item["interaction_spots"]]
    return next((spot for spot in spots if spot not in taken), None)


def _relations(guest_id: str, name: str, ties: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # Old ties set a guest's opinions before they meet anyone tonight (see thoughts.seed_relations),
    # and old friends and rivals alike know each other's names.
    pairs = [{"a": guest_id, "b": tie["with"], "kind": tie["kind"]} for tie in ties]
    names = {guest_id: name, **{tie["with"]: tie["name"] for tie in ties}}
    return {other: {**relation, "knows_name": True}
            for other, relation in seed_relations(pairs, names).get(guest_id, {}).items()}


def check_saved_visit(visit: Any) -> None:
    """Check a saved visit tally.

    Args:
        visit: Decoded `visit` of a visitor: seconds, beers and, once gone, `left_at`.
    Raises:
        ValueError: A field is missing, negative or of the wrong type.
    """
    if not isinstance(visit, dict):
        raise ValueError("Invalid saved visit")
    # left_at appears only once the visitor has gone home.
    times = [visit.get("seconds"), visit.get("left_at", 0.0)]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in times):
        raise ValueError("Invalid saved visit time")
    if type(visit.get("beers")) is not int or visit["beers"] < 0:
        raise ValueError("Invalid saved beer count")
