"""Story score: which moments of an evening a player would retell, counted from its event log."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

# Weight of each moment: what a player retells most weighs most. A parameter of `story_score`, so a task
# that logs a new moment (a signature act, leaving in anger) adds one entry here and one rule below.
WEIGHTS: Mapping[str, float] = {"quarrel": 2.0, "fight": 4.0, "knockout": 3.0, "played_together": 1.0, "gift": 1.0,
                                "fell_asleep": 2.0, "limped_home": 2.0, "got_drunk": 1.0}

# Logged event types that are a moment by themselves.
# An insult is not one: every quarrel logs its own `quarrel` event beside it, so counting both would count twice.
_BY_TYPE = {"quarrel": "quarrel", "fight_started": "fight", "dice_won": "played_together",
            "gave": "gift", "dozed_off": "fell_asleep", "limped_home": "limped_home", "got_drunk": "got_drunk"}
# `fight_ended` carries no outcome field, only words (`aftermath._words`): these end the fights that knocked someone out.
_KNOCKOUT_WORDS = ("out cold", "knocked each other out")


class Moment(TypedDict):
    """One moment worth retelling: its kind (a key of the weights) and the logged event it came from."""

    moment: str
    event: Mapping[str, Any]


class StoryScore(TypedDict):
    """The moments of an evening counted per kind (every kind of the weights, zero included), and their weighted total."""

    moments: dict[str, int]
    score: float


def _kind_of(event: Mapping[str, Any]) -> str | None:
    if event["type"] == "fight_ended":
        return "knockout" if any(words in event["message"] for words in _KNOCKOUT_WORDS) else None
    return _BY_TYPE.get(event["type"])


def story_moments(events: Sequence[Mapping[str, Any]]) -> list[Moment]:
    """Pick the moments worth retelling out of an event log.

    Args:
        events: Event log in order. A quarrel, fight or gift logs one event per participant with the same time
            and words, so events with the same type, time and message count once; two different moments that
            share all three are indistinguishable in the log and also count once.

    Returns:
        The moments, in the log's order, each with its first event.

    Raises:
        KeyError: An event lacks `type`, `time` or `message`.
    """
    seen: set[tuple[str, float, str]] = set()
    moments: list[Moment] = []
    for event in events:
        kind = _kind_of(event)
        key = (event["type"], event["time"], event["message"])
        if kind is None or key in seen:
            continue
        seen.add(key)
        moments.append({"moment": kind, "event": event})
    return moments


def story_score(moments: Sequence[Moment], weights: Mapping[str, float]) -> StoryScore:
    """Count moments per kind and weigh them.

    Args:
        moments: Moments from `story_moments`.
        weights: Weight per kind of moment; it names every kind of `WEIGHTS`, or the call is refused.

    Returns:
        Counts per kind of `weights`, and the sum of count × weight, unrounded.

    Raises:
        ValueError: A kind of moment has no weight.
    """
    missing = sorted(set(WEIGHTS) - set(weights))
    if missing:
        raise ValueError(f"No weight for the moment kinds {missing}")
    counts = {kind: 0 for kind in weights}
    for item in moments:
        counts[item["moment"]] += 1
    return {"moments": counts, "score": sum(counts[kind] * weights[kind] for kind in weights)}
