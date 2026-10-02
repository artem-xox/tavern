"""Saved worlds keep pending sounds and each visitor's attention, gaze, and emote."""

from collections.abc import Callable
import json
from typing import Any

import pytest

from tavern.memory import record_event
from tavern.persistence import parse_world
from tavern.world import create_world


def noisy_world() -> dict[str, Any]:
    """Build a room where a quarrel is still waiting to be heard."""
    world = create_world({"width": 6, "height": 4, "blocked": [], "objects": [], "actors": [
        {"id": "ada", "name": "Ada", "x": 1, "y": 1}, {"id": "bea", "name": "Bea", "x": 3, "y": 1}]})
    world["time"] = 4.0
    for actor in world["actors"]:
        record_event(world, actor, "quarrel", "Ada and Bea quarreled about beer")
    return world


def test_pending_sounds_survive_a_save() -> None:
    world = noisy_world()
    assert parse_world(json.dumps(world)) == world


def stimulus(world: dict[str, Any]) -> dict[str, Any]:
    """The pending quarrel."""
    return world["stimuli"][0]


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: world.update(stimuli={}), id="stimuli-not-a-list"),
    pytest.param(lambda world: world.update(stimuli=[7]), id="stimulus-not-a-record"),
    pytest.param(lambda world: stimulus(world).pop("noun"), id="missing-field"),
    pytest.param(lambda world: stimulus(world).update(loudness=1.5), id="too-loud"),
    pytest.param(lambda world: stimulus(world).update(reach=0), id="no-reach"),
    pytest.param(lambda world: stimulus(world).update(cell=[6, 1]), id="cell-outside-the-map"),
    pytest.param(lambda world: stimulus(world).update(time=5.0), id="heard-in-the-future"),
    pytest.param(lambda world: stimulus(world).update(sources=[1]), id="source-not-an-id"),
    pytest.param(lambda world: stimulus(world).update(about="bea"), id="about-not-a-list"),
    pytest.param(lambda world: stimulus(world).update(cause=None), id="cause-not-text"),
    pytest.param(lambda world: stimulus(world).update(event=3), id="event-not-text"),
    pytest.param(lambda world: stimulus(world).update(id=1), id="id-not-yet-issued"),
    pytest.param(lambda world: world["stimuli"].append(dict(stimulus(world))), id="duplicate-ids"),
    pytest.param(lambda world: world.update(next_stimulus_id=-1), id="negative-counter"),
    pytest.param(lambda world: world["rules"]["attention"].update(glance=0.8), id="glance-above-interrupt"),
    pytest.param(lambda world: world["rules"]["attention"].update(wall_damping=2), id="damping-amplifies"),
    pytest.param(lambda world: world["rules"]["attention"].pop("turn_seconds"), id="missing-attention-rule"),
])
def test_damaged_sounds_are_rejected(damage: Callable[[dict[str, Any]], Any]) -> None:
    world = noisy_world()
    damage(world)
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))
