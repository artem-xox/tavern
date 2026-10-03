"""Saved worlds keep pending sounds and each visitor's attention, gaze, and emote."""

from collections.abc import Callable
import json
from typing import Any

import pytest

from tavern.expression import look_at
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


def expressive_world() -> dict[str, Any]:
    """Build a room where Ada glances, frowns, and was just interrupted."""
    world = noisy_world()
    look_at(world["actors"][0], [3, 1], 6.0, 0)
    world["actors"][0].update(facing="east", interrupted_at=4.0)
    return world


def test_gaze_and_emotes_survive_a_save() -> None:
    world = expressive_world()
    assert world["actors"][0]["emote"] == {"kind": "angry", "until": 8.0}
    assert parse_world(json.dumps(world)) == world


def ada(world: dict[str, Any]) -> dict[str, Any]:
    """The first visitor."""
    return world["actors"][0]


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: ada(world).update(facing="up"), id="unknown-facing"),
    pytest.param(lambda world: ada(world).pop("gaze"), id="missing-gaze"),
    pytest.param(lambda world: ada(world).update(gaze={"cell": [3, 1]}), id="gaze-without-end"),
    pytest.param(lambda world: ada(world)["gaze"].update(cell=[9, 9]), id="gaze-outside-the-map"),
    pytest.param(lambda world: ada(world)["gaze"].update(stimulus_id="0"), id="gaze-cause-not-an-id"),
    pytest.param(lambda world: ada(world)["emote"].update(kind="smug"), id="unknown-emote"),
    pytest.param(lambda world: ada(world)["emote"].update(until=-1.0), id="emote-ending-before-the-evening"),
    pytest.param(lambda world: ada(world).update(interrupted_at=5.0), id="interrupted-in-the-future"),
    pytest.param(lambda world: world["rules"]["emote_seconds"].pop("alert"), id="missing-emote-lifetime"),
    pytest.param(lambda world: world["rules"].update(long_wait=-1), id="negative-long-wait"),
])
def test_damaged_expressions_are_rejected(damage: Callable[[dict[str, Any]], Any]) -> None:
    world = expressive_world()
    damage(world)
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))
