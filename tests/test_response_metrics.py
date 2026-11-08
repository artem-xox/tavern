"""Answers in the evening metrics: how many, to what, and how long after."""

from typing import Any

import pytest

from tavern.evening.response_metrics import response_counts


def answered(message: str, response: str, after: float, actor_id: str = "ada") -> dict[str, Any]:
    """A logged answer, with the kind of thought and the seconds since it."""
    return {"time": 1.0, "actor_id": actor_id, "type": "answered", "message": message, "response": response, "after": after}


DICE = answered("Ada went to answer Bea, who beat them at dice (30 s later)", "lost_at_dice", 30.0)
SEAT = answered("Cid went to answer Dan, who took their seat (10 s later)", "seat_taken", 10.0, "cid")


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"answered": 0, "by_kind": {}, "mean_delay": None}, id="empty"),
    pytest.param([DICE], {"answered": 1, "by_kind": {"lost_at_dice": 1}, "mean_delay": 30.0},
                 id="single-answer"),
    pytest.param([DICE, DICE], {"answered": 2, "by_kind": {"lost_at_dice": 2}, "mean_delay": 30.0},
                 id="duplicate-answers"),
    pytest.param([DICE, SEAT],
                 {"answered": 2, "by_kind": {"seat_taken": 1, "lost_at_dice": 1}, "mean_delay": 20.0},
                 id="two-kinds-in-table-order"),
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "talk", "message": "x"}, DICE],
                 {"answered": 1, "by_kind": {"lost_at_dice": 1}, "mean_delay": 30.0}, id="other-events-ignored"),
])
def test_answers_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert response_counts(events) == expected


def test_the_mean_delay_is_taken_over_whole_seconds_as_the_message_shows_them() -> None:
    assert response_counts([{**DICE, "after": 29.6}, {**DICE, "after": 10.4}])["mean_delay"] == 20.0


@pytest.mark.parametrize("fields", [
    pytest.param({"response": None}, id="no-response"),
    pytest.param({"response": "did_something_odd"}, id="an-unknown-response"),
])
def test_an_answer_with_no_known_response_fails_loudly(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        response_counts([{**DICE, **fields}])


def test_an_answer_without_its_delay_fails_loudly() -> None:
    with pytest.raises(ValueError):
        response_counts([{key: value for key, value in DICE.items() if key != "after"}])
