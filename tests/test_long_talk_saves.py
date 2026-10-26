"""A world saved while a conversation outlasts the talk's own timer still loads."""

import json

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import start_action, step_world
from tests.test_social import advance, command, seated_world


@pytest.mark.parametrize("seconds", [
    pytest.param(4, id="inside-the-timer"),
    pytest.param(9, id="past-the-timer"),
])
def test_a_world_saved_during_a_conversation_loads(seconds: int) -> None:
    world = seated_world()
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, seconds)
    assert world["actors"][0]["action"] is not None
    assert parse_world(json.dumps(world)) == world
