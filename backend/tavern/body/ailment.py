"""Ailment: who comes in unwell tonight, and what a remedy does for them."""

from collections.abc import Mapping, Sequence
from random import Random
from typing import Any

from tavern.body.items import ITEMS
from tavern.hall.state import Actor
from tavern.hall.validation import number

# How much tiredness a remedy takes off a guest it cures: back from a fever's weakness to a middling evening.
RELIEF = 40.0


def parse_ailment(value: Any) -> float:
    """Validate a scenario's ailment.

    Args:
        value: A mapping with exactly `fatigue`, the tiredness (0–100) the unwell guest comes in with.

    Returns:
        That tiredness, as a float.

    Raises:
        ValueError: It is no mapping with exactly `fatigue`, or the tiredness is no number from 0 to 100.
    """
    if not isinstance(value, Mapping) or set(value) != {"fatigue"}:
        raise ValueError("A scenario's ailment is exactly {\"fatigue\": 0-100}")
    return number(value["fatigue"], "Ailment fatigue", 0, 100)


def carries_cure(inventory: Mapping[str, int]) -> bool:
    """Tell whether someone carries anything that cures the unwell.

    Args:
        inventory: Counts by item kind.

    Returns:
        True when they hold at least one of a kind that `Item.cures`.
    """
    return any(ITEMS[kind].cures and count > 0 for kind, count in inventory.items() if kind in ITEMS)


def eligible(guests: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """List the guests who may come in unwell: those who carry no cure themselves.

    Args:
        guests: Scenario guests, each with an optional `carries`.

    Returns:
        The guests who carry no cure, in listed order.
    """
    return [guest for guest in guests if not carries_cure(guest.get("carries", {}))]


def draw_ailing(guests: Sequence[Mapping[str, Any]], rng: Random) -> str:
    """Pick the guest who comes in unwell tonight.

    Args:
        guests: Scenario guests, in listed order (the order is part of the draw).
        rng: Source of the draw; the same seeded stream gives the same guest.

    Returns:
        The ID of one guest who carries no cure.

    Raises:
        ValueError: Every guest carries a cure, so nobody could fall ill.
    """
    choices = eligible(guests)
    if not choices:
        raise ValueError("The scenario's ailment needs a guest who carries no cure to fall ill")
    return str(rng.choice(choices)["id"])


def relieve(receiver: Actor) -> None:
    """Cure an unwell guest who took a remedy.

    Args:
        receiver: The guest, updated in place: no longer `ailing`, `RELIEF` less tired (never below 0).
    """
    receiver["ailing"] = False
    receiver["needs"]["fatigue"] = max(0.0, receiver["needs"]["fatigue"] - RELIEF)


def check_saved_ailing(person: Mapping[str, Any]) -> None:
    """Check a saved visitor's ailing flag.

    Args:
        person: Decoded visitor, in the hall or departed.

    Raises:
        ValueError: The flag is missing or not true or false.
    """
    if type(person.get("ailing")) is not bool:
        raise ValueError("Invalid saved ailing flag")
