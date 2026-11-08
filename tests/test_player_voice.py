"""The player's `say` through the live runtime: the slot, cutting in on a guest, and the act's effect."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tavern.hall.world import create_world
from tavern.server.runtime import TavernRuntime
from tavern.social.scenes import conversation_of
from tavern.social.thoughts import think
from test_turns import hall as table_hall
from test_turns import talking

TEXT = "Mind your tongue, Ada."


class Voices:
    """Fake model ports: a line writer held shut until the test opens it, and a reader with a fixed reading."""

    def __init__(self, reading: Mapping[str, Any] | Exception) -> None:
        self.open = asyncio.Event()
        self.views: list[Mapping[str, Any]] = []
        self.reading = reading

    async def write(self, view: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        self.views.append(view)
        await self.open.wait()
        return {"line": "~A written line.", "act": "remark", "topic": "the road",
                "addressee": "bea" if view["speaker"]["id"] == "ada" else None}

    async def read(self, view: Mapping[str, Any], text: str, to: str) -> Mapping[str, Any]:
        if isinstance(self.reading, Exception):
            raise self.reading
        return self.reading


def played(tmp_path: Path, voices: Voices, world: dict[str, Any], actor_id: str = "bea") -> TavernRuntime:
    """A runtime over the world, in which the player steers the given guest."""
    opened = TavernRuntime(table_hall(), tmp_path / "save.json", {"temperament": 0.0}, writer=voices.write,
                           reader=voices.read)
    opened.world = world
    opened.world["player"] = {"actor_id": actor_id, "steering": True}
    return opened


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def run_until(opened: TavernRuntime, turns: int, scene_of: str = "ada") -> list[dict[str, Any]]:
    for _ in range(300):
        opened.advance(0.1)
        await settle()
        if len(conversation_of(opened.world, scene_of)["turns"]) >= turns:
            break
    return conversation_of(opened.world, scene_of)["turns"]


def test_the_players_line_cuts_in_on_a_guest_whose_line_is_in_flight(tmp_path: Path) -> None:
    async def run() -> tuple[list[dict[str, Any]], list[str], list[Mapping[str, Any]]]:
        voices = Voices({"act": "remark", "addressee": "ada", "topic": "manners"})
        opened = played(tmp_path, voices, talking())
        opened.advance(0.1)
        await settle()
        claimed = conversation_of(opened.world, "ada")["writing"]["speaker"]
        opened.command({"type": "say", "text": TEXT, "to": "auto"})
        voices.open.set()
        turns = await run_until(opened, 2)
        events = [item for item in opened.world["events"] if item["type"] == "turn"]
        await opened.close()
        return turns, [claimed, *(item.get("player", False) for item in events)], voices.views
    turns, trail, views = asyncio.run(run())
    assert trail[0] == "ada"
    # The player speaks first, in their own words; the guest's late answer is dropped and they are asked again.
    assert [(turn["speaker"], turn["line"]) for turn in turns[:1]] == [("bea", TEXT)]
    assert trail[1] is True
    assert [turn["line"] for turn in views[-1]["conversation"]["turns"]] == [TEXT]
    assert "~A written line." not in [turn["line"] for turn in turns[:1]]


def test_the_players_answer_to_a_guest_has_the_effect_of_its_act(tmp_path: Path) -> None:
    async def run() -> tuple[list[str], list[str]]:
        voices = Voices({"act": "insult", "addressee": "ada", "topic": "manners"})
        voices.open.set()
        world = talking()
        bea = next(item for item in world["actors"] if item["id"] == "bea")
        ada = next(item for item in world["actors"] if item["id"] == "ada")
        for _ in range(2):
            think(bea, "quarrel", world["time"], "Quarreled with Ada about ale", "quarrel", about=ada)
        opened = played(tmp_path, voices, world)
        turns = await run_until(opened, 1)
        assert turns[0]["addressee"] == "bea"
        opened.command({"type": "say", "text": TEXT, "to": "auto"})
        turns = await run_until(opened, 2)
        await opened.close()
        return [turns[1]["act"], turns[1]["line"]], [item["kind"] for item in ada["thoughts"]]
    spoken, thoughts = asyncio.run(run())
    assert spoken == ["insult", TEXT]
    assert "insulted" in thoughts


def test_a_reading_that_fails_is_spoken_as_a_remark_in_the_players_words(tmp_path: Path) -> None:
    async def run() -> list[dict[str, Any]]:
        voices = Voices(RuntimeError("the reader is down"))
        voices.open.set()
        opened = played(tmp_path, voices, talking())
        await run_until(opened, 1)
        opened.command({"type": "say", "text": TEXT, "to": "ada"})
        turns = await run_until(opened, 2)
        await opened.close()
        return turns
    turns = asyncio.run(run())
    assert [(item["speaker"], item["act"], item["addressee"], item["line"]) for item in turns[1:2]] == [
        ("bea", "remark", "ada", TEXT)]


@pytest.mark.parametrize("player, scene, text, to", [
    pytest.param(None, True, TEXT, "auto", id="no-player"),
    pytest.param({"actor_id": "bea", "steering": False}, True, TEXT, "auto", id="autopilot"),
    pytest.param({"actor_id": "bea", "steering": True}, False, TEXT, "auto", id="no-scene"),
    pytest.param({"actor_id": "bea", "steering": True}, True, "   ", "auto", id="empty"),
    pytest.param({"actor_id": "bea", "steering": True}, True, "x" * 201, "auto", id="too-long"),
    pytest.param({"actor_id": "bea", "steering": True}, True, 7, "auto", id="not-text"),
    pytest.param({"actor_id": "bea", "steering": True}, True, TEXT, "cid", id="to-a-stranger"),
    pytest.param({"actor_id": "bea", "steering": True}, True, TEXT, "bea", id="to-themselves"),
])
def test_a_say_the_world_refuses_changes_nothing(tmp_path: Path, player: dict[str, Any] | None, scene: bool,
                                                 text: Any, to: str) -> None:
    opened = played(tmp_path, Voices({}), talking() if scene else create_world(table_hall(), 4))
    opened.world["player"] = player
    before = [(item["writing"], item["written"]) for item in opened.world["conversations"]]
    with pytest.raises(ValueError, match="say"):
        opened.command({"type": "say", "text": text, "to": to})
    assert [(item["writing"], item["written"]) for item in opened.world["conversations"]] == before


def test_a_second_line_is_refused_while_the_first_is_being_read(tmp_path: Path) -> None:
    async def run() -> None:
        opened = played(tmp_path, Voices({}), talking())
        opened.command({"type": "say", "text": TEXT, "to": "auto"})
        try:
            with pytest.raises(ValueError, match="one at a time"):
                opened.command({"type": "say", "text": "And another thing.", "to": "auto"})
        finally:
            await opened.close()
    asyncio.run(run())
