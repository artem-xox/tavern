"""How a decision is drawn from scored options: the temperature and the near-best draw."""

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
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


def drawable(candidates: Sequence[Mapping[str, Any]], scores: Mapping[str, float],
             window: float = 0.15) -> list[Mapping[str, Any]]:
    """Keep the options chance may pick: never a pointless exit, never a clearly worse option.

    Args:
        candidates: Nonempty scored options.
        scores: Score per option ID, 0–1.
        window: How far below the best an option may score and still be drawn (see `spread`).

    Returns:
        The options worth drawing from, in candidate order.
    """
    # Walking out is final, so chance alone must not decide it: it is drawn only when the
    # evaluator finds leaving at least moderately worthwhile (level 2 of the 0–4 rubric),
    # or when going home is all that is left, as after closing time (see `_FINAL`).
    eligible = [action for action in candidates if action["verb"] not in _FINAL or scores[action["id"]] >= 0.5]
    eligible = eligible or list(candidates)
    # People weigh only the options nearly as good as their best; chance picks among those,
    # never a clearly worse one (0.15 is just over half a rubric level, the window of an ordinary guest).
    best = max(scores[action["id"]] for action in eligible)
    return [action for action in eligible if scores[action["id"]] >= best - window]


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


def _flag(config: Mapping[str, Any], name: str) -> bool:
    value = config.get(name, False)
    if not isinstance(value, bool):
        raise ValueError(f"The {name} setting must be true or false, not {value!r}")
    return value


def read_lean(config: Mapping[str, Any]) -> bool:
    """Read whether requests to a model are made lean (see `worth_asking`) from the AI config.

    Args:
        config: AI config, with a `lean` entry or none.

    Returns:
        The setting; requests are plain (every option) when the config does not say.

    Raises:
        ValueError: The setting is not a bool.
    """
    return _flag(config, "lean")


def read_aims(config: Mapping[str, Any]) -> bool:
    """Read whether a social option is followed by a choice of aim (see `tavern.social.aims`) from the AI config.

    Args:
        config: AI config, with an `aims` entry or none.

    Returns:
        The setting; no aim is chosen when the config does not say.

    Raises:
        ValueError: The setting is not a bool.
    """
    return _flag(config, "aims")


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


@dataclass(frozen=True)
class Spread:
    """How a guest's draw spreads: the `window` below the best score that chance still reaches (see `drawable`) and the
    softmax `temperature` (see `select`)."""

    window: float
    temperature: float


# How far a guest's temper (against their patience) and drink widen or narrow the draw. The factor is 1 for an ordinary
# sober guest, so the config's window and temperature stand for them; each term is a guess to tune on evenings.
TEMPER_PULL = 0.6
DRINK_PULL = 0.8
# The window of the near-best draw stays between these, and the temperature between these multiples of the config's,
# so that a cool head never reaches for nothing and a hot one never draws blindly.
WINDOW_BAND = (0.08, 0.3)
TEMPERATURE_BAND = (0.5, 2.0)


def spread(actor: Mapping[str, Any], temperature: float) -> Spread:
    """Tell how widely a guest's draw ranges: wider for the hot-tempered and the drunk, narrower for the patient.

    Args:
        actor: The guest, with `traits` (`temper` and `patience`, 0-1, each 0.5 when missing as for a Stage 0 visitor)
            and `drunkenness` (0-1, 0 when missing).
        temperature: The config's selection temperature.

    Returns:
        The window and temperature of their draw: the usual 0.15 and the config's temperature, times
        `1 + TEMPER_PULL * (temper - patience) + DRINK_PULL * drunkenness`, kept within `WINDOW_BAND` and
        `TEMPERATURE_BAND`. A temperature of 0 stays 0: the best option is taken whoever chooses.

    Raises:
        ValueError: A trait or drunkenness is outside 0-1, or the temperature is negative or not finite.
    """
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError(f"Temperature must be a nonnegative finite number, not {temperature!r}")
    traits = actor.get("traits", {})
    temper, patience, drunk = traits.get("temper", 0.5), traits.get("patience", 0.5), actor.get("drunkenness", 0.0)
    for name, value in (("temper", temper), ("patience", patience), ("drunkenness", drunk)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"A guest's {name} must be from 0 to 1, not {value!r}")
    factor = 1 + TEMPER_PULL * (temper - patience) + DRINK_PULL * drunk
    low, high = TEMPERATURE_BAND
    return Spread(min(WINDOW_BAND[1], max(WINDOW_BAND[0], 0.15 * factor)),
                  min(high * temperature, max(low * temperature, temperature * factor)))
