"""Story score: the moments of an evening worth retelling, counted from its event log."""

from typing import Any

import pytest

from tavern.evening.story_score import WEIGHTS, story_moments, story_score


def event(kind: str, message: str = "Ada did a thing", time: float = 1.0, actor_id: str = "ada") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


def ended(outcome: str, message: str) -> dict[str, Any]:
    """Build the logged end of a fight, with the outcome it carries."""
    return {**event("fight_ended", message), "outcome": outcome}


def counts(**given: int) -> dict[str, int]:
    """Moment counts with every kind of the table present, zero unless given."""
    return {kind: given.get(kind, 0) for kind in WEIGHTS}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], counts(), id="empty-log"),
    pytest.param([event("quarrel")], counts(quarrel=1), id="quarrel"),
    pytest.param([event("insulted"), event("quarrel", "Ada and Bram quarreled")], counts(quarrel=1),
                 id="insult-and-the-quarrel-it-starts-count-once"),
    pytest.param([event("fight_started")], counts(fight=1), id="fight"),
    pytest.param([ended("knockout", "Bram knocked Ada out cold")], counts(knockout=1), id="knockout-counts-extra"),
    pytest.param([ended("double_knockout", "Ada and Bram knocked each other out")], counts(knockout=1),
                 id="double-knockout-is-one-moment"),
    pytest.param([ended("knockout", "Bram won the fight")], counts(knockout=1), id="knockout-is-read-from-the-outcome"),
    pytest.param([ended("yielded", "Bram talked of knocking Ada out cold")], counts(),
                 id="words-alone-are-no-knockout"),
    pytest.param([ended("yielded", "Ada gave up and backed away from Bram")], counts(),
                 id="fight-ended-without-knockout-adds-nothing"),
    pytest.param([event("dice_won")], counts(played_together=1), id="dice-game"),
    pytest.param([event("gave", "Ada gave Bram a beer")], counts(gift=1), id="gift"),
    pytest.param([event("dozed_off")], counts(fell_asleep=1), id="fell-asleep"),
    pytest.param([event("limped_home")], counts(limped_home=1), id="battered-and-gone"),
    pytest.param([event("got_drunk")], counts(got_drunk=1), id="got-drunk"),
    pytest.param([event("got_drunk", actor_id="ada"), event("got_drunk", actor_id="bram", time=5.0)],
                 counts(got_drunk=2), id="two-guests-who-got-drunk"),
    pytest.param([event("quarrel", "Ada quarreled with Bram", actor_id="ada"),
                  event("quarrel", "Ada quarreled with Bram", actor_id="bram")], counts(quarrel=1),
                 id="one-event-per-participant-is-one-moment"),
    pytest.param([event("quarrel", time=1.0), event("quarrel", time=9.0)], counts(quarrel=2),
                 id="same-words-at-another-time-is-another-moment"),
    pytest.param([event("action_completed"), event("turn"), event("arrival")], counts(),
                 id="unknown-kinds-ignored-because-only-the-table-is-story"),
])
def test_moments_are_counted_per_kind(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert story_score(story_moments(events), WEIGHTS)["moments"] == expected


@pytest.mark.parametrize("moments_given, weights, expected", [
    pytest.param([], WEIGHTS, 0.0, id="no-moments-no-score"),
    pytest.param([event("quarrel")], {**WEIGHTS, "quarrel": 2.5}, 2.5, id="weight-is-a-parameter"),
    pytest.param([event("quarrel"), event("quarrel", time=2.0)], {**WEIGHTS, "quarrel": 2.5}, 5.0,
                 id="weights-add-up"),
])
def test_score_is_the_weighted_total(moments_given: list[dict[str, Any]], weights: dict[str, float],
                                     expected: float) -> None:
    assert story_score(story_moments(moments_given), weights)["score"] == expected


def test_moments_keep_the_event_they_came_from() -> None:
    quarrel = event("quarrel", "Ada quarreled with Bram")
    assert story_moments([event("turn"), quarrel]) == [{"moment": "quarrel", "event": quarrel}]


def test_a_weight_missing_for_a_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="gift"):
        story_score([], {kind: 1.0 for kind in WEIGHTS if kind != "gift"})


def test_getting_drunk_is_a_small_moment_beside_a_quarrel() -> None:
    assert 0 < WEIGHTS["got_drunk"] < WEIGHTS["quarrel"]
