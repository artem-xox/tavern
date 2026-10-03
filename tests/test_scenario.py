"""A scenario describes the evening apart from the room: who comes, when, and closing time."""

from typing import Any

import pytest

from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import start_action, step_world


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


def hall(door_spots: list[list[int]] | None = None) -> dict[str, Any]:
    """Build a 10×7 hall: a door in the bottom wall, a tap far from it, and a two-seat table."""
    def chair(side: str, x: int) -> dict[str, Any]:
        return {"id": f"chair-{side}", "kind": "chair", "name": f"Chair {side}", "x": x, "y": 2,
                "walkable": True, "table_id": "table", "interaction_spots": [[x, 2]]}
    return {"width": 10, "height": 7, "blocked": [[x, 6] for x in range(10) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 6, "interaction_spots": door_spots or [[5, 5]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5},
        {"id": "table", "kind": "table", "name": "Table", "x": 5, "y": 2}, chair("west", 4), chair("east", 6),
    ]}


def evening(guests: list[dict[str, Any]], room: dict[str, Any] | None = None, seed: int = 0) -> dict[str, Any]:
    """Open the hall for an evening with the given guests."""
    return open_evening(room or hall(), parse_scenario(scenario(guests)), seed)


def advance(world: dict[str, Any], seconds: float, step: float = 0.5) -> list[int]:
    """Step the world without decisions; return how many visitors share a cell after each tick."""
    overlaps = []
    for _ in range(round(seconds / step)):
        step_world(world, step)
        cells = [(item["x"], item["y"]) for item in world["actors"]]
        overlaps.append(len(cells) - len(set(cells)))
    return overlaps


def present(world: dict[str, Any]) -> list[str]:
    """List the IDs of visitors inside the inn."""
    return [item["id"] for item in world["actors"]]


@pytest.mark.parametrize("guests, door_spots, expected", [
    pytest.param([guest("ada")], None, (["ada"], []), id="single-guest-at-opening"),
    pytest.param([guest("ada", 30)], None, ([], ["ada"]), id="single-guest-later"),
    pytest.param([guest("ada"), guest("bea")], None, (["ada"], ["bea"]), id="duplicate-time-one-door-spot"),
    pytest.param([guest("ada"), guest("bea")], [[5, 5], [4, 5]], (["ada", "bea"], []),
                 id="duplicate-time-two-door-spots"),
    pytest.param([guest("ada", 30), guest("bea")], None, (["bea"], ["ada"]), id="listed-out-of-order"),
])
def test_guests_due_at_opening_come_in_and_the_rest_are_expected(
        guests: list[dict[str, Any]], door_spots: list[list[int]] | None,
        expected: tuple[list[str], list[str]]) -> None:
    world = evening(guests, hall(door_spots))
    assert (present(world), [item["id"] for item in world["expected"]]) == expected


def test_newcomer_steps_in_at_the_door_and_takes_in_the_hall() -> None:
    world = evening([guest("ada", sprite="edda")])
    ada = world["actors"][0]
    assert ((ada["x"], ada["y"]), ada["sprite"], "tap" in ada["knowledge"]["objects"],
            50 <= ada["needs"]["thirst"] <= 90) == ((5, 5), "edda", True, True)
    assert [(event["type"], event["message"]) for event in world["events"]] == [("arrival", "Ada came in")]


@pytest.mark.parametrize("seconds, expected", [
    pytest.param(29.5, [], id="still-on-the-road"),
    pytest.param(30.0, ["ada"], id="arrives-on-time"),
    pytest.param(45.0, ["ada"], id="stays-after-arriving"),
])
def test_expected_guest_comes_in_at_their_arrival_time(seconds: float, expected: list[str]) -> None:
    world = evening([guest("ada", 30)])
    advance(world, seconds)
    assert present(world) == expected


def test_guest_waits_outside_while_the_door_spot_is_taken() -> None:
    world = evening([guest("ada"), guest("bea", 10)])
    overlaps = advance(world, 20)
    waiting = [item["id"] for item in world["expected"]]
    assert start_action(world, "ada", {"id": "sit", "verb": "sit", "target_id": "chair-east"})["accepted"]
    overlaps += advance(world, 10)
    assert (waiting, present(world), max(overlaps)) == (["bea"], ["ada", "bea"], 0)


def test_each_seed_draws_its_own_reproducible_arrival_needs() -> None:
    def thirst(seed: int) -> list[float]:
        world = evening([guest("ada"), guest("bea", 60)], seed=seed)
        return [item["needs"]["thirst"] for item in [*world["actors"], *world["expected"]]]
    assert thirst(1) == thirst(1)
    assert thirst(1) != thirst(2)


def test_the_scenario_not_the_room_says_who_comes() -> None:
    room = {**hall(), "actors": [{"id": "zed", "name": "Zed", "x": 2, "y": 3}]}
    assert present(evening([guest("ada")], room)) == ["ada"]


def test_room_without_a_door_cannot_host_an_evening() -> None:
    room = hall()
    room["objects"] = [item for item in room["objects"] if item["kind"] != "door"]
    with pytest.raises(ValueError):
        evening([guest("ada")], room)
