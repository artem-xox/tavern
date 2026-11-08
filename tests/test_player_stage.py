"""The player's `say` on the stage: a comeback to a heckle, or their own number."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from random import Random

from tavern.evening.lockstep import LockstepCourier
from tavern.evening.mind_loop import EveningPorts, MindLoop, evening_mind
from tavern.evening.player_commands import say
from tavern.mind.agents import choose_action
from tavern.mind.intentions import INTENTION_RULES
from tavern.mind.scripted import write_scripted_turn
from tavern.social.stage_lines import write_scripted_stage
from tavern.social.scenes import conversation_of
from dice_hall import advance, who
from test_stage_lines import heckled, on_stage, performed
from test_turns import talking

TEXT = "Sit down yourself, Cid."


def mind_for() -> MindLoop:
    """The offline mind of an evening: local decisions, scripted words, every reading a remark or a pitch."""
    return evening_mind(LockstepCourier(1.0), EveningPorts(
        lambda observation: choose_action(observation, {"temperature": 0.0}, Random(1)), None,
        lambda view: write_scripted_turn(view, {}), lambda view: write_scripted_stage(view, {}), None),
        INTENTION_RULES)


def steer(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """The player takes the wheel of a guest."""
    world["player"] = {"actor_id": actor_id, "steering": True}
    return world


def owed_a_comeback() -> dict[str, Any]:
    return steer(heckled(), "ada")


def on_stage_no_number() -> dict[str, Any]:
    return steer(on_stage(), "ada")


def in_a_scene() -> dict[str, Any]:
    return steer(talking(), "bea")


def number_given() -> dict[str, Any]:
    return steer(performed(), "ada")


def nowhere() -> dict[str, Any]:
    world = talking()
    return steer(world, "cid")


def where_it_went(world: dict[str, Any]) -> str:
    """Where a `say` ended up once the reading is back: a comeback, a number, or the scene's claim."""
    mind = mind_for()
    say(world, mind, {"type": "say", "text": TEXT})
    for _ in range(4):
        asyncio.run(mind.courier.settle())
        advance(world, 1.0)
        mind.tick(world)
    kinds = {item["type"]: item for item in world["events"]}
    if "heckle_answered" in kinds and kinds["heckle_answered"]["line"] == TEXT:
        return "comeback"
    if any(item["type"] == "gave_speech" and item["line"] == TEXT for item in world["events"]):
        return "number"
    scene = conversation_of(world, world["player"]["actor_id"])
    return "scene" if scene is not None and any(turn["line"] == TEXT for turn in scene["turns"]) else "lost"


@pytest.mark.parametrize("make, went", [
    pytest.param(owed_a_comeback, "comeback", id="owed-a-comeback"),
    pytest.param(on_stage_no_number, "number", id="on-stage-no-number"),
    pytest.param(in_a_scene, "scene", id="in-a-scene"),
])
def test_a_say_goes_where_the_played_guest_is(make: Callable[[], dict[str, Any]], went: str) -> None:
    assert where_it_went(make()) == went


@pytest.mark.parametrize("make", [
    pytest.param(number_given, id="on-stage-number-given-and-in-no-scene"),
    pytest.param(nowhere, id="nowhere"),
])
def test_a_say_with_nobody_listening_is_refused(make: Callable[[], dict[str, Any]]) -> None:
    with pytest.raises(ValueError, match="Nobody is listening"):
        say(make(), mind_for(), {"type": "say", "text": TEXT})
