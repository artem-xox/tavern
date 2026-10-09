"""Aims in the evening metrics: what guests came to talk for, and how often they got round to it."""

from typing import Any

import pytest

from tavern.evening.aim_metrics import aim_counts


def event(kind: str, aim: str, actor_id: str = "ada") -> dict[str, Any]:
    """A logged `aim_set` or `aim_kept` event."""
    words = "means to pass the time with Bea" if kind == "aim_set" else "got round to it: pass the time with Bea"
    return {"time": 1.0, "actor_id": actor_id, "type": kind, "message": f"Ada {words} ({aim})"}


NONE: dict[str, Any] = {"set": 0, "kept": 0, "by_kind": {}}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], NONE, id="empty"),
    pytest.param([event("aim_set", "pass_time")], {"set": 1, "kept": 0, "by_kind": {"pass_time": {"set": 1, "kept": 0}}},
                 id="one-aim-set-and-not-kept"),
    pytest.param([event("aim_set", "pass_time"), event("aim_kept", "pass_time")],
                 {"set": 1, "kept": 1, "by_kind": {"pass_time": {"set": 1, "kept": 1}}}, id="set-and-kept"),
    pytest.param([event("aim_set", "tell_news:fever"), event("aim_set", "tell_news:robbery"),
                  event("aim_kept", "tell_news:robbery")],
                 {"set": 2, "kept": 1, "by_kind": {"tell_news": {"set": 2, "kept": 1}}},
                 id="the-detail-is-not-a-kind"),
    pytest.param([event("aim_set", "win_over"), event("aim_set", "pass_time", "bea")],
                 {"set": 2, "kept": 0, "by_kind": {"pass_time": {"set": 1, "kept": 0}, "win_over": {"set": 1, "kept": 0}}},
                 id="kinds-in-table-order"),
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "talk", "message": "x"}], NONE, id="other-events-ignored"),
])
def test_aims_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert aim_counts(events) == expected


@pytest.mark.parametrize("message", [
    pytest.param("Ada means to pass the time", id="no-aim-in-the-message"),
    pytest.param("Ada means to do something (nothing)", id="an-unknown-kind"),
])
def test_an_aim_event_that_cannot_be_read_fails_loudly(message: str) -> None:
    with pytest.raises(ValueError):
        aim_counts([{"time": 1.0, "actor_id": "ada", "type": "aim_set", "message": message}])
