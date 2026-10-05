"""Giving in the evening metrics: gifts by kind, refusals, and drink errands begun, done and failed."""

from typing import Any

import pytest

from tavern.evening.giving_metrics import giving_counts


def event(kind: str, message: str = "x", actor_id: str = "ada", time: float = 1.0, **data: Any) -> dict[str, Any]:
    """A logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message, **data}


def gift(message: str, time: float = 1.0) -> list[dict[str, Any]]:
    """A gift as the log holds it: one event for the giver and one for the receiver."""
    return [event("gave", message, "ada", time), event("gave", message, "bea", time)]


def nothing(**counts: Any) -> dict[str, Any]:
    """The counts of an evening without any giving, with some fields changed."""
    base = {"gifts": {"beer": 0, "remedy": 0, "keepsake": 0}, "refused": 0,
            "errands": {"begun": 0, "done": 0, "failed": 0}, "goals": {"set": 0, "done": 0, "failed": 0, "expired": 0}}
    return {**base, **counts}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], nothing(), id="empty"),
    pytest.param(gift("Ada gave Bea a mug of ale"), nothing(gifts={"beer": 1, "remedy": 0, "keepsake": 0}),
                 id="one-gift-is-logged-twice-and-counted-once"),
    pytest.param(gift("Ada gave Bea a herbal remedy"), nothing(gifts={"beer": 0, "remedy": 1, "keepsake": 0}),
                 id="a-remedy"),
    pytest.param(gift("Toren gave Rurik a keepsake"), nothing(gifts={"beer": 0, "remedy": 0, "keepsake": 1}),
                 id="a-keepsake"),
    pytest.param([*gift("Ada gave Bea a mug of ale", 1.0), *gift("Ada gave Bea a mug of ale", 200.0)],
                 nothing(gifts={"beer": 2, "remedy": 0, "keepsake": 0}), id="the-same-gift-twice-at-different-times"),
    pytest.param([*gift("Ada gave Bea a herbal remedy"), *gift("Bea gave Ada a keepsake")],
                 nothing(gifts={"beer": 0, "remedy": 1, "keepsake": 1}), id="two-gifts-at-the-same-moment"),
    pytest.param([event("gift_refused", "Bea would not take a keepsake from Ada", "ada"),
                  event("gift_refused", "Bea would not take a keepsake from Ada", "bea")], nothing(refused=1),
                 id="a-refusal-is-logged-twice-and-counted-once"),
    pytest.param([event("fetch_begun"), event("fetch_begun"), event("fetch_done"), event("fetch_failed")],
                 nothing(errands={"begun": 2, "done": 1, "failed": 1}), id="errands"),
    pytest.param([event("goal_set", goal="bring_drink"), event("goal_set", goal="talk_to"),
                  event("goal_done", goal="bring_drink"), event("goal_expired", goal="bring_drink"),
                  event("goal_failed", goal="bring_drink"), event("goal_done")],
                 nothing(goals={"set": 1, "done": 1, "failed": 1, "expired": 1}), id="goals-of-bringing-a-drink"),
    pytest.param([event("turn"), *gift("Ada gave Bea a mug of ale"), event("quarrel")],
                 nothing(gifts={"beer": 1, "remedy": 0, "keepsake": 0}), id="mixed-with-other-events"),
])
def test_giving_is_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert giving_counts(events) == expected


@pytest.mark.parametrize("events, error", [
    pytest.param([{"time": 1.0, "message": "no type"}], KeyError, id="event-without-a-type"),
    pytest.param([event("gave", "Ada gave Bea a sword")], ValueError, id="a-gift-of-an-unknown-kind"),
    pytest.param([{"time": 1.0, "type": "gave"}], KeyError, id="gift-without-words"),
])
def test_a_malformed_event_fails_loudly(events: list[dict[str, Any]], error: type[Exception]) -> None:
    with pytest.raises(error):
        giving_counts(events)
