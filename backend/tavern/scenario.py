"""An evening's scenario, separate from the room: who is expected, when, and closing time."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import inf
from typing import Any, TypedDict

from tavern.arrival import arrival_ranges
from tavern.validation import number, unique_ids


class Guest(TypedDict):
    """A guest the scenario expects tonight; `arrives_at` is in game seconds after opening."""

    id: str
    name: str
    color: str
    sprite: str
    traits: dict[str, float]
    arrives_at: float


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
