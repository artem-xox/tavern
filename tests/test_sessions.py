"""Private evenings per device: isolation, ticking only while watched, autosave."""

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
import pytest

from tavern.app import TavernSessions, create_app

FIRST = "device-first"
SECOND = "device-second"


def room() -> dict[str, Any]:
    return {
        "width": 8, "height": 6, "tile_size": 32, "blocked": [],
        "objects": [], "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}],
    }


def sessions(tmp_path: Path) -> TavernSessions:
    return TavernSessions(room(), tmp_path, {"typesafe_api_key": None})


def client(tmp_path: Path) -> TestClient:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    return TestClient(create_app(map_path, tmp_path / "saves", {"typesafe_api_key": None}, run_loop=False))


def receive_until(socket: Any, accept: Callable[[Mapping[str, Any]], bool]) -> Mapping[str, Any]:
    # Periodic snapshots interleave with command replies, so skip a bounded number of them.
    for _ in range(50):
        message = socket.receive_json()
        if accept(message):
            return message
    raise AssertionError("Expected message never arrived")


@pytest.mark.parametrize("session_id", [
    pytest.param("", id="empty-id"),
    pytest.param("short", id="too-short"),
    pytest.param("../../etc/passwd", id="path-traversal"),
    pytest.param("a" * 65, id="too-long"),
    pytest.param(None, id="not-a-string"),
])
def test_malformed_session_ids_are_rejected(tmp_path: Path, session_id: Any) -> None:
    with pytest.raises(ValueError):
        sessions(tmp_path).open(session_id)


def test_new_session_waits_at_the_door(tmp_path: Path) -> None:
    world = sessions(tmp_path).open(FIRST).world
    assert (world["paused"], world["tick"]) == (True, 0)


def test_sessions_do_not_share_worlds(tmp_path: Path) -> None:
    hub = sessions(tmp_path)
    first, second = hub.open(FIRST), hub.open(SECOND)
    first.command({"type": "speed", "value": 4})
    assert (first.world["speed"], second.world["speed"]) == (4, 1)


@pytest.mark.parametrize("opened,closed,ticking", [
    pytest.param([], [], set(), id="no-sessions"),
    pytest.param([FIRST], [], {FIRST}, id="single-open-page"),
    pytest.param([FIRST, FIRST], [FIRST], {FIRST}, id="duplicate-page-still-open"),
    pytest.param([FIRST, SECOND], [SECOND], {FIRST}, id="closed-session-stops"),
    pytest.param([FIRST], [FIRST], set(), id="last-page-closed"),
])
def test_only_watched_sessions_advance(
    tmp_path: Path, opened: Sequence[str], closed: Sequence[str], ticking: set[str],
) -> None:
    async def scenario() -> set[str]:
        hub = sessions(tmp_path)
        runtimes = {session_id: hub.open(session_id) for session_id in opened}
        for runtime in runtimes.values():
            runtime.command({"type": "pause", "paused": False})
        for session_id in closed:
            await hub.release(session_id)
        hub.advance(0.1)
        await hub.close()
        return {session_id for session_id, runtime in runtimes.items() if runtime.world["tick"] > 0}
    assert asyncio.run(scenario()) == ticking


def test_reopened_session_resumes_paused_where_it_stopped(tmp_path: Path) -> None:
    async def scenario() -> tuple[int, bool]:
        hub = sessions(tmp_path)
        hub.open(FIRST).command({"type": "pause", "paused": False})
        for _ in range(5):
            hub.advance(0.1)
        await hub.release(FIRST)
        restored = hub.open(FIRST).world
        await hub.close()
        return restored["tick"], restored["paused"]
    assert asyncio.run(scenario()) == (5, True)


def test_restarted_server_restores_running_sessions_paused(tmp_path: Path) -> None:
    async def before_deploy() -> None:
        hub = sessions(tmp_path)
        hub.open(FIRST).command({"type": "pause", "paused": False})
        for _ in range(3):
            hub.advance(0.1)
        await hub.close()
    asyncio.run(before_deploy())
    hub = sessions(tmp_path)
    first, second = hub.open(FIRST).world, hub.open(SECOND).world
    assert (first["tick"], first["paused"], second["tick"]) == (3, True, 0)


def test_manual_saves_belong_to_their_session(tmp_path: Path) -> None:
    hub = sessions(tmp_path)
    hub.open(FIRST).command({"type": "save"})
    with pytest.raises(ValueError):
        hub.open(SECOND).command({"type": "load"})


def test_websocket_serves_the_requested_session(tmp_path: Path) -> None:
    with client(tmp_path) as connection, \
            connection.websocket_connect(f"/ws?session={FIRST}") as first, \
            connection.websocket_connect(f"/ws?session={SECOND}") as second:
        first.receive_json()
        second.receive_json()
        first.send_json({"type": "speed", "value": 4})
        receive_until(first, lambda message: message["state"]["speed"] == 4)
        assert receive_until(second, lambda message: message["type"] == "snapshot")["state"]["speed"] == 1


@pytest.mark.parametrize("query", [
    pytest.param("", id="missing-session"),
    pytest.param("?session=bad", id="malformed-session"),
])
def test_websocket_without_valid_session_is_refused(tmp_path: Path, query: str) -> None:
    with client(tmp_path) as connection:
        with pytest.raises(WebSocketDisconnect):
            with connection.websocket_connect(f"/ws{query}") as socket:
                socket.receive_json()


@pytest.mark.parametrize("query,status", [
    pytest.param("", 422, id="missing-session"),
    pytest.param(f"?session={SECOND}", 404, id="session-not-open"),
])
def test_state_endpoint_only_reads_open_sessions(tmp_path: Path, query: str, status: int) -> None:
    with client(tmp_path) as connection, connection.websocket_connect(f"/ws?session={FIRST}") as socket:
        socket.receive_json()
        assert connection.get(f"/api/state{query}").status_code == status
