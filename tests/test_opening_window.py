"""Guests due at opening come in one by one, in a random order, from the first to the last second of the opening window."""

from typing import Any

import pytest

from tavern.evening.scenario import open_evening, parse_scenario

NAMES = ("ada", "bea", "cid", "dan", "eli", "fay")


def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a door in the bottom wall."""
    return {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
    ]}


def plan(arrivals: tuple[float, ...], **fields: Any) -> dict[str, Any]:
    """Describe one guest per arrival time, named ada, bea, cid… in order, before closing at 300 s."""
    guests = [{"id": name, "name": name.title(), "color": "#a08060", "sprite": "visitor", "traits": {},
               "arrives_at": time} for name, time in zip(NAMES, arrivals)]
    return {"guests": guests, "arrival": {"needs": {"thirst": [40, 80]}}, "closes_at": 300, **fields}


def schedule(data: dict[str, Any], seed: int) -> list[tuple[str, float]]:
    """Open the evening and list who is expected, with the second they come in."""
    world = open_evening(hall(), parse_scenario(data), seed)
    return [(item["id"], item["arrives_at"]) for item in world["expected"]]


def test_opening_guests_fill_the_window_evenly_in_a_seeded_random_order() -> None:
    data = plan((0, 0, 0, 0, 0, 0), opening_window=[1, 30])
    orders = {tuple(guest for guest, _ in schedule(data, seed)) for seed in range(8)}
    times = [time for _, time in schedule(data, 1)]
    assert (len(orders) > 1, times, schedule(data, 1) == schedule(data, 1)) == (True, [1, 6.8, 12.6, 18.4, 24.2, 30], True)


def test_a_lone_opening_guest_comes_in_at_the_start_of_the_window() -> None:
    assert schedule(plan((0,), opening_window=[1, 30]), 1) == [("ada", 1)]


def test_guests_due_later_keep_their_time() -> None:
    data = plan((0, 0, 90), opening_window=[1, 30])
    assert dict(schedule(data, 3))["cid"] == 90


def test_without_a_window_opening_guests_walk_in_at_once_in_listed_order() -> None:
    world = open_evening(hall(), parse_scenario(plan((0, 0))), 1)
    assert [item["id"] for item in world["actors"]] == ["ada"] and world["expected"][0]["id"] == "bea"


@pytest.mark.parametrize("window", [
    pytest.param([-1, 30], id="negative"),
    pytest.param("a minute", id="malformed"),
    pytest.param(30, id="not-a-pair"),
    pytest.param([30, 1], id="reversed"),
    pytest.param([1, 300], id="not-before-closing"),
])
def test_window_must_end_before_closing(window: Any) -> None:
    with pytest.raises(ValueError):
        parse_scenario(plan((0,), opening_window=window))
