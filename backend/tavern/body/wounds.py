"""Wounds: a visitor's health and condition, who is laid low, and what a remedy or a bad beating leads to."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from typing import Any

from tavern.body.ailment import relieve
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.hall.validation import number

# What state a visitor's body is in: whole, reeling for a moment after a shove, thrown down by one, knocked out cold,
# or on their feet again but groggy.
CONDITIONS = ("ok", "staggered", "down", "out", "groggy")
# The ones in which a visitor can do nothing: the `recover` action holds them until their time is up.
LOCKING = ("staggered", "down", "out")
# Health below which a visitor visibly bears a bruise, and below which they are battered.
HURT = 70.0
BATTERED = 40.0
# How long a knocked-out guest stays groggy on their feet: a remedy in that time puts them right, and with none they
# slip away home on their own (the body's rule, not a choice).
GROGGY_SECONDS = 30.0
# What a remedy puts back: enough that even a knocked-out guest is on the mend, over the line of being hurt.
MENDS = 60.0
# How long a shove leaves someone reeling, and how long it leaves them on the floor.
STAGGER_SECONDS = 2.0
DOWN_SECONDS = 6.0
# The verb that holds a visitor who is laid low.
RECOVER = "recover"


def health_of(actor: Mapping[str, Any]) -> float:
    """Tell a visitor's health, as far as a record that may be hand-made says.

    Args:
        actor: A visitor or an observed actor.

    Returns:
        Their health from 0 to 100; a record that keeps none is whole.
    """
    return float(actor.get("health", 100.0))


def hurt(actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor is visibly hurt.

    Args:
        actor: A visitor or an observed actor.

    Returns:
        True when their health is below `HURT`.
    """
    return health_of(actor) < HURT


def laid_out(actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor lies on the floor, thrown down or knocked out.

    Args:
        actor: A visitor or an observed actor.

    Returns:
        True when their condition is `down` or `out`.
    """
    return actor.get("condition", "ok") in ("down", "out")


def treat(actor: Actor) -> None:
    """Give a visitor a remedy's due: a fever eased and wounds mended.

    Args:
        actor: Visitor, updated in place: no longer `ailing` (and so much less tired, see `ailment.relieve`) and, where
            they were hurt or laid low, mended (see `mend`).
    """
    if actor["ailing"]:
        relieve(actor)
    if hurt(actor) or actor["condition"] != "ok":
        mend(actor)


def needs_cure(actor: Mapping[str, Any]) -> bool:
    """Tell whether a remedy would help a visitor.

    Args:
        actor: A visitor or an observed person.

    Returns:
        True when they are unwell (`ailing`) or hurt.
    """
    return bool(actor.get("ailing")) or hurt(actor)


def lay_low(actor: Actor, condition: str, until: float) -> None:
    """Put a visitor in a locking condition until a game time.

    Args:
        actor: Visitor, updated in place; the world's step holds them in `recover` until `until`.
        condition: One of `LOCKING`.
        until: Game time they are back on their feet.

    Raises:
        ValueError: The condition does not lock.
    """
    if condition not in LOCKING:
        raise ValueError(f"A visitor is laid low in one of {', '.join(LOCKING)}, not {condition!r}")
    actor["condition"], actor["condition_until"] = condition, until


def mend(actor: Actor) -> None:
    """Heal a visitor with a remedy: health back by `MENDS`, and a body that was down or groggy is up and whole.

    Args:
        actor: Visitor, updated in place; their health never goes above 100.
    """
    actor["health"] = min(100.0, health_of(actor) + MENDS)
    actor["condition"], actor["condition_until"] = "ok", None


@dataclass
class Stepped:
    """What a tick of wounds asks of the world: who stands up (their `recover` ends), who is thrown to the floor (they
    start it), and who slips away home groggy and untreated."""

    released: list[Actor] = field(default_factory=list)
    fallen: list[Actor] = field(default_factory=list)
    sent_home: list[Actor] = field(default_factory=list)


def step_wounds(world: World) -> Stepped:
    """Move every visitor's condition on: down becomes up, knocked out becomes groggy, groggy becomes home.

    Args:
        world: World whose visitors' conditions are updated in place and whose events are logged.

    Returns:
        The visitors to release from `recover`, to hold in it, and to send home.
    """
    now, stepped = world["time"], Stepped()
    for actor in world["actors"]:
        condition, until = actor["condition"], actor["condition_until"]
        lying = actor["action"] is not None and actor["action"]["verb"] == RECOVER
        if condition in LOCKING and until is not None and until > now:
            if not lying:
                stepped.fallen.append(actor)
            continue
        if condition == "out":
            actor["condition"], actor["condition_until"] = "groggy", now + GROGGY_SECONDS
            record_event(world, actor, "got_up", f"{actor['name']} got to their feet, groggy and bruised")
        elif condition in LOCKING:
            actor["condition"], actor["condition_until"] = "ok", None
        elif condition == "groggy" and until is not None and until <= now:
            actor["condition"], actor["condition_until"] = "ok", None
            stepped.sent_home.append(actor)
        if lying and actor["condition"] not in LOCKING:
            stepped.released.append(actor)
    return stepped


def check_saved_wounds(actor: Mapping[str, Any]) -> None:
    """Check a saved visitor's health and condition.

    Args:
        actor: Decoded visitor, in the hall or departed.

    Raises:
        ValueError: Health is no number from 0 to 100, the condition is unknown, or its end is missing where
            the condition has one, present where it has none, or not a time.
    """
    health: Any = actor.get("health")
    if type(health) not in (int, float) or not math.isfinite(health) or not 0 <= health <= 100:
        raise ValueError("Invalid saved health")
    condition, until = actor.get("condition"), actor.get("condition_until")
    if condition not in CONDITIONS:
        raise ValueError("Invalid saved condition")
    if (condition in (*LOCKING, "groggy")) != (until is not None):
        raise ValueError("A saved condition has an end exactly when it is not ok")
    if until is not None:
        number(until, "Saved condition end", 0, math.inf)
