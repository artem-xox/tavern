"""Measures of the bar in an evening, counted from the event log."""

from typing import Any

import pytest

from tavern.evening.metrics import bar_metrics


def event(kind: str, actor_id: str, message: str = "x") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": 1.0, "actor_id": actor_id, "type": kind, "message": message}


def counts(served: int = 0, opened: int = 0, lines: int = 0, news_told: int = 0) -> dict[str, int]:
    """The expected counts."""
    return {"served": served, "opened": opened, "lines": lines, "news_told": news_told}


@pytest.mark.parametrize("events, staff, expected", [
    pytest.param([], ["hob"], counts(), id="empty-log"),
    pytest.param([event("served", "hob"), event("served", "hob")], ["hob"], counts(served=2),
                 id="each-mug-poured-counts"),
    pytest.param([event("conversation_started", "hob"), event("conversation_started", "ada")], ["hob"],
                 counts(opened=1), id="only-the-barkeeps-own-scenes-are-his-openings"),
    pytest.param([event("turn", "hob"), event("turn", "ada"), event("turn", "hob")], ["hob"], counts(lines=2),
                 id="only-his-lines-count"),
    pytest.param([event("news_told", "hob"), event("news_told", "ada")], ["hob"], counts(news_told=1),
                 id="only-the-news-he-told"),
    pytest.param([event("turn", "hob"), event("turn", "pip")], ["hob", "pip"], counts(lines=2),
                 id="every-staff-member-counts"),
    pytest.param([event("turn", "hob")], [], counts(), id="no-staff-no-lines"),
    pytest.param([event("action_completed", "hob", "Hob completed pour_beer"), event("arrival", "ada")], ["hob"],
                 counts(), id="other-events-are-ignored"),
])
def test_the_bar_is_counted_from_the_log(events: list[dict[str, Any]], staff: list[str],
                                         expected: dict[str, int]) -> None:
    assert bar_metrics(events, staff) == expected
