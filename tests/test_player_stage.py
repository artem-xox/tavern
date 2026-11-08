"""The player's `say` on the stage: a comeback to a heckle, or their own number."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from random import Random

from tavern.evening.lockstep import LockstepCourier, Pace, run_evening
from tavern.evening.player_script import PlayerScript, Step
from tavern.mind.agents import Evaluators
from tavern.social.thoughts import active_thoughts
from tavern.evening.mind_loop import EveningPorts, MindLoop, evening_mind
from tavern.evening.player_commands import say
from tavern.mind.agents import choose_action
from tavern.mind.intentions import INTENTION_RULES
from tavern.mind.scripted import write_scripted_turn
from tavern.social.player_lines import player_turn
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


ROAST = "Cid, you sold this hall a roof it never had!"
COMEBACK = "At least my roof stood up, Cid."


def a_roast_of_cid() -> Any:
    """A reader that takes the typed number for a roast of Cid, as Haiku would."""
    async def read(view: Any, text: str) -> dict[str, Any]:
        return {"number": "roast", "target": "cid"}
    return read


def test_the_played_guest_climbs_the_stage_roasts_a_guest_and_answers_the_heckle() -> None:
    world = on_stage(seconds=0.0)
    who(world, "ada")["action"] = None
    who(world, "ada").update(status="idle", _remaining=0.0)
    world["events"].clear()
    steer(world, "ada")
    script = PlayerScript("ada", (
        Step(0.5, {"type": "act", "action": {"id": "give_speech:stage", "verb": "give_speech", "target_id": "stage"}}),
        Step(3.0, {"type": "say", "text": ROAST}), Step(9.0, {"type": "say", "text": COMEBACK})))
    config = {"model": "jev-latest", "timeout": 1.0, "temperature": 0.25, "typesafe_api_key": None}

    async def never_asked(*arguments: Any) -> dict[str, float]:
        raise AssertionError("Jev was asked in an offline evening")
    evening = asyncio.run(run_evening(
        world, config, Random(1), Evaluators(never_asked, never_asked),
        Pace(step=0.25, model_latency=1.0, time_limit=14.0), script=script, number_reader=a_roast_of_cid()))
    given = [item for item in evening.events if item["type"] == "gave_speech"]
    answered = [item for item in evening.events if item["type"] == "heckle_answered"]
    thoughts = [item["kind"] for item in active_thoughts(who(world, "cid")["thoughts"], world["time"])]
    assert ([(item["line"], item["number"], item["target_id"]) for item in given],
            "roasted" in thoughts, [item["line"] for item in answered]) == (
        [(ROAST, "roast", "cid")], True, [COMEBACK])


@pytest.mark.parametrize("make, state, has_silence", [
    pytest.param(owed_a_comeback, "comeback", False, id="owed-a-comeback"),
    pytest.param(on_stage_no_number, "on_stage", True, id="on-stage"),
    pytest.param(number_given, "none", False, id="number-given-and-no-scene"),
])
def test_the_players_turn_names_the_stage(make: Callable[[], dict[str, Any]], state: str, has_silence: bool) -> None:
    turn = player_turn(make())
    assert turn is not None
    assert (turn["state"], turn["silence_at"] is not None) == (state, has_silence)
