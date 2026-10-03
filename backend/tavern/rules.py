"""The tunable rules of a new world: rates, timings and thresholds, each with the reason for its number."""

import math

from collections.abc import Mapping
from tavern.activities import ACTIVITIES
from tavern.expression import EMOTES
from tavern.state import Rules
from tavern.validation import number
from typing import Any


def default_rules() -> Rules:
    """Give a new world the game's tunable rules.

    Returns:
        A fresh set, owned by the caller: every world keeps its own copy in its save. Rates are
        per game second, distances in cells.
    """
    return {"move_seconds": 0.35, "blocked_timeout": 3.0, "vision_radius": 5,
            "need_rates": {"thirst": 0.18, "fatigue": 0.12, "bladder": 0.10,
                           "social": 0.18, "boredom": 0.25},
            "durations": {verb: activity.duration for verb, activity in ACTIVITIES.items()
                          if activity.duration is not None},
            # Each beer the pair has drunk beyond the first adds this much quarrel chance,
            # scaled by impatience (2 − both patience traits), up to quarrel_max.
            "quarrel_per_beer": 0.1, "quarrel_max": 0.5,
            # Seconds a visitor waits in line before reconsidering: base, plus this much per unit
            # of the patience trait and per unit of urgency of the need the place relieves.
            "queue_patience": {"base": 5.0, "patience": 40.0, "urgency": 30.0},
            "queue_needs": {"tap": "thirst", "toilet": "bladder", "darts": "boredom"},
            # Salience at which a visitor glances at a sound, and at which it interrupts them;
            # each wall cell between a sound and a listener multiplies its loudness by wall_damping.
            "attention": {"glance": 0.15, "interrupt": 0.5, "wall_damping": 0.5,
                          "glance_seconds": 2.0, "turn_seconds": 3.0},
            # How long each emote shows; a route blocked for long_wait seconds shows `waiting`.
            "emote_seconds": {"alert": 1.5, "confused": 2.5, "angry": 4.0, "affection": 3.0, "sleep": 5.0,
                              "waiting": 0.5},
            "long_wait": 2.0,
            # A middling drinker's rise per beer, how much wears off each second, and how often a
            # wasted guest at their table nods off, per second.
            "drunkenness": {"per_beer": 0.2, "per_second": 0.0005, "doze_per_second": 0.01},
            # Scenes (`tavern.scenes`, `tavern.turns`): seconds before the first line and per line
            # at least, reading speed, how long a claimed line may keep the others waiting, social
            # relief per friendly act, the wish for company below which a scene ends, its size, how
            # many cells apart guests may stand to talk, and the need that makes a partner decline.
            "conversation": {"opening": 0.5, "min_gap": 2.5, "chars_per_second": 15.0, "turn_timeout": 10.0,
                             "relief": 25.0, "satisfied": 25.0, "max_participants": 4, "reach": 2,
                             "pressing": 75.0}}


def check_rules(world: Mapping[str, Any]) -> None:
    """Check the rules saved with a world.

    Args:
        world: Decoded save whose `rules` must match `default_rules` in shape: positive rates, one
            duration per timed verb, all needs, and ordered attention thresholds.
    Raises:
        ValueError: A rule is missing, unknown or out of range.
    """
    rules = world["rules"]
    values = [rules["move_seconds"], rules["blocked_timeout"], rules["quarrel_per_beer"], rules["quarrel_max"],
              *rules["durations"].values(), *rules["need_rates"].values()]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Invalid saved simulation rates")
    if type(rules["vision_radius"]) is not int or not 0 <= rules["vision_radius"] <= 100:
        raise ValueError("Invalid saved vision radius")
    if set(rules["durations"]) != {verb for verb, activity in ACTIVITIES.items() if activity.duration is not None}:
        raise ValueError("Invalid saved action definitions")
    if set(rules["need_rates"]) != {"thirst", "fatigue", "bladder", "social", "boredom"}:
        raise ValueError("Invalid saved needs")
    patience = rules["queue_patience"]
    if set(patience) != {"base", "patience", "urgency"}:
        raise ValueError("Invalid saved patience in line")
    for value in patience.values():
        number(value, "Saved patience in line", 0, math.inf)
    if not isinstance(rules["queue_needs"], dict) or not set(rules["queue_needs"].values()) <= set(rules["need_rates"]):
        raise ValueError("Invalid saved needs behind lines")
    _validate_attention_rules(rules.get("attention"))
    lifetimes = rules.get("emote_seconds")
    if not isinstance(lifetimes, dict) or set(lifetimes) != set(EMOTES):
        raise ValueError("Invalid saved emote lifetimes")
    for value in [*lifetimes.values(), rules.get("long_wait")]:
        number(value, "Saved emote time", 0, math.inf)
    _validate_conversation_rules(rules.get("conversation"))


def _validate_conversation_rules(conversation: Any) -> None:
    keys = {"opening", "min_gap", "chars_per_second", "turn_timeout", "relief", "satisfied", "max_participants",
            "reach", "pressing"}
    if not isinstance(conversation, dict) or set(conversation) != keys:
        raise ValueError("Invalid saved conversation rules")
    for key in keys:
        number(conversation[key], f"Saved conversation rule {key}", 0, math.inf)
    if conversation["chars_per_second"] <= 0 or conversation["max_participants"] < 2:
        raise ValueError("Saved conversations could never be read or held")


def _validate_attention_rules(attention: Any) -> None:
    keys = {"glance", "interrupt", "wall_damping", "glance_seconds", "turn_seconds"}
    if not isinstance(attention, dict) or set(attention) != keys:
        raise ValueError("Invalid saved attention rules")
    for key in keys:
        number(attention[key], f"Saved attention rule {key}", 0, math.inf)
    if not 0 < attention["glance"] <= attention["interrupt"] or attention["wall_damping"] > 1:
        raise ValueError("Saved attention thresholds are out of order")
