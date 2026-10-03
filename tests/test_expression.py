"""Where visitors look and which emotes they show, and for how long."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.body.expression import facing_toward, look_at
from tavern.hall.memory import record_event
from tavern.hall.world import create_world, start_action, step_world


def table_room() -> dict[str, Any]:
    """Build a room with a tap and a table whose two chairs sit at a slant, each with a visitor."""
    def chair(chair_id: str, x: int, y: int, facing: str) -> dict[str, Any]:
        return {"id": chair_id, "kind": "chair", "x": x, "y": y, "walkable": True, "table_id": "table",
                "facing": facing, "interaction_spots": [[x, y]]}
    return {"width": 8, "height": 5, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "x": 3, "y": 2}, chair("table-west", 2, 2, "east"),
        chair("table-south", 3, 4, "west"),
        {"id": "tap", "kind": "tap", "x": 7, "y": 0, "interaction_spots": [[6, 0]], "stock": 3},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 3, "y": 4}]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance physical state in 0.1 s ticks."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a visitor."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def seated(world: dict[str, Any]) -> None:
    """Seat both visitors at the table."""
    for actor_id, seat in (("ada", "table-west"), ("bea", "table-south")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]


@pytest.mark.parametrize("origin, target, expected", [
    pytest.param((0, 0), (3, 1), "east", id="east"),
    pytest.param((3, 1), (0, 0), "west", id="west"),
    pytest.param((2, 2), (2, 5), "south", id="south-is-down-the-map"),
    pytest.param((2, 5), (2, 2), "north", id="north"),
    pytest.param((0, 0), (2, 2), "east", id="diagonal-tie-turns-sideways"),
    pytest.param((1, 1), (1, 1), None, id="same-cell"),
])
def test_facing_toward_a_cell(origin: tuple[int, int], target: tuple[int, int], expected: str | None) -> None:
    assert facing_toward(origin, target) == expected


def glance_west(world: dict[str, Any]) -> None:
    """Ada glances at something to her left for two seconds."""
    look_at(actor(world, "ada"), [0, 2], world["time"] + 2.0, 0)


def glance_over(world: dict[str, Any]) -> None:
    """Ada glanced to her left, and the glance has passed."""
    look_at(actor(world, "ada"), [0, 2], world["time"] + 0.05, 0)


def bea_talks_to_ada(world: dict[str, Any]) -> None:
    """Bea starts a chat with Ada across the corner of the table."""
    seated(world)
    assert start_action(world, "bea", command("talk", "ada"))["accepted"]


def ada_talks_to_bea(world: dict[str, Any]) -> None:
    """Ada starts a chat with Bea across the corner of the table."""
    seated(world)
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]


def glance_during_chat(world: dict[str, Any]) -> None:
    """Bea talks to Ada while Ada glances to her left."""
    bea_talks_to_ada(world)
    glance_west(world)


def walking(world: dict[str, Any]) -> None:
    """Ada glances away while walking to the tap."""
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    glance_west(world)


@pytest.mark.parametrize("prepare, actor_id, expected", [
    pytest.param(lambda world: None, "ada", None, id="nothing-to-look-at"),
    pytest.param(seated, "ada", None, id="seated-keeps-the-chair-facing"),
    pytest.param(glance_west, "ada", "west", id="glancing-at-a-sound"),
    pytest.param(glance_over, "ada", None, id="glance-has-passed"),
    pytest.param(bea_talks_to_ada, "ada", "south", id="listener-faces-the-speaker"),
    pytest.param(bea_talks_to_ada, "bea", "north", id="speaker-faces-the-partner"),
    pytest.param(ada_talks_to_bea, "bea", "north", id="partner-faces-the-speaker"),
    pytest.param(glance_during_chat, "ada", "west", id="a-sound-turns-heads-mid-chat"),
    pytest.param(walking, "ada", None, id="walkers-face-their-steps"),
])
def test_facing_follows_sounds_and_partners(prepare: Callable[[dict[str, Any]], None], actor_id: str,
                                            expected: str | None) -> None:
    world = create_world(table_room())
    prepare(world)
    advance(world, 0.1)
    assert actor(world, actor_id)["facing"] == expected


def refused(world: dict[str, Any]) -> None:
    """Ada tries to drink without a mug."""
    assert not start_action(world, "ada", command("drink"))["accepted"]


def quarrel(world: dict[str, Any]) -> None:
    """Ada quarrels."""
    record_event(world, actor(world, "ada"), "quarrel", "Ada and Bea quarreled about beer")


def seat_taken(world: dict[str, Any]) -> None:
    """Someone took Ada's seat."""
    record_event(world, actor(world, "ada"), "seat_taken", "Bea took Ada's seat (Table · west)")


def chatted(world: dict[str, Any]) -> None:
    """Ada finished a pleasant chat."""
    record_event(world, actor(world, "ada"), "conversation", "Ada and Bea chatted about darts")


def quarrel_then_refused(world: dict[str, Any]) -> None:
    """Ada quarrels, then is turned away."""
    quarrel(world)
    refused(world)


@pytest.mark.parametrize("prepare, seconds, expected", [
    pytest.param(lambda world: None, 0.1, None, id="no-reason"),
    pytest.param(chatted, 0.1, None, id="pleasant-events-show-nothing-yet"),
    pytest.param(refused, 0.1, "confused", id="refusal-confuses"),
    pytest.param(refused, 2.4, "confused", id="confusion-lingers"),
    pytest.param(refused, 2.6, None, id="confusion-passes"),
    pytest.param(quarrel, 3.9, "angry", id="quarrel-angers"),
    pytest.param(quarrel, 4.1, None, id="anger-passes"),
    pytest.param(seat_taken, 0.1, "angry", id="grievance-angers"),
    pytest.param(quarrel_then_refused, 0.1, "confused", id="latest-emote-wins"),
])
def test_emotes_last_their_lifetime(prepare: Callable[[dict[str, Any]], None], seconds: float,
                                    expected: str | None) -> None:
    world = create_world(table_room())
    prepare(world)
    advance(world, seconds)
    emote = actor(world, "ada")["emote"]
    assert (emote["kind"] if emote else None) == expected


def corridor() -> dict[str, Any]:
    """Build a one-cell-wide corridor with a tap at its end."""
    return {"width": 7, "height": 1, "blocked": [], "objects": [
        {"id": "tap", "kind": "tap", "x": 6, "y": 0, "interaction_spots": [[5, 0]], "stock": 3},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 0, "y": 0}]}


@pytest.mark.parametrize("seconds, expected", [
    pytest.param(1.5, None, id="short-wait-shows-nothing"),
    pytest.param(2.5, "waiting", id="long-wait-shows"),
    pytest.param(4.0, "confused", id="giving-up-confuses"),
])
def test_long_waits_show(seconds: float, expected: str | None) -> None:
    world = create_world(corridor())
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    world["map"]["blocked"].append([1, 0])
    advance(world, seconds)
    emote = actor(world, "ada")["emote"]
    assert (emote["kind"] if emote else None) == expected
