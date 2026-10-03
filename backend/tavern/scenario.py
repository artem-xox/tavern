"""An evening's scenario, separate from the room: who is expected, when, and closing time."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from math import inf
import math
from typing import Any, NotRequired, TypedDict, cast

from tavern.arrival import admit_arrivals, arrival_ranges, arriving
from tavern.cards import Card, parse_card
from tavern.ties import OwnTie, Tie, own_ties, parse_own_ties, parse_ties
from tavern.state import World
from tavern.validation import number, unique_ids
from tavern.world import create_world


class Guest(TypedDict):
    """A guest the scenario expects tonight; `arrives_at` is in game seconds after opening.

    A guest cast from a character card carries the `card`, and their `traits` are its params.
    A guest with starting relationships carries them as `ties`, from their own side.
    """

    id: str
    name: str
    color: str
    sprite: str
    traits: dict[str, float]
    arrives_at: float
    card: NotRequired[Card]
    ties: NotRequired[list[OwnTie]]


class ExpectedGuest(Guest):
    """A guest still on the way, kept in the world's `expected` list with tonight's needs drawn."""

    needs: dict[str, float]


@dataclass(frozen=True)
class Scenario:
    """A validated evening plan; `closes_at` is in game seconds after opening.

    `ties` are the starting relationships between guests, in listed order: what later
    systems seed opinions and familiarity from.
    """

    guests: tuple[Guest, ...]
    arrival: dict[str, tuple[float, float]]
    closes_at: float
    seed: int | None
    ties: tuple[Tie, ...] = ()


def _fields(data: Any, required: set[str], optional: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    missing, unknown = required - data.keys(), data.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{label} is missing {sorted(missing)} or has unknown {sorted(unknown)}")
    return data


def parse_guest(data: Any) -> Guest:
    """Validate one guest expected tonight.

    Args:
        data: Guest record with exactly `id`, `name`, `color`, `sprite`, `traits` (names to
            0–1 values) and `arrives_at` (game seconds, at least 0), and optionally the `card`
            the guest is cast from and their `ties` (see `ties.own_ties`).
    Returns:
        The guest, with numbers as floats.
    Raises:
        ValueError: A field is missing, unknown, or malformed, or the guest's name, sprite or
            traits differ from their card's.
    """
    fields = _fields(data, {"id", "name", "color", "sprite", "traits", "arrives_at"}, {"card", "ties"}, "Guest")
    for key in ("id", "name", "color", "sprite"):
        if not isinstance(fields[key], str) or not fields[key]:
            raise ValueError(f"Guest {key} must be a nonempty string")
    if not isinstance(fields["traits"], Mapping):
        raise ValueError("Guest traits must map names to numbers")
    guest = Guest(id=fields["id"], name=fields["name"], color=fields["color"], sprite=fields["sprite"],
                  traits={name: number(value, name, 0, 1) for name, value in fields["traits"].items()},
                  arrives_at=number(fields["arrives_at"], "Arrival time", 0, inf))
    if "card" in fields:
        guest["card"] = _matching_card(guest, fields["card"])
    if "ties" in fields:
        guest["ties"] = parse_own_ties(fields["ties"])
    return guest


def _matching_card(guest: Guest, data: Any) -> Card:
    card = parse_card(data)
    if (card["name"], card["sprite"], card["params"]) != (guest["name"], guest["sprite"], guest["traits"]):
        raise ValueError(f"Guest {guest['id']!r} must have the name, sprite and params of card {card['id']!r}")
    return card


def parse_scenario(data: Any, cards: Mapping[str, Card] | None = None) -> Scenario:
    """Validate a scenario read from outside the game.

    Args:
        data: Decoded scenario with `guests`, `arrival` need ranges (as in a room's `arrival`
            section), `closes_at` in game seconds, an optional integer `seed` and optional
            starting `relationships` (see `ties.parse_ties`). A guest is either described
            inline with `traits`, or cast from a character card named by ID in `card`, with
            the card's name and sprite.
        cards: Character cards by ID. Without them only the schedule is read: guests cast from
            a card come with no card and middling traits.
    Returns:
        The scenario, with guests in their listed order, each holding their own ties.
    Raises:
        ValueError: A section is missing, unknown or malformed, there are no guests, guest IDs
            repeat, a guest would arrive at or after closing time, a guest's card is unknown
            or does not match them, or a relationship is invalid.
    """
    fields = _fields(data, {"guests", "arrival", "closes_at"}, {"seed", "relationships"}, "Scenario")
    closes_at = number(fields["closes_at"], "Closing time", 0, inf)
    seed = fields.get("seed")
    if seed is not None and type(seed) is not int:
        raise ValueError("Scenario seed must be an integer")
    guests = _guests(fields["guests"], closes_at, cards)
    ties = parse_ties(fields.get("relationships", []), [item["id"] for item in guests])
    # `arrival` is a required field above, so its ranges are never None here.
    arrival = cast(dict[str, tuple[float, float]], arrival_ranges(fields))
    return Scenario(guests=_with_ties(guests, ties), arrival=arrival, closes_at=closes_at, seed=seed, ties=ties)


def _guests(value: Any, closes_at: float, cards: Mapping[str, Card] | None) -> tuple[Guest, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise ValueError("Scenario guests must be a nonempty list")
    guests = tuple(parse_guest(_cast(item, cards)) for item in value)
    unique_ids(guests, "guest")
    late = [item["id"] for item in guests if item["arrives_at"] >= closes_at]
    if late:
        raise ValueError(f"Guests must arrive before closing time: {', '.join(late)}")
    return guests


def _cast(entry: Any, cards: Mapping[str, Card] | None) -> Any:
    # A scenario names a guest's card by ID; the guest record carries the card itself.
    if not isinstance(entry, Mapping) or "card" not in entry:
        return entry
    if "traits" in entry or not isinstance(entry["card"], str):
        raise ValueError("A guest cast from a card names the card by ID instead of listing traits")
    rest = {key: value for key, value in entry.items() if key != "card"}
    if cards is None:
        return {**rest, "traits": {}}
    if entry["card"] not in cards:
        raise ValueError(f"Unknown character card {entry['card']!r}")
    card = cards[entry["card"]]
    return {**rest, "traits": dict(card["params"]), "card": card}


def _with_ties(guests: Sequence[Guest], ties: Sequence[Tie]) -> tuple[Guest, ...]:
    # Only guests with ties carry the field, so guests without any keep their plain shape.
    names = {item["id"]: item["name"] for item in guests}
    held = {item["id"]: own_ties(item["id"], ties, names) for item in guests}
    return tuple(Guest(**item, ties=held[item["id"]]) if held[item["id"]] else item for item in guests)


def open_evening(room: Mapping[str, Any], scenario: Scenario, seed: int) -> World:
    """Open the inn for a scenario's evening.

    Args:
        room: Room definition. Its own `actors` and `arrival` sections are not used: the
            scenario says who comes tonight and how they arrive.
        scenario: Validated scenario.
        seed: Seed of tonight's arrival needs and decision policy.
    Returns:
        New world in which the guests due at opening have come in, as far as the door's free
        spots allow, and the others are expected in order of arrival.
    Raises:
        ValueError: The room is invalid or has no door for guests to come in by.
    """
    world = create_world({key: value for key, value in room.items() if key not in ("actors", "arrival")}, seed)
    if not any(item["kind"] == "door" for item in world["map"]["objects"]):
        raise ValueError("A scenario needs a door for its guests to come in by")
    world.update({"expected": _expected(scenario, seed), "closes_at": scenario.closes_at})
    admit_arrivals(world)
    return world


def _expected(scenario: Scenario, seed: int) -> list[ExpectedGuest]:
    # Tonight's needs are drawn at opening, in listed order, so the evening replays from its seed.
    # Sorting is stable: guests due at the same moment keep their listed order at the door.
    drawn = [cast(ExpectedGuest, deepcopy(item)) for item in arriving(scenario.guests, scenario.arrival, seed)]
    return sorted(drawn, key=lambda item: item["arrives_at"])


def check_saved_expected(world: Mapping[str, Any]) -> None:
    """Check the guests a saved world still expects.

    Args:
        world: Decoded save with `expected` and `closes_at`.
    Raises:
        ValueError: A guest lacks drawn needs, they are out of order or after closing, or an ID repeats.
    """
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
