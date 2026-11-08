"""The player record: who is steered, and what a save may say about them."""

import json
from typing import Any

import pytest

from social_hall import hall
from tavern.adapters.persistence import parse_world
from tavern.hall.player import check_player, steered
from tavern.hall.world import create_world


def world_with(player: Any) -> dict[str, Any]:
    """Build a small hall world whose player record is the given one."""
    world = create_world(hall(), 1)
    world["player"] = player
    return world


@pytest.mark.parametrize("player, actor_id, expected", [
    pytest.param(None, "ada", False, id="no-player"),
    pytest.param({"actor_id": "ada", "steering": True}, "bea", False, id="another-guest"),
    pytest.param({"actor_id": "ada", "steering": True}, "ada", True, id="the-played-guest-with-the-wheel"),
    pytest.param({"actor_id": "ada", "steering": False}, "ada", False, id="the-played-guest-on-autopilot"),
])
def test_steered_says_whether_the_player_holds_the_wheel_of_a_body(
        player: Any, actor_id: str, expected: bool) -> None:
    assert steered(world_with(player), actor_id) is expected


@pytest.mark.parametrize("player", [
    pytest.param(None, id="no-player"),
    pytest.param({"actor_id": "ada", "steering": False}, id="autopilot"),
])
def test_a_sound_player_record_passes_the_save_check_and_survives_a_save(player: Any) -> None:
    world = world_with(player)
    check_player(world)
    assert parse_world(json.dumps(world))["player"] == player


@pytest.mark.parametrize("player", [
    pytest.param({"actor_id": "nobody", "steering": True}, id="unknown-actor"),
    pytest.param({"actor_id": "ada", "steering": "yes"}, id="steering-not-a-boolean"),
    pytest.param({"actor_id": "ada"}, id="missing-field"),
    pytest.param({"actor_id": "ada", "steering": True, "extra": 1}, id="unknown-field"),
    pytest.param("ada", id="not-a-record"),
])
def test_a_malformed_player_record_is_refused(player: Any) -> None:
    with pytest.raises(ValueError, match="player"):
        check_player(world_with(player))


def test_a_staff_member_cannot_be_the_player() -> None:
    world = world_with({"actor_id": "ada", "steering": True})
    world["map"]["objects"].append({"id": "bar", "kind": "bar"})
    next(item for item in world["actors"] if item["id"] == "ada")["post"] = "bar"
    with pytest.raises(ValueError, match="staff"):
        check_player(world)
