"""Auto-pause for a person: the live hall waits for the played guest's due line, and lets go when they act."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tavern.evening.turn_hold import owed_line
from tavern.server.runtime import TavernRuntime
from tavern.server.sessions import TavernSessions
from tavern.social.scenes import conversation_of
from test_player_stage import in_a_scene, nowhere, owed_a_comeback
from test_turns import hall as table_hall
from test_turns import talking


async def remark(view: Mapping[str, Any], text: str, to: str) -> Mapping[str, Any]:
    return {"act": "remark", "addressee": None, "topic": view["conversation"]["topic"]}


def held_hall(tmp_path: Path, auto_pause: bool = True) -> TavernRuntime:
    """A live runtime in which the player steers Ada, whose line opens her talk with Bea and is due at once."""
    opened = TavernRuntime(table_hall(), tmp_path / "save.json", {"temperament": 0.0}, reader=remark,
                           auto_pause=auto_pause)
    opened.world = talking()
    opened.world["player"] = {"actor_id": "ada", "steering": True}
    return opened


def ticks(opened: TavernRuntime, seconds: float) -> None:
    for _ in range(round(seconds / 0.1)):
        opened.advance(0.1)


def spoken(opened: TavernRuntime) -> list[tuple[str, str]]:
    return [(turn["speaker"], turn["act"]) for turn in conversation_of(opened.world, "bea")["turns"]]


@pytest.mark.parametrize("auto_pause, paused", [
    pytest.param(True, True, id="a-person-is-waited-for"),
    pytest.param(False, False, id="default-keeps-the-clock-running"),
])
def test_the_hall_holds_its_clock_when_the_players_line_falls_due(tmp_path: Path, auto_pause: bool, paused: bool) -> None:
    async def run() -> tuple[bool, bool, float]:
        opened = held_hall(tmp_path, auto_pause)
        opened.advance(0.1)
        held_at = opened.world["time"]
        ticks(opened, 60.0)
        snapshot = opened.snapshot()
        await opened.close()
        return opened.world["paused"], snapshot["turn_held"], opened.world["time"] - held_at
    world_paused, turn_held, waited = asyncio.run(run())
    assert (world_paused, turn_held) == (paused, paused)
    # Held, the clock stands still however long the person thinks; running, the silence passes the turn.
    assert (waited == 0.0) == paused


@pytest.mark.parametrize("command", [
    pytest.param({"type": "typing"}, id="a-keystroke"),
    pytest.param({"type": "say", "text": "Bea, darling.", "to": "auto"}, id="a-line"),
    pytest.param({"type": "pause", "paused": False}, id="resume"),
    pytest.param({"type": "let_pass"}, id="let-it-pass"),
])
def test_the_hall_lets_go_when_the_player_answers_and_waits_no_more_for_that_line(
        tmp_path: Path, command: dict[str, Any]) -> None:
    async def run() -> tuple[bool, bool]:
        opened = held_hall(tmp_path)
        opened.advance(0.1)
        assert opened.world["paused"]
        opened.command(command)
        ticks(opened, 1.0)
        held = opened.snapshot()["turn_held"]
        await opened.close()
        return opened.world["paused"], held
    assert asyncio.run(run()) == (False, False)


def test_the_silence_counts_from_the_first_keystroke_not_from_the_line_falling_due(tmp_path: Path) -> None:
    async def run() -> tuple[list[tuple[str, str]], list[tuple[str, str]], float]:
        opened = held_hall(tmp_path)
        opened.advance(0.1)
        ticks(opened, 100.0)  # thinking, held: no game time passes
        opened.command({"type": "typing"})
        typed_at = opened.world["time"]
        ticks(opened, 19.5)
        before = spoken(opened)
        ticks(opened, 1.0)
        after = spoken(opened)
        await opened.close()
        return before, after, typed_at
    before, after, _ = asyncio.run(run())
    assert before == []
    assert after == [("ada", "silence")]


def test_letting_the_line_pass_plays_a_silence_at_once(tmp_path: Path) -> None:
    async def run() -> list[tuple[str, str]]:
        opened = held_hall(tmp_path)
        opened.advance(0.1)
        opened.command({"type": "let_pass"})
        opened.advance(0.1)
        turns = spoken(opened)
        await opened.close()
        return turns
    assert asyncio.run(run()) == [("ada", "silence")]


@pytest.mark.parametrize("player", [
    pytest.param(None, id="no-player"),
    pytest.param({"actor_id": "ada", "steering": False}, id="autopilot"),
    pytest.param({"actor_id": "cid", "steering": True}, id="not-their-turn"),
])
def test_letting_a_line_pass_is_refused_when_none_is_owed(tmp_path: Path, player: dict[str, Any] | None) -> None:
    opened = held_hall(tmp_path)
    opened.world["player"] = player
    with pytest.raises(ValueError, match="let_pass"):
        opened.command({"type": "let_pass"})


@pytest.mark.parametrize("make, owed", [
    pytest.param(owed_a_comeback, "comeback", id="a-heckle-owed-a-comeback"),
    pytest.param(in_a_scene, None, id="someone-else-speaks-next"),
    pytest.param(nowhere, None, id="in-no-scene"),
])
def test_the_line_owed_names_what_the_hall_waits_for(make: Any, owed: str | None) -> None:
    line = owed_line(make())
    assert (None if line is None else line.split(":")[0]) == owed


def test_each_line_owed_has_its_own_name(tmp_path: Path) -> None:
    world = talking()
    world["player"] = {"actor_id": "ada", "steering": True}
    first = owed_line(world)
    conversation_of(world, "ada")["turns"].extend([
        {"speaker": "ada", "addressee": "bea", "line": "Hello.", "act": "remark", "time": 0.0},
        {"speaker": "bea", "addressee": "ada", "line": "Hi.", "act": "remark", "time": 0.0}])
    assert first is not None and owed_line(world) not in (None, first)


def test_a_browser_session_is_a_person_and_holds_the_clock_for_them(tmp_path: Path) -> None:
    sessions = TavernSessions(table_hall(), tmp_path, {})
    assert sessions.open("person-at-the-page").auto_pause is True
