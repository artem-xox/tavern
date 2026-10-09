"""Answers in the evening metrics: how many, to what, and how long after."""

from typing import Any

import pytest

from tavern.evening.response_metrics import response_counts


def answered(message: str, actor_id: str = "ada") -> dict[str, Any]:
    """A logged answer."""
    return {"time": 1.0, "actor_id": actor_id, "type": "answered", "message": message}


DICE = "Ada went to answer Bea, who beat them at dice (30 s later)"
SEAT = "Cid went to answer Dan, who took their seat (10 s later)"


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"answered": 0, "by_kind": {}, "mean_delay": None}, id="empty"),
    pytest.param([answered(DICE)], {"answered": 1, "by_kind": {"lost_at_dice": 1}, "mean_delay": 30.0},
                 id="single-answer"),
    pytest.param([answered(DICE), answered(DICE)], {"answered": 2, "by_kind": {"lost_at_dice": 2}, "mean_delay": 30.0},
                 id="duplicate-answers"),
    pytest.param([answered(DICE), answered(SEAT, "cid")],
                 {"answered": 2, "by_kind": {"seat_taken": 1, "lost_at_dice": 1}, "mean_delay": 20.0},
                 id="two-kinds-in-table-order"),
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "talk", "message": "x"}, answered(DICE)],
                 {"answered": 1, "by_kind": {"lost_at_dice": 1}, "mean_delay": 30.0}, id="other-events-ignored"),
])
def test_answers_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert response_counts(events) == expected


@pytest.mark.parametrize("message", [
    pytest.param("Ada answered Bea", id="not-in-the-logged-form"),
    pytest.param("Ada went to answer Bea, who did something odd (3 s later)", id="an-unknown-reason"),
])
def test_an_answer_that_cannot_be_read_fails_loudly(message: str) -> None:
    with pytest.raises(ValueError):
        response_counts([answered(message)])
