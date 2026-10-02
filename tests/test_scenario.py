"""A scenario describes the evening apart from the room: who comes, when, and closing time."""

from typing import Any

import pytest

from tavern.scenario import parse_scenario


def guest(guest_id: str, arrives_at: Any = 0, **fields: Any) -> dict[str, Any]:
    """Describe a guest the way a scenario file does."""
    return {"id": guest_id, "name": guest_id.title(), "color": "#c09060", "sprite": "visitor",
            "traits": {"patience": 0.5}, "arrives_at": arrives_at, **fields}


def scenario(guests: list[dict[str, Any]], closes_at: Any = 300, **fields: Any) -> dict[str, Any]:
    """Describe an evening with thirsty arrivals and the given guests."""
    return {"guests": guests, "arrival": {"needs": {"thirst": [50, 90]}}, "closes_at": closes_at, **fields}


@pytest.mark.parametrize("data, expected", [
    pytest.param(scenario([guest("ada")]), (["ada"], 300.0, None), id="single-guest"),
    pytest.param(scenario([guest("ada", 30), guest("bea", 30)]), (["ada", "bea"], 300.0, None),
                 id="duplicate-arrival-times"),
    pytest.param(scenario([guest("bea", 90), guest("ada", 0)]), (["bea", "ada"], 300.0, None),
                 id="file-order-kept"),
    pytest.param(scenario([guest("ada")], closes_at=600.5, seed=7), (["ada"], 600.5, 7), id="seeded-evening"),
])
def test_scenario_lists_guests_closing_time_and_seed(data: dict[str, Any],
                                                      expected: tuple[list[str], float, int | None]) -> None:
    parsed = parse_scenario(data)
    assert ([item["id"] for item in parsed.guests], parsed.closes_at, parsed.seed) == expected


def test_scenario_keeps_each_guests_look_and_arrival_time() -> None:
    parsed = parse_scenario(scenario([guest("ada", 45, sprite="edda", traits={"comfort": 0.9})]))
    assert parsed.guests[0] == {"id": "ada", "name": "Ada", "color": "#c09060", "sprite": "edda",
                                "traits": {"comfort": 0.9}, "arrives_at": 45.0}
    assert parsed.arrival == {"thirst": (50.0, 90.0)}


@pytest.mark.parametrize("data", [
    pytest.param([], id="malformed-scenario"),
    pytest.param(scenario([]), id="empty-guests"),
    pytest.param(scenario("ada"), id="malformed-guests"),
    pytest.param(scenario([guest("ada"), guest("ada", 60)]), id="duplicate-guest-ids"),
    pytest.param(scenario([{key: value for key, value in guest("ada").items() if key != "sprite"}]),
                 id="missing-sprite"),
    pytest.param(scenario([guest("ada", sprite="")]), id="empty-sprite"),
    pytest.param(scenario([guest("ada", name=None)]), id="malformed-name"),
    pytest.param(scenario([guest("ada", traits={"patience": 2})]), id="trait-out-of-range"),
    pytest.param(scenario([guest("ada", -5)]), id="negative-arrival-time"),
    pytest.param(scenario([guest("ada", "dusk")]), id="malformed-arrival-time"),
    pytest.param(scenario([guest("ada", 300)]), id="arrives-at-closing"),
    pytest.param(scenario([guest("ada", mood="grim")]), id="unknown-guest-field"),
    pytest.param(scenario([guest("ada")], closes_at="late"), id="malformed-closing-time"),
    pytest.param({key: value for key, value in scenario([guest("ada")]).items() if key != "closes_at"},
                 id="missing-closing-time"),
    pytest.param({key: value for key, value in scenario([guest("ada")]).items() if key != "arrival"},
                 id="missing-arrival-ranges"),
    pytest.param(scenario([guest("ada")], arrival={"needs": {"thirst": [90, 50]}}), id="reversed-arrival-range"),
    pytest.param(scenario([guest("ada")], seed=True), id="malformed-seed"),
    pytest.param(scenario([guest("ada")], news=["tolls"]), id="unknown-scenario-field"),
])
def test_malformed_scenario_fails_loudly(data: Any) -> None:
    with pytest.raises(ValueError):
        parse_scenario(data)
