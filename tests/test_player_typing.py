"""The player's typing signal: the `typing` command, and what a save may say about it."""

import json
from typing import Any

import pytest

from social_hall import hall
from tavern.adapters.persistence import parse_world
from tavern.evening.player_commands import typing
from tavern.hall.player import check_player
from tavern.hall.world import create_world


def world_with(player: Any, time: float = 12.5) -> dict[str, Any]:
    """Build a small hall world at a given game time whose player record is the given one."""
    world = create_world(hall(), 1)
    world.update(player=player, time=time)
    return world


def test_typing_notes_the_game_time_of_the_keystroke_and_logs_nothing() -> None:
    world = world_with({"actor_id": "ada", "steering": True, "typing_at": None})
    events = len(world["events"])
    typing(world, {"type": "typing"})
    assert (world["player"]["typing_at"], len(world["events"])) == (12.5, events)


@pytest.mark.parametrize("player, reason", [
    pytest.param(None, "player", id="no-player"),
    pytest.param({"actor_id": "ada", "steering": False, "typing_at": None}, "wheel", id="autopilot"),
])
def test_typing_is_refused_without_a_player_who_holds_the_wheel(player: Any, reason: str) -> None:
    world = world_with(player)
    with pytest.raises(ValueError, match=reason):
        typing(world, {"type": "typing"})


@pytest.mark.parametrize("typing_at", [
    pytest.param(None, id="before-the-first-keystroke"),
    pytest.param(7.5, id="after-a-keystroke"),
])
def test_the_last_keystroke_survives_a_save(typing_at: float | None) -> None:
    world = world_with({"actor_id": "ada", "steering": True, "typing_at": typing_at})
    check_player(world)
    assert parse_world(json.dumps(world))["player"]["typing_at"] == typing_at


@pytest.mark.parametrize("typing_at", [
    pytest.param("now", id="not-a-number"),
    pytest.param(True, id="a-boolean"),
    pytest.param(-1.0, id="before-the-evening"),
])
def test_a_malformed_last_keystroke_is_refused(typing_at: Any) -> None:
    with pytest.raises(ValueError, match="typing_at"):
        check_player(world_with({"actor_id": "ada", "steering": True, "typing_at": typing_at}))
