"""Measures of the sleep in an evening, counted from the event log and from the guests who went home."""

from typing import Any

import pytest

from tavern.evening.metrics import sleep_metrics


def event(kind: str, actor_id: str) -> dict[str, Any]:
    """Build a logged event."""
    return {"time": 1.0, "actor_id": actor_id, "type": kind, "message": "x"}


def guest(actor_id: str, fatigue: float, left_at: float = 100.0) -> dict[str, Any]:
    """Build a guest who has gone home at a game time, as tired as given."""
    return {"id": actor_id, "needs": {"fatigue": fatigue}, "visit": {"left_at": left_at}}


NONE = {"naps": 0, "napped": {}, "slept_out": 0, "woken": 0, "fatigue_at_departure": {}, "tired_home": 0}


@pytest.mark.parametrize("events, departed, expected", [
    pytest.param([], [], NONE, id="empty-log"),
    pytest.param([event("dozed_off", "ada"), event("woke_up", "ada")], [],
                 {**NONE, "naps": 1, "napped": {"ada": 1}, "slept_out": 1}, id="one-nap-slept-out"),
    pytest.param([event("dozed_off", "ada"), event("woken", "ada")], [],
                 {**NONE, "naps": 1, "napped": {"ada": 1}, "woken": 1}, id="a-nap-cut-by-a-quarrel"),
    pytest.param([event("dozed_off", "ada"), event("woke_up", "ada"), event("dozed_off", "ada"),
                  event("dozed_off", "bea")], [],
                 {**NONE, "naps": 3, "napped": {"ada": 2, "bea": 1}, "slept_out": 1}, id="one-guest-naps-twice"),
    pytest.param([event("arrival", "ada"), event("action_completed", "ada")], [], NONE, id="other-events-are-ignored"),
    pytest.param([], [guest("ada", 59.9), guest("bea", 60.0), guest("cid", 100.0)],
                 {**NONE, "fatigue_at_departure": {"ada": 59.9, "bea": 60.0, "cid": 100.0}, "tired_home": 2},
                 id="tired-from-sixty"),
])
def test_sleep_is_counted_from_the_log_and_the_departed(events: list[dict[str, Any]],
                                                        departed: list[dict[str, Any]],
                                                        expected: dict[str, Any]) -> None:
    assert sleep_metrics(events, departed, closes_at=None) == expected


@pytest.mark.parametrize("closes_at, tired_home", [
    pytest.param(None, 2, id="no-closing-time-every-tired-guest-chose-to-go"),
    pytest.param(200.0, 2, id="both-left-before-closing"),
    pytest.param(100.0, 1, id="leaving-at-closing-is-no-choice"),
    pytest.param(50.0, 0, id="all-left-after-closing"),
])
def test_only_a_tired_guest_who_went_before_closing_chose_to_go_home_tired(closes_at: float | None,
                                                                          tired_home: int) -> None:
    departed = [guest("ada", 80.0, left_at=90.0), guest("bea", 70.0, left_at=100.0 if closes_at != 200.0 else 150.0),
                guest("cid", 20.0, left_at=10.0)]
    assert sleep_metrics([], departed, closes_at=closes_at)["tired_home"] == tired_home
