"""How wide and how deep the evening's choices were: options asked, who chance could draw, dead slots, stages."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.mind.selection import drawable


class StageCounts(TypedDict):
    """One kind of decision stage: how many requests, the mean options in one, the mean size of the near-best set
    chance draws from (`selection.drawable`), and the share of requests where that set held a single option."""

    requests: int
    options: float
    near_best: float
    decided: float


class Depth(TypedDict):
    """The share of decisions (first stages) followed by a second stage, a family or a chair, and by a third (an aim)."""

    second: float | None
    third: float | None


class ChoiceCounts(TypedDict):
    """The evening's choices: `stages` per kind; `dead`, the share of first-stage options scored under `DEAD`;
    `depth`; and `repeats`, the share of a guest's actions that repeat the verb of their previous one.
    Shares are None when the evening held nothing to share over."""

    stages: dict[str, StageCounts]
    dead: float | None
    depth: Depth
    repeats: float | None


# An option scored under this is a dead slot: the near-best draw (`selection.drawable`, 0.15 below the best) only
# reaches it when nothing in the request scores above 0.3, so it rarely does anything but fill a request.
DEAD = 0.15
# Stage kinds that follow a first stage of the same decision (same guest, same moment).
_SECOND = ("family", "seats")
_THIRD = ("aims",)


def choice_counts(choices: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]]) -> ChoiceCounts:
    """Measure the width and depth of a finished evening's choices.

    Args:
        choices: Every decision stage asked for, each with `time`, `actor_id`, `kind` and the `scores` per option ID.
        events: The complete event log, whose `action_started` events read "<name> chose <verb>".

    Returns:
        Counts per stage kind in order of first appearance, the dead share, the depth and the repeats. Rounding is
        left to the presentation. A guest who never chose is a staff member whose routine is no choice, so their
        actions do not count as repeats.

    Raises:
        ValueError: A stage has no scores or no options, or an action event does not name its verb.
    """
    stages = {kind: _stage_counts([item for item in choices if item["kind"] == kind])
              for kind in dict.fromkeys(item["kind"] for item in choices)}
    firsts = [item for item in choices if item["kind"] == "actions"]
    return {"stages": stages, "dead": _dead(firsts), "depth": _depth(choices, firsts),
            "repeats": _repeats(events, {item["actor_id"] for item in choices})}


def _scores(stage: Mapping[str, Any]) -> Mapping[str, float]:
    scores = stage.get("scores")
    if not scores:
        raise ValueError(f"A {stage['kind']} stage of {stage['actor_id']} at {stage['time']} has no scored options")
    return scores


def _stage_counts(stages: Sequence[Mapping[str, Any]]) -> StageCounts:
    # An option's verb is its ID before the first colon: `leave:door` is a leave, and a family such as `pastime` its
    # own name, which `drawable` treats like any verb that is not an exit.
    near = [len(drawable([{"id": key, "verb": key.split(":")[0]} for key in _scores(item)], _scores(item)))
            for item in stages]
    return {"requests": len(stages), "options": sum(len(_scores(item)) for item in stages) / len(stages),
            "near_best": sum(near) / len(near), "decided": sum(count == 1 for count in near) / len(near)}


def _dead(firsts: Sequence[Mapping[str, Any]]) -> float | None:
    scores = [score for item in firsts for score in _scores(item).values()]
    return sum(score < DEAD for score in scores) / len(scores) if scores else None


def _depth(choices: Sequence[Mapping[str, Any]], firsts: Sequence[Mapping[str, Any]]) -> Depth:
    moments = Counter((item["actor_id"], item["time"], item["kind"]) for item in choices)

    def reached(kinds: Sequence[str]) -> float | None:
        return (sum(any(moments[(item["actor_id"], item["time"], kind)] for kind in kinds) for item in firsts)
                / len(firsts) if firsts else None)

    return {"second": reached(_SECOND), "third": reached(_THIRD)}


def _repeats(events: Sequence[Mapping[str, Any]], deciders: set[str]) -> float | None:
    verbs: dict[str, list[str]] = {}
    for event in events:
        if event["type"] != "action_started" or event["actor_id"] not in deciders:
            continue
        verb = event["message"].rpartition(" chose ")[2] if " chose " in event["message"] else ""
        if not verb:
            raise ValueError(f"An action event must say what was chosen: {event['message']!r}")
        verbs.setdefault(event["actor_id"], []).append(verb)
    pairs = [(before, after) for chosen in verbs.values() for before, after in zip(chosen, chosen[1:])]
    return sum(before == after for before, after in pairs) / len(pairs) if pairs else None
