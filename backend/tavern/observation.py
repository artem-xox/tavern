"""Checks on what a deciding visitor observes: their own state and the places they know."""

import math
from collections.abc import Mapping, Sequence
from typing import Any

from tavern.validation import number


def own_actor(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    """Check and return the deciding visitor's own state from their observation.

    Args:
        observation: Personal observation with the visitor's own `actor`.
    Returns:
        The actor record.
    Raises:
        ValueError: The actor, needs, inventory, traits, or visit are malformed.
    """
    actor = observation.get("actor")
    if not isinstance(actor, Mapping) or not isinstance(actor.get("id"), str) or not actor["id"]:
        raise ValueError("Observation must contain the NPC's own actor")
    needs, inventory, traits = actor.get("needs"), actor.get("inventory"), actor.get("traits", {})
    if not all(isinstance(value, Mapping) for value in (needs, inventory, traits)):
        raise ValueError("Actor needs, inventory and traits must be mappings")
    for name in ("thirst", "fatigue", "bladder"):
        number(needs.get(name), name, 0, 100)
    for name in ("social", "boredom"):
        number(needs.get(name, 0), name, 0, 100)
    beer = inventory.get("beer")
    if isinstance(beer, bool) or not isinstance(beer, int) or beer < 0:
        raise ValueError("Own beer inventory must be a nonnegative integer")
    for name in ("patience", "comfort", "curiosity"):
        number(traits.get(name, 0.5), name, 0, 1)
    _validate_visit(actor)
    return actor


def _validate_visit(actor: Mapping[str, Any]) -> None:
    # Observations built outside the world may omit the visit; that reads as a fresh arrival.
    visit = actor.get("visit", {})
    if not isinstance(visit, Mapping):
        raise ValueError("Visit must be a mapping")
    number(visit.get("seconds", 0), "Visit seconds", 0, math.inf)
    beers, grievances = visit.get("beers", 0), visit.get("grievances", [])
    if isinstance(beers, bool) or not isinstance(beers, int) or beers < 0:
        raise ValueError("Beers drunk must be a nonnegative integer")
    if not isinstance(grievances, list) or any(not isinstance(item, str) for item in grievances):
        raise ValueError("Grievances must be a list of strings")
    own = actor.get("favorite_seat_id")
    if own is not None and (not isinstance(own, str) or not own):
        raise ValueError("Own seat must be a chair ID or null")


def known_objects(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Check and return the places a visitor knows, one record per object.

    Args:
        observation: Personal observation with remembered `objects`.
    Returns:
        Known object records without duplicates, in first-seen order.
    Raises:
        ValueError: Records are malformed or two records of one object conflict.
    """
    objects = observation.get("objects")
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
        raise ValueError("Observation objects must be a sequence")
    known = {}
    for item in objects:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("Observed objects must have nonempty string IDs")
        if item.get("kind") not in ("tap", "chair", "toilet", "table", "bar", "darts", "door", "window", "fireplace"):
            raise ValueError("Unknown observed object kind")
        if "appeal" in item:
            number(item["appeal"], "Seat appeal", 0, 1)
        if not isinstance(item.get("interaction_spots", []), list):
            raise ValueError("Observed interaction spots must be a list")
        if item["id"] in known and known[item["id"]] != item:
            raise ValueError("Conflicting observations of the same object")
        reservation = item.get("reserved_by")
        if reservation is not None and (not isinstance(reservation, str) or not reservation):
            raise ValueError("Observed reservation must be an actor ID or null")
        stock = item.get("stock")
        if stock is not None and (isinstance(stock, bool) or not isinstance(stock, int) or stock < 0):
            raise ValueError("Observed stock must be a nonnegative integer or unknown")
        _check_line(item)
        known[item["id"]] = item
    return list(known.values())


def _check_line(item: Mapping[str, Any]) -> None:
    if "queue_spots" not in item and "queue" not in item:
        return
    spots, line = item.get("queue_spots"), item.get("queue", [])
    if not isinstance(spots, list) or not isinstance(line, list):
        raise ValueError("Observed queue spots and line must be lists")
    waiting = [entry.get("actor_id") if isinstance(entry, Mapping) else None for entry in line]
    if any(not isinstance(actor_id, str) or not actor_id for actor_id in waiting) or len(set(waiting)) != len(waiting):
        raise ValueError("Observed line must list distinct visitor IDs")
