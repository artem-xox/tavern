"""An evening's scenario, separate from the room: who is expected, when, and closing time."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from math import inf
from typing import Any, TypedDict

from tavern.arrival import admit_arrivals, arrival_ranges, arriving
from tavern.validation import number, unique_ids
from tavern.world import create_world


class Guest(TypedDict):
    """A guest the scenario expects tonight; `arrives_at` is in game seconds after opening."""

    id: str
    name: str
    color: str
    sprite: str
    traits: dict[str, float]
    arrives_at: float


class ExpectedGuest(Guest):
    """A guest still on the way, kept in the world's `expected` list with tonight's needs drawn."""

    needs: dict[str, float]


@dataclass(frozen=True)
class Scenario:
    """A validated evening plan; `closes_at` is in game seconds after opening."""

    guests: tuple[Guest, ...]
    arrival: dict[str, tuple[float, float]]
    closes_at: float
    seed: int | None


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
            0–1 values) and `arrives_at` (game seconds, at least 0).
    Returns:
        The guest, with numbers as floats.
    Raises:
        ValueError: A field is missing, unknown, or malformed.
    """
    fields = _fields(data, {"id", "name", "color", "sprite", "traits", "arrives_at"}, set(), "Guest")
    for key in ("id", "name", "color", "sprite"):
        if not isinstance(fields[key], str) or not fields[key]:
            raise ValueError(f"Guest {key} must be a nonempty string")
    if not isinstance(fields["traits"], Mapping):
        raise ValueError("Guest traits must map names to numbers")
    return Guest(id=fields["id"], name=fields["name"], color=fields["color"], sprite=fields["sprite"],
                 traits={name: number(value, name, 0, 1) for name, value in fields["traits"].items()},
                 arrives_at=number(fields["arrives_at"], "Arrival time", 0, inf))


def parse_scenario(data: Any) -> Scenario:
    """Validate a scenario read from outside the game.

    Args:
        data: Decoded scenario with `guests`, `arrival` need ranges (as in a room's `arrival`
            section), `closes_at` in game seconds and an optional integer `seed`.
    Returns:
        The scenario, with guests in their listed order.
    Raises:
        ValueError: A section is missing, unknown or malformed, there are no guests, guest IDs
            repeat, or a guest would arrive at or after closing time.
    """
    fields = _fields(data, {"guests", "arrival", "closes_at"}, {"seed"}, "Scenario")
    closes_at = number(fields["closes_at"], "Closing time", 0, inf)
    seed = fields.get("seed")
    if seed is not None and type(seed) is not int:
        raise ValueError("Scenario seed must be an integer")
    return Scenario(guests=_guests(fields["guests"], closes_at), arrival=arrival_ranges(fields),
                    closes_at=closes_at, seed=seed)


def _guests(value: Any, closes_at: float) -> tuple[Guest, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise ValueError("Scenario guests must be a nonempty list")
    guests = tuple(parse_guest(item) for item in value)
    unique_ids(guests, "guest")
    late = [item["id"] for item in guests if item["arrives_at"] >= closes_at]
    if late:
        raise ValueError(f"Guests must arrive before closing time: {', '.join(late)}")
    return guests


def open_evening(room: Mapping[str, Any], scenario: Scenario, seed: int) -> dict[str, Any]:
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
    world.update(expected=_expected(scenario, seed), closes_at=scenario.closes_at)
    admit_arrivals(world)
    return world


def _expected(scenario: Scenario, seed: int) -> list[ExpectedGuest]:
    # Tonight's needs are drawn at opening, in listed order, so the evening replays from its seed.
    # Sorting is stable: guests due at the same moment keep their listed order at the door.
    drawn = [ExpectedGuest(**deepcopy(item)) for item in arriving(scenario.guests, scenario.arrival, seed)]
    return sorted(drawn, key=lambda item: item["arrives_at"])
