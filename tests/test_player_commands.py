"""The player's commands through the live runtime: taking the wheel and giving it back."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.hall.world import create_world
from tavern.server.runtime import TavernRuntime
from tavern.social.scenes import conversation_of
from test_decisions import room
from test_turns import hall as table_hall
from test_turns import talking


class Gate:
    """Fake model ports that answer only once the test opens the gate, noting who was asked."""

    def __init__(self) -> None:
        self.open = asyncio.Event()
        self.asked: list[str] = []

    async def choose(self, observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
        self.asked.append(observation["actor"]["id"])
        await self.open.wait()
        return {"action": {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}, "source": "local",
                "scores": {}, "error": None}

    async def write(self, view: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        await self.open.wait()
        return {"line": "~A written line.", "act": "remark", "addressee": None, "topic": "the road"}


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def runtime_for(tmp_path: Path, gate: Gate, map_data: dict[str, Any], player: dict[str, Any] | None) -> TavernRuntime:
    opened = TavernRuntime(map_data, tmp_path / "save.json", {"temperature": 0.0}, choose=gate.choose,
                           writer=gate.write)
    opened.world = create_world(map_data, 1)
    opened.world["player"] = player
    return opened


def test_taking_the_wheel_discards_the_decision_asked_before(tmp_path: Path) -> None:
    async def run() -> tuple[list[str], dict[str, Any] | None]:
        gate = Gate()
        opened = runtime_for(tmp_path, gate, room(), {"actor_id": "ada", "steering": False})
        opened.advance(0.1)
        await settle()
        asked = list(gate.asked)
        opened.command({"type": "steer", "on": True})
        gate.open.set()
        await settle()
        opened.advance(0.1)
        action = next(item for item in opened.world["actors"] if item["id"] == "ada")["action"]
        await opened.close()
        return asked, action
    asked, action = asyncio.run(run())
    assert (asked, action) == (["ada", "bea"], None)


def test_taking_the_wheel_discards_the_line_the_writer_was_asked_for(tmp_path: Path) -> None:
    async def run() -> list[dict[str, Any]]:
        gate = Gate()
        opened = runtime_for(tmp_path, gate, table_hall(), {"actor_id": "ada", "steering": False})
        opened.world = talking()
        opened.world["player"] = {"actor_id": "ada", "steering": False}
        opened.advance(0.1)
        await settle()
        claimed = conversation_of(opened.world, "ada")["writing"] is not None
        opened.command({"type": "steer", "on": True})
        gate.open.set()
        await settle()
        for _ in range(30):
            opened.advance(0.1)
            await settle()
        turns = conversation_of(opened.world, "ada")["turns"]
        await opened.close()
        assert claimed
        return turns
    assert asyncio.run(run()) == []


def test_giving_the_wheel_back_asks_for_a_decision_on_the_next_tick(tmp_path: Path) -> None:
    async def run() -> tuple[list[str], list[str]]:
        gate = Gate()
        opened = runtime_for(tmp_path, gate, room(), {"actor_id": "ada", "steering": True})
        opened.advance(0.1)
        await settle()
        while_steered = list(gate.asked)
        opened.command({"type": "steer", "on": False})
        opened.advance(0.1)
        await settle()
        await opened.close()
        return while_steered, list(gate.asked)
    assert asyncio.run(run()) == (["bea"], ["bea", "ada"])


@pytest.mark.parametrize("player, command", [
    pytest.param(None, {"type": "steer", "on": True}, id="no-player-in-this-evening"),
    pytest.param({"actor_id": "ada", "steering": True}, {"type": "steer", "on": "yes"}, id="on-is-not-a-boolean"),
    pytest.param({"actor_id": "ada", "steering": True}, {"type": "steer"}, id="on-is-missing"),
    pytest.param({"actor_id": "ada", "steering": True}, {"type": "steer", "on": 1}, id="on-is-a-number"),
])
def test_a_malformed_steer_is_refused_and_changes_nothing(
        tmp_path: Path, player: dict[str, Any] | None, command: dict[str, Any]) -> None:
    opened = runtime_for(tmp_path, Gate(), room(), player)
    with pytest.raises(ValueError, match="steer|player"):
        opened.command(command)
    assert opened.world["player"] == player


def test_a_steer_is_logged_naming_the_guest(tmp_path: Path) -> None:
    opened = runtime_for(tmp_path, Gate(), room(), {"actor_id": "ada", "steering": True})
    opened.command({"type": "steer", "on": False})
    [event] = [item for item in opened.world["events"] if item["type"] == "steer"]
    assert (event["actor_id"], "Ada" in event["message"], opened.world["player"]["steering"]) == ("ada", True, False)
