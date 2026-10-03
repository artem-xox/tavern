"""The tunable rules of a new world: rates, timings and thresholds, each with the reason for its number."""

from tavern.activities import ACTIVITIES
from tavern.state import Rules


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
