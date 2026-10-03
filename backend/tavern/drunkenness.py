"""How drunk visitors are: beers raise it, time wears it off, and its stage changes them."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any

from tavern.state import DrunkennessRules
from tavern.validation import number


@dataclass(frozen=True)
class DrunkStage:
    """One stage of drunkenness and what it does to a visitor.

    Attributes:
        name: `sober`, `tipsy`, `drunk` or `wasted`.
        floor: Lowest drunkenness (0–1) of the stage.
        inhibition: Multiplier on the urge to act on hostility (E20); 1 when sober.
        accuracy: Multiplier on the chance to land a blow (E21); 1 when sober.
        sway: How far the client sways the sprite, 0–1.
        speech: How drink colours their speech, for the briefing and line writers; empty when sober.
    """

    name: str
    floor: float
    inhibition: float
    accuracy: float
    sway: float
    speech: str


STAGES = (
    DrunkStage("sober", 0.0, 1.0, 1.0, 0.0, ""),
    DrunkStage("tipsy", 0.2, 1.3, 0.95, 0.15,
               "They are tipsy: a little louder and franker than usual, quick to laugh."),
    DrunkStage("drunk", 0.45, 1.7, 0.8, 0.45,
               "They are drunk: they talk loudly, slur a word now and then, and say what they would "
               "usually keep to themselves."),
    DrunkStage("wasted", 0.75, 2.2, 0.55, 0.9,
               "They are wasted: their speech is slurred, they ramble and repeat themselves, and they "
               "lose the thread of a conversation."),
)


def drunk_stage(level: Any) -> DrunkStage:
    """Find the stage a level of drunkenness falls in.

    Args:
        level: Drunkenness, 0 (sober) to 1 (as drunk as can be).

    Returns:
        The last stage whose floor the level reaches.

    Raises:
        ValueError: The level is not a number from 0 to 1.
    """
    value = number(level, "Drunkenness", 0, 1)
    return [stage for stage in STAGES if value >= stage.floor][-1]


def inhibition_modifier(level: float) -> float:
    """Tell how much drink loosens a visitor's restraint, for hostile options (E20).

    Args:
        level: Drunkenness, 0–1.

    Returns:
        A multiplier, 1 when sober and larger with each stage.

    Raises:
        ValueError: The level is not a number from 0 to 1.
    """
    return drunk_stage(level).inhibition


def fight_accuracy(level: float) -> float:
    """Tell how well a visitor still aims a blow, for fights (E21).

    Args:
        level: Drunkenness, 0–1.

    Returns:
        A multiplier on the hit chance, 1 when sober and smaller with each stage.

    Raises:
        ValueError: The level is not a number from 0 to 1.
    """
    return drunk_stage(level).accuracy


def speech_instruction(level: float) -> str:
    """Say in a plain sentence how drink colours a visitor's speech.

    Args:
        level: Drunkenness, 0–1.

    Returns:
        A sentence for the briefing (and line writers later); empty when sober.

    Raises:
        ValueError: The level is not a number from 0 to 1.
    """
    return drunk_stage(level).speech


def drink_beer(level: float, tolerance: float, rules: DrunkennessRules) -> float:
    """Raise drunkenness by one beer.

    Args:
        level: Drunkenness before, 0–1.
        tolerance: The visitor's tolerance trait, 0–1; 0.5 is a middling drinker.
        rules: `per_beer`, the rise for a middling drinker.

    Returns:
        The level plus `per_beer × (1.5 − tolerance)`, at most 1: a lightweight feels a
        beer half as much again, a hard drinker half as much.

    Raises:
        ValueError: The level or tolerance is not a number from 0 to 1.
    """
    rise = rules["per_beer"] * (1.5 - number(tolerance, "Tolerance", 0, 1))
    return min(1.0, number(level, "Drunkenness", 0, 1) + rise)


def sober_up(level: float, seconds: float, rules: DrunkennessRules) -> float:
    """Let drunkenness wear off.

    Args:
        level: Drunkenness before, 0–1.
        seconds: Game seconds passed.
        rules: `per_second`, how much wears off each second.

    Returns:
        The level less `per_second × seconds`, at least 0.

    Raises:
        ValueError: The level is not a number from 0 to 1, or the time is negative.
    """
    passed = number(seconds, "Elapsed time", 0, math.inf)
    return max(0.0, number(level, "Drunkenness", 0, 1) - rules["per_second"] * passed)


def wear_off(world: Mapping[str, Any], elapsed: float) -> None:
    """Let drink wear off a little for every visitor in the hall.

    Args:
        world: World with the `drunkenness` rules; visitors are updated in place.
        elapsed: Game seconds since the last tick.
    """
    for actor in world["actors"]:
        actor["drunkenness"] = sober_up(actor["drunkenness"], elapsed, world["rules"]["drunkenness"])


def check_drunkenness(actor: Mapping[str, Any], rules: Mapping[str, Any]) -> None:
    """Check a saved visitor's drunkenness and the saved drinking rules.

    Args:
        actor: Untrusted saved visitor record.
        rules: Untrusted saved world rules.

    Raises:
        ValueError: Drunkenness is missing or outside 0–1, or a rule is missing or negative.
    """
    number(actor.get("drunkenness"), "Saved drunkenness", 0, 1)
    drink = rules.get("drunkenness")
    if not isinstance(drink, dict) or set(drink) != {"per_beer", "per_second", "doze_per_second"}:
        raise ValueError("Invalid saved drinking rules")
    for key, value in drink.items():
        number(value, f"Saved drinking rule {key}", 0, math.inf)
