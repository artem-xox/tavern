"""Seeded chance: the draws of an evening, the same on every replay and reloaded save."""

from collections.abc import Mapping
from random import Random
from typing import Any


def roll(world: Mapping[str, Any], *keys: str) -> float:
    """Draw a number for this evening, tick and set of keys.

    Args:
        world: World whose seed and tick the draw is tied to.
        keys: What the draw is for, such as two guest IDs or a guest and a reason.

    Returns:
        A number in [0, 1).
    """
    # Joined by colons, the form recorded evenings were played with, so replays do not change.
    return Random(":".join([str(world["seed"]), str(world["tick"]), *keys])).random()
