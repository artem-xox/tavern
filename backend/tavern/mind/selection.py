"""How a decision is drawn from scored options: the temperature and the near-best draw."""

import math
from collections.abc import Collection, Mapping, Sequence
from random import Random
from typing import Any

from tavern.body.activities import ACTIVITIES


# Walking out is final: the verb, and the family that offers a choice between doors, which is just as final.
_FINAL = ("leave", ACTIVITIES["leave"].family)


def read_temperature(config: Mapping[str, Any]) -> float:
    """Read the selection temperature from the AI config.

    Args:
        config: AI config with a `temperature` entry.

    Returns:
        The temperature; 0 always picks the best option.

    Raises:
        ValueError: The temperature is missing, negative, not finite or not a number.
    """
    value = config.get("temperature")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Temperature must be a nonnegative finite number")
    return float(value)


def select(candidates: Sequence[Mapping[str, Any]], scores: Mapping[str, float], temperature: float,
           rng: Random) -> Mapping[str, Any]:
    """Draw one option, favouring higher scores.

    Args:
        candidates: Nonempty options to draw from.
        scores: Score per option ID.
        temperature: 0 picks the first best option; higher values spread the draw.
        rng: Seeded generator of the draw.

    Returns:
        The drawn option.
    """
    best = max(scores.values())
    if temperature == 0:
        return max(candidates, key=lambda action: scores[action["id"]])
    weights = [math.exp((scores[action["id"]] - best) / temperature) for action in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def drawable(candidates: Sequence[Mapping[str, Any]], scores: Mapping[str, float]) -> list[Mapping[str, Any]]:
    """Keep the options chance may pick: never a pointless exit, never a clearly worse option.

    Args:
        candidates: Nonempty scored options.
        scores: Score per option ID, 0–1.

    Returns:
        The options worth drawing from, in candidate order.
    """
    # Walking out is final, so chance alone must not decide it: it is drawn only when the
    # evaluator finds leaving at least moderately worthwhile (level 2 of the 0–4 rubric),
    # or when going home is all that is left, as after closing time (see `_FINAL`).
    eligible = [action for action in candidates if action["verb"] not in _FINAL or scores[action["id"]] >= 0.5]
    eligible = eligible or list(candidates)
    # People weigh only the options nearly as good as their best; chance picks among those,
    # never a clearly worse one (0.15 is just over half a rubric level).
    best = max(scores[action["id"]] for action in eligible)
    return [action for action in eligible if scores[action["id"]] >= best - 0.15]


def bounded(candidates: Sequence[Mapping[str, Any]], scores: Mapping[str, float],
            limit: int) -> list[Mapping[str, Any]]:
    """Keep the options worth putting to the evaluator, so one request never grows unbounded.

    Args:
        candidates: Options in offer order.
        scores: Local score per option ID, the ranking used to trim.
        limit: Most options one request may hold.

    Returns:
        The `limit` best options in offer order; among equal scores the earlier is kept.

    Raises:
        ValueError: The limit is below one.
    """
    if limit < 1:
        raise ValueError(f"A request needs a limit of at least one option, not {limit!r}")
    ranked = sorted(range(len(candidates)), key=lambda index: (-scores[candidates[index]["id"]], index))
    return [candidates[index] for index in sorted(ranked[:limit])]



def worth_asking(candidates: Sequence[Mapping[str, Any]], scores: Mapping[str, float],
                 floors: Mapping[str, float], kept: Collection[str] = ()) -> list[Mapping[str, Any]]:
    """Leave out the fixtures a guest's state gives no reason to weigh, so a request holds options that matter.

    Args:
        candidates: Options in offer order.
        scores: Local score per option ID.
        floors: Lowest local score at which an option of a verb is worth a slot, by verb.
        kept: IDs of options that stay whatever their score, such as keeping one's place in a line.

    Returns:
        The options at or above their verb's floor (every verb without one) and those in `kept`, in offer
        order. Never empty for a nonempty request: when every option is under its floor, all stay. Nor does it
        leave a guest with nothing but an exit: then the request is whole, so that staying is an option too.
    """
    worth = [item for item in candidates
             if item["id"] in kept or scores[item["id"]] >= floors.get(item["verb"], 0.0)]
    return list(candidates) if all(item["verb"] in _FINAL for item in worth) else worth


def read_lean(config: Mapping[str, Any]) -> bool:
    """Read whether requests to a model are made lean (see `worth_asking`) from the AI config.

    Args:
        config: AI config, with a `lean` entry or none.

    Returns:
        The setting; requests are plain (every option) when the config does not say.

    Raises:
        ValueError: The setting is not a bool.
    """
    lean = config.get("lean", False)
    if not isinstance(lean, bool):
        raise ValueError(f"The lean setting must be true or false, not {lean!r}")
    return lean


def read_switch(text: str | None, default: bool, name: str) -> bool:
    """Read an on/off setting from the environment.

    Args:
        text: The variable's value, or None or empty when it is not set.
        default: What an unset variable means.
        name: The variable's name, for the error.

    Returns:
        True for "true", False for "false", else the default when unset.

    Raises:
        ValueError: The value is anything else.
    """
    if not text:
        return default
    if text not in ("true", "false"):
        raise ValueError(f"{name} must be true or false, not {text!r}")
    return text == "true"
