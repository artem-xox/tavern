"""Transport, operator controls, persistence, and asynchronous decisions."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from tavern.app import TavernRuntime, create_app, create_default_app


def room() -> dict[str, Any]:
    return {
        "width": 8, "height": 6, "tile_size": 32, "blocked": [[0, 0]],
        "objects": [{"id": "tap", "kind": "tap", "name": "Beer", "x": 4, "y": 1,
                     "interaction_spots": [[3, 1]], "stock": 2}],
        "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}],
    }


def runtime(tmp_path: Path) -> TavernRuntime:
    return TavernRuntime(room(), tmp_path / "save.json", {"typesafe_api_key": None})


def client(tmp_path: Path) -> TestClient:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    return TestClient(create_app(map_path, tmp_path / "save.json", {"typesafe_api_key": "secret-test-key"}, run_loop=False))


def test_snapshot_and_health_never_expose_api_credentials(tmp_path: Path) -> None:
    with client(tmp_path) as connection, connection.websocket_connect("/ws?session=device-test") as socket:
        socket.receive_json()
        response = connection.get("/api/state?session=device-test")
        assert response.status_code == 200
        assert response.json()["ai"]["mode"] == "jev"
        assert "secret-test-key" not in response.text
        assert connection.get("/health").json()["status"] == "ok"


def test_default_factory_resolves_repository_map() -> None:
    world = create_default_app().state.sessions.open("device-test").world
    assert (world["map"]["width"], len(world["actors"])) == (20, 3)


def test_default_factory_does_not_use_unenabled_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://unreachable")
    monkeypatch.delenv("TAVERN_DATABASE_ENABLED", raising=False)
    app = create_default_app()
    assert app.state.sessions.database_url is None


@pytest.mark.parametrize("command,field,expected", [
    pytest.param({"type": "pause", "paused": True}, "paused", True, id="pause"),
    pytest.param({"type": "speed", "value": 2}, "speed", 2, id="speed"),
])
def test_controls_change_server_state(tmp_path: Path, command: dict[str, Any], field: str, expected: Any) -> None:
    engine = runtime(tmp_path)
    engine.command(command)
    assert engine.world[field] == expected


@pytest.mark.parametrize("command", [
    pytest.param({}, id="empty-command"),
    pytest.param({"type": "pause", "paused": "yes"}, id="malformed-pause"),
    pytest.param({"type": "speed", "value": 0}, id="invalid-speed"),
    pytest.param({"type": "speed", "value": float("nan")}, id="nonfinite-speed"),
    pytest.param({"type": "refill", "object_id": "tap", "amount": -1}, id="negative-refill"),
    pytest.param({"type": "refill", "object_id": "missing", "amount": 1}, id="unknown-resource"),
    pytest.param({"type": "block", "x": True, "y": 2, "blocked": True}, id="malformed-cell"),
    pytest.param({"type": "block", "x": 1, "y": 1, "blocked": True}, id="occupied-cell"),
    pytest.param({"type": "block", "x": 0, "y": 0, "blocked": False}, id="static-wall"),
    pytest.param({"type": "force_action", "actor_id": "missing", "action": {}}, id="unknown-actor"),
    pytest.param({"type": "force_action", "actor_id": "ada", "action": {"verb": "magic"}}, id="unknown-action"),
    pytest.param({"type": "force_action", "actor_id": "ada", "action": {"id": "bad", "verb": []}}, id="non-string-verb"),
])
def test_invalid_commands_leave_world_unchanged(tmp_path: Path, command: dict[str, Any]) -> None:
    engine = runtime(tmp_path)
    before = deepcopy(engine.world)
    with pytest.raises(ValueError):
        engine.command(command)
    assert engine.world == before


def test_refill_and_duplicate_block_commands_are_safe(tmp_path: Path) -> None:
    engine = runtime(tmp_path)
    engine.command({"type": "refill", "object_id": "tap", "amount": 3})
    command = {"type": "block", "x": 2, "y": 2, "blocked": True}
    engine.command(command)
    engine.command(command)
    assert engine.world["map"]["objects"][0]["stock"] == 5
    assert engine.world["map"]["blocked"].count([2, 2]) == 1
    engine.command({**command, "blocked": False})
    assert [2, 2] not in engine.world["map"]["blocked"]


def test_save_load_restores_ongoing_action_and_resources(tmp_path: Path) -> None:
    engine = runtime(tmp_path)
    engine.command({"type": "force_action", "actor_id": "ada", "action": {
        "id": "take_beer:tap", "verb": "take_beer", "target_id": "tap",
    }})
    engine.command({"type": "save"})
    saved = json.loads((tmp_path / "save.json").read_text())
    engine.command({"type": "reset"})
    engine.command({"type": "load"})
    assert engine.world["actors"] == saved["actors"]
    assert engine.world["map"] == saved["map"]
    from tavern.world import step_world
    for _ in range(150):
        step_world(engine.world, 0.1)
    assert engine.world["actors"][0]["inventory"]["beer"] == 1
    assert engine.world["map"]["objects"][0]["stock"] == 1
    assert engine.world["map"]["objects"][0]["reserved_by"] is None


@pytest.mark.parametrize("saved", [
    pytest.param({}, id="empty-snapshot"),
    pytest.param({"schema_version": 99}, id="unknown-version"),
    pytest.param("not-json", id="malformed-json"),
])
def test_invalid_load_preserves_current_world(tmp_path: Path, saved: Any) -> None:
    engine = runtime(tmp_path)
    (tmp_path / "save.json").write_text(saved if isinstance(saved, str) else json.dumps(saved))
    before = deepcopy(engine.world)
    with pytest.raises(ValueError):
        engine.command({"type": "load"})
    assert engine.world == before


def test_save_load_accepts_dynamically_blocked_interaction_spot(tmp_path: Path) -> None:
    engine = runtime(tmp_path)
    engine.command({"type": "block", "x": 3, "y": 1, "blocked": True})
    engine.command({"type": "save"})
    engine.command({"type": "reset"})
    engine.command({"type": "load"})
    assert [3, 1] in engine.world["map"]["blocked"]


@pytest.mark.parametrize("field,value", [
    pytest.param("_remaining", "bad", id="malformed-action-timer"),
    pytest.param("path", [[100, 100]], id="out-of-bounds-path"),
    pytest.param("_spot", "bad", id="malformed-reserved-spot"),
    pytest.param("knowledge", [], id="malformed-knowledge"),
    pytest.param("knowledge", {"objects": [], "cells": []}, id="malformed-known-objects"),
    pytest.param("memory", {}, id="malformed-memories"),
])
def test_invalid_runtime_snapshot_is_rejected_atomically(tmp_path: Path, field: str, value: Any) -> None:
    engine = runtime(tmp_path)
    saved = deepcopy(engine.world)
    saved["actors"][0][field] = value
    (tmp_path / "save.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        engine.command({"type": "load"})
    assert engine.world["actors"][0][field] != value


def test_websocket_command_errors_do_not_disconnect(tmp_path: Path) -> None:
    with client(tmp_path) as connection, connection.websocket_connect("/ws?session=device-test") as socket:
        assert socket.receive_json()["type"] == "snapshot"
        socket.send_json({"type": "speed", "value": -2})
        message = socket.receive_json()
        assert message["type"] == "error"
        socket.send_json({"type": "pause", "paused": True})
        assert socket.receive_json()["state"]["paused"] is True


def test_slow_ai_does_not_freeze_world_or_override_forced_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        async def delayed_choice(observation: Any, config: Any, rng: Any) -> dict[str, Any]:
            await gate.wait()
            return {"action": {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"},
                    "source": "jev", "scores": {"take_beer:tap": 4}, "error": None}
        monkeypatch.setattr("tavern.app.choose_action", delayed_choice)
        engine = runtime(tmp_path)
        engine.advance(0.1)
        await asyncio.sleep(0)
        engine.command({"type": "force_action", "actor_id": "ada", "action": {
            "id": "wait", "verb": "wait", "target_id": None,
        }})
        for _ in range(60):
            engine.advance(0.1)
        assert engine.world["time"] >= 5
        gate.set()
        await asyncio.sleep(0)
        engine.advance(0.1)
        assert engine.world["actors"][0]["action"] is None
        assert engine.world["actors"][0]["inventory"]["beer"] == 0
        await engine.close()
    asyncio.run(scenario())
