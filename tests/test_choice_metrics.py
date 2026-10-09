"""Choice metrics: how wide and how deep the evening's decisions were."""

from typing import Any

import pytest

from tavern.evening.choice_metrics import choice_counts


def stage(scores: dict[str, float], kind: str = "actions", actor_id: str = "ada", time: float = 1.0) -> dict[str, Any]:
    """A logged decision stage, as the lockstep records it."""
    return {"time": time, "actor_id": actor_id, "kind": kind, "source": "jev", "error": None, "scores": scores}


def started(verb: str, actor_id: str = "ada", time: float = 1.0) -> dict[str, Any]:
    """The event of an action begun."""
    return {"time": time, "actor_id": actor_id, "type": "action_started", "message": f"{actor_id.title()} chose {verb}"}


def counts(**fields: Any) -> dict[str, Any]:
    """The counts of an evening without any choice, with some fields changed."""
    base = {"stages": {}, "dead": None, "depth": {"second": None, "third": None}, "repeats": None}
    return {**base, **fields}


def seen(requests: int, options: float, near_best: float, decided: float) -> dict[str, Any]:
    """The counts of one stage kind."""
    return {"requests": requests, "options": options, "near_best": near_best, "decided": decided}


@pytest.mark.parametrize("choices, events, expected", [
    pytest.param([], [], counts(), id="empty-evening-has-no-means"),
    pytest.param([stage({"sit:s1": 0.9, "wait": 0.1})], [],
                 counts(stages={"actions": seen(1, 2, 1, 1.0)}, dead=0.5, depth={"second": 0.0, "third": 0.0}),
                 id="single-request-with-a-clear-best"),
    pytest.param([stage({"sit:s1": 0.9, "talk:bea": 0.8, "wait": 0.1})], [],
                 counts(stages={"actions": seen(1, 3, 2, 0.0)}, dead=pytest.approx(1 / 3), depth={"second": 0.0, "third": 0.0}),
                 id="a-close-second-is-in-the-near-best-set"),
    pytest.param([stage({"sit:s1": 0.5, "talk:bea": 0.5})], [],
                 counts(stages={"actions": seen(1, 2, 2, 0.0)}, dead=0.0, depth={"second": 0.0, "third": 0.0}),
                 id="tie-at-the-top"),
    pytest.param([stage({"leave:door": 0.4, "sit:s1": 0.3})], [],
                 counts(stages={"actions": seen(1, 2, 1, 1.0)}, dead=0.0, depth={"second": 0.0, "third": 0.0}),
                 id="a-pointless-exit-is-not-drawn"),
    pytest.param([stage({"inspect": 0.05, "wait": 0.1, "sit:s1": 0.9, "use_toilet:wc": 0.0})], [],
                 counts(stages={"actions": seen(1, 4, 1, 1.0)}, dead=0.75, depth={"second": 0.0, "third": 0.0}),
                 id="options-scored-under-0.15-are-dead"),
    pytest.param([stage({"pastime": 0.9, "wait": 0.2}), stage({"play_darts:darts": 0.7, "watch:fire": 0.3}, "family")],
                 [],
                 counts(stages={"actions": seen(1, 2, 1, 1.0), "family": seen(1, 2, 1, 1.0)}, dead=0.0,
                        depth={"second": 1.0, "third": 0.0}),
                 id="a-family-stage-after-an-action-stage"),
    pytest.param([stage({"pastime": 0.9, "wait": 0.2}), stage({"sit:s1": 0.7, "sit:s2": 0.3}, "seats"),
                  stage({"wait": 0.9, "inspect": 0.2}, time=5.0)], [],
                 counts(stages={"actions": seen(2, 2, 1, 1.0), "seats": seen(1, 2, 1, 1.0)}, dead=0.0,
                        depth={"second": 0.5, "third": 0.0}),
                 id="a-second-stage-belongs-to-the-decision-of-its-moment"),
    pytest.param([stage({"talk:bea": 0.9, "wait": 0.2}), stage({"pass_time@talk:bea": 0.7, "needle@talk:bea": 0.1},
                                                               "aims")], [],
                 counts(stages={"actions": seen(1, 2, 1, 1.0), "aims": seen(1, 2, 1, 1.0)}, dead=0.0,
                        depth={"second": 0.0, "third": 1.0}),
                 id="a-third-stage"),
    pytest.param([stage({"sit:s1": 0.9}, actor_id="ada"), stage({"sit:s1": 0.9}, actor_id="bea")],
                 [started("sit", "ada", 1.0), started("sit", "ada", 15.0), started("sit", "bea", 1.0)],
                 counts(stages={"actions": seen(2, 1, 1, 1.0)}, dead=0.0, depth={"second": 0.0, "third": 0.0},
                        repeats=1.0),
                 id="a-repeat-is-counted-per-guest-and-only-between-their-own-actions"),
    pytest.param([stage({"sit:s1": 0.9})],
                 [started("sit", time=1.0), started("drink", time=2.0), started("sit", time=3.0),
                  started("sit", time=4.0)],
                 counts(stages={"actions": seen(1, 1, 1, 1.0)}, dead=0.0, depth={"second": 0.0, "third": 0.0},
                        repeats=pytest.approx(1 / 3)),
                 id="duplicate-consecutive-verbs"),
    pytest.param([stage({"sit:s1": 0.9})], [started("sit", "hob", 1.0), started("sit", "hob", 2.0)],
                 counts(stages={"actions": seen(1, 1, 1, 1.0)}, dead=0.0, depth={"second": 0.0, "third": 0.0}),
                 id="staff-who-decide-nothing-are-left-out-of-repeats"),
])
def test_choices_are_counted(choices: list[dict[str, Any]], events: list[dict[str, Any]],
                             expected: dict[str, Any]) -> None:
    assert choice_counts(choices, events) == expected


@pytest.mark.parametrize("choices, events", [
    pytest.param([{"time": 1.0, "actor_id": "ada", "kind": "actions", "source": "jev", "error": None}], [],
                 id="stage-without-scores"),
    pytest.param([stage({})], [], id="stage-without-options"),
    pytest.param([stage({"sit:s1": 0.9})],
                 [{"time": 1.0, "actor_id": "ada", "type": "action_started", "message": "Ada sat down"}],
                 id="action-event-without-a-verb"),
])
def test_malformed_choice_input_fails_loudly(choices: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    with pytest.raises(ValueError):
        choice_counts(choices, events)
