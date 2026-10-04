"""Measures of the dice played in an evening, counted from the event log."""

from typing import Any

import pytest

from tavern.evening.metrics import dice_metrics


def event(kind: str, actor_id: str, message: str = "x") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": 1.0, "actor_id": actor_id, "type": kind, "message": message}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"games": 0, "abandoned": 0, "onlookers": 0, "wins": {}}, id="empty-log"),
    pytest.param([event("dice_won", "ada"), event("dice_lost", "bea")],
                 {"games": 1, "abandoned": 0, "onlookers": 0, "wins": {"ada": 1}}, id="one-game-counts-its-winner-once"),
    pytest.param([event("dice_won", "ada"), event("dice_won", "ada"), event("dice_won", "bea")],
                 {"games": 3, "abandoned": 0, "onlookers": 0, "wins": {"ada": 2, "bea": 1}}, id="winners-add-up"),
    pytest.param([event("dice_abandoned", "ada"), event("dice_abandoned", "bea")],
                 {"games": 0, "abandoned": 2, "onlookers": 0, "wins": {}}, id="broken-off-games-are-no-games"),
    pytest.param([event("dice_won", "ada"), event("dice_watched", "cid"), event("dice_watched", "dan")],
                 {"games": 1, "abandoned": 0, "onlookers": 2, "wins": {"ada": 1}}, id="each-onlooker-counts"),
    pytest.param([event("dice_started", "ada"), event("action_completed", "ada", "Ada completed play_dice")],
                 {"games": 0, "abandoned": 0, "onlookers": 0, "wins": {}}, id="other-events-are-ignored"),
])
def test_dice_are_counted_from_the_log(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert dice_metrics(events) == expected
