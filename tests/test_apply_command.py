"""`apply_command`: the one door for the player's commands, shared by the live runtime and a scripted evening."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.evening.lockstep import LockstepCourier
from tavern.evening.mind_loop import EveningPorts, MindLoop, evening_mind
from tavern.evening.player_commands import apply_command
from tavern.mind.intentions import INTENTION_RULES
from tavern.mind.scripted import write_scripted_turn
from tavern.social.scenes import conversation_of
from tavern.social.stage_lines import write_scripted_stage
from test_player_hands import TAKE_BEER, ada, played
from test_turns import talking


def mind_for() -> MindLoop:
    async def nobody(*_: Any) -> dict[str, Any]:
        raise AssertionError("no decision is asked in this test")
    return evening_mind(LockstepCourier(1.0), EveningPorts(
        nobody, None, lambda view: write_scripted_turn(view, {}), lambda view: write_scripted_stage(view, {}), None),
        INTENTION_RULES)


def at_the_tap() -> dict[str, Any]:
    return played(steering=False)


def at_the_table() -> dict[str, Any]:
    world = talking()
    world["player"] = {"actor_id": "bea", "steering": True}
    return world


def steering(world: dict[str, Any]) -> bool:
    return bool(world["player"]["steering"])


def chose_the_beer(world: dict[str, Any]) -> bool:
    return (ada(world)["action"] or {}).get("verb") == "take_beer"


def holds_the_slot(world: dict[str, Any]) -> bool:
    return (conversation_of(world, "bea")["writing"] or {}).get("speaker") == "bea"


@pytest.mark.parametrize("world_of, command, effect", [
    pytest.param(at_the_tap, {"type": "steer", "on": True}, steering, id="steer"),
    pytest.param(lambda: {**played(), "player": {"actor_id": "ada", "steering": True}}, {"type": "act", "action": TAKE_BEER},
                 chose_the_beer, id="act"),
    pytest.param(at_the_table, {"type": "say", "text": "Good evening, all.", "to": "auto"}, holds_the_slot, id="say"),
])
def test_each_command_reaches_its_handlers_effect(world_of: Callable[[], dict[str, Any]], command: dict[str, Any],
                                                  effect: Callable[[dict[str, Any]], bool]) -> None:
    world = world_of()
    assert not effect(world)
    mind = mind_for()
    assert apply_command(world, mind, command) is None
    assert effect(world)
    for ticket, *_ in mind.reading.values():  # a line's reading is never awaited here
        mind.courier.cancel(ticket)


def test_options_come_back_as_the_reply() -> None:
    reply = apply_command(played(), mind_for(), {"type": "options"})
    assert reply is not None and reply["type"] == "options"


@pytest.mark.parametrize("command", [
    pytest.param({"type": "pause"}, id="operator-command"),
    pytest.param({}, id="no-type"),
])
def test_other_commands_are_refused(command: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="player command"):
        apply_command(played(), mind_for(), command)
