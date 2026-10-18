"""Drink in the evening metrics: who got drunk, who got wasted, and how many beers each guest had."""

from typing import Any

import pytest

from tavern.evening.drink_metrics import drink_counts


def event(kind: str, who: str = "ada") -> dict[str, Any]:
    """A logged event."""
    return {"time": 1.0, "actor_id": who, "type": kind, "message": f"{who}: {kind}"}


def guest(who: str, beers: int) -> dict[str, Any]:
    """A guest and the beers they drank."""
    return {"id": who, "visit": {"beers": beers}}


@pytest.mark.parametrize("events, guests, expected", [
    pytest.param([], [], {"drunk": [], "wasted": [], "beers": {}}, id="empty"),
    pytest.param([event("got_drunk")], [guest("ada", 3)], {"drunk": ["ada"], "wasted": [], "beers": {"ada": 3}},
                 id="single"),
    pytest.param([event("got_drunk"), event("got_drunk"), event("got_wasted")], [guest("ada", 5)],
                 {"drunk": ["ada"], "wasted": ["ada"], "beers": {"ada": 5}}, id="duplicates-count-a-guest-once"),
    pytest.param([event("got_drunk", "bea"), event("turn"), event("got_drunk", "ada")],
                 [guest("ada", 3), guest("bea", 4), guest("cy", 0)],
                 {"drunk": ["bea", "ada"], "wasted": [], "beers": {"ada": 3, "bea": 4, "cy": 0}},
                 id="two-guests-in-order-with-other-events"),
])
def test_drink_is_counted(events: list[dict[str, Any]], guests: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert drink_counts(events, guests) == expected


def test_malformed_event_fails_loudly() -> None:
    with pytest.raises(KeyError):
        drink_counts([{"time": 1.0, "message": "no type"}], [])
