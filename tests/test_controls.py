"""The operator's debug commands change the world, or refuse loudly and leave it as it was."""

from copy import deepcopy
from typing import Any

import pytest

from tavern.server.controls import forced_action, refill_tap, set_paused, set_speed, toggle_block
from tavern.hall.world import create_world

WALLS = [[0, 0]]


def hall() -> dict[str, Any]:
    return create_world({
        "width": 8, "height": 6, "tile_size": 32, "blocked": WALLS,
        "objects": [{"id": "tap", "kind": "tap", "name": "Beer", "x": 4, "y": 1,
                     "interaction_spots": [[3, 1]], "stock": 2},
                    {"id": "board", "kind": "darts", "name": "Darts", "x": 6, "y": 4,
                     "interaction_spots": [[5, 4]]}],
        "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}],
    })


@pytest.mark.parametrize("paused", [
    pytest.param(True, id="pause"),
    pytest.param(False, id="resume"),
])
def test_pause_and_resume(paused: bool) -> None:
    world = hall()
    set_paused(world, {"paused": paused})
    assert world["paused"] is paused


@pytest.mark.parametrize("command", [
    pytest.param({}, id="missing"),
    pytest.param({"paused": 1}, id="number"),
    pytest.param({"paused": "yes"}, id="text"),
])
def test_pause_refuses_a_non_boolean(command: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="paused"):
        set_paused(hall(), command)


@pytest.mark.parametrize("value", [
    pytest.param(0.25, id="slowest"),
    pytest.param(1, id="normal"),
    pytest.param(8, id="fastest"),
])
def test_speed_within_range_is_set(value: float) -> None:
    world = hall()
    set_speed(world, {"value": value})
    assert world["speed"] == value


@pytest.mark.parametrize("command", [
    pytest.param({}, id="missing"),
    pytest.param({"value": 0.2}, id="too-slow"),
    pytest.param({"value": 9}, id="too-fast"),
    pytest.param({"value": True}, id="bool"),
])
def test_speed_outside_range_is_refused(command: dict[str, Any]) -> None:
    world = hall()
    with pytest.raises(ValueError, match="Speed"):
        set_speed(world, command)
    assert world["speed"] == 1.0


def test_refill_adds_to_the_tap_and_repeats_add_again() -> None:
    world = hall()
    refill_tap(world, {"object_id": "tap", "amount": 3})
    refill_tap(world, {"object_id": "tap", "amount": 3})
    assert world["map"]["objects"][0]["stock"] == 8


@pytest.mark.parametrize("command, message", [
    pytest.param({"object_id": "tap", "amount": 0}, "Amount", id="nothing"),
    pytest.param({"object_id": "tap", "amount": 1001}, "Amount", id="too-much"),
    pytest.param({"object_id": "board", "amount": 1}, "Unknown beer tap", id="not-a-tap"),
    pytest.param({"amount": 1}, "Unknown beer tap", id="no-id"),
])
def test_refill_refuses_bad_commands(command: dict[str, Any], message: str) -> None:
    world = hall()
    with pytest.raises(ValueError, match=message):
        refill_tap(world, command)
    assert world["map"]["objects"][0]["stock"] == 2


def test_blocking_twice_blocks_once_and_unblocking_clears() -> None:
    world = hall()
    block = {"x": 2, "y": 2, "blocked": True}
    toggle_block(world, WALLS, block)
    toggle_block(world, WALLS, block)
    assert world["map"]["blocked"].count([2, 2]) == 1
    toggle_block(world, WALLS, {**block, "blocked": False})
    assert [2, 2] not in world["map"]["blocked"]


@pytest.mark.parametrize("command, message", [
    pytest.param({"x": 0, "y": 0, "blocked": False}, "Permanent walls", id="permanent-wall"),
    pytest.param({"x": 1, "y": 1, "blocked": True}, "under a visitor", id="under-a-visitor"),
    pytest.param({"x": 4, "y": 1, "blocked": True}, "Furniture", id="furniture"),
    pytest.param({"x": 8, "y": 1, "blocked": True}, "Cell x", id="off-the-map"),
    pytest.param({"x": 2, "y": 2, "blocked": "yes"}, "blocked", id="not-a-boolean"),
])
def test_block_refuses_bad_cells(command: dict[str, Any], message: str) -> None:
    world = hall()
    before = deepcopy(world["map"]["blocked"])
    with pytest.raises(ValueError, match=message):
        toggle_block(world, WALLS, command)
    assert world["map"]["blocked"] == before


def test_forced_action_returns_a_new_world_and_leaves_the_old_one() -> None:
    world = hall()
    before = deepcopy(world)
    forced, actor_id = forced_action(world, {"actor_id": "ada", "action": {
        "id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}})
    assert actor_id == "ada"
    assert forced["actors"][0]["action"]["verb"] == "take_beer"
    assert world == before


@pytest.mark.parametrize("command, message", [
    pytest.param({}, "Expected actor_id", id="empty"),
    pytest.param({"actor_id": "ada", "action": "dance"}, "Expected actor_id", id="action-not-a-mapping"),
    pytest.param({"actor_id": "zed", "action": {"id": "x", "verb": "wait"}}, "Unknown visitor", id="unknown-visitor"),
    pytest.param({"actor_id": "ada", "action": {"id": 1, "verb": "wait"}}, "strings", id="id-not-text"),
    pytest.param({"actor_id": "ada", "action": {"id": "x", "verb": "wait", "target_id": 3}}, "target",
                 id="target-not-text"),
    pytest.param({"actor_id": "ada", "action": {"id": "x", "verb": "fly", "target_id": None}},
                 "Unknown action verb", id="world-refuses"),
])
def test_forced_action_refuses_bad_commands(command: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        forced_action(hall(), command)
