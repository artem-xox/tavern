"""The server tells whether Jev and Claude can be used: in /health, in the snapshot, after a startup probe."""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tavern.adapters.claude import ClaudeError
from tavern.mind.model_health import HealthBoard
from tavern.server.api import create_app


def room() -> dict[str, Any]:
    return {"width": 4, "height": 4, "tile_size": 32, "blocked": [], "objects": [],
            "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]}


def application(tmp_path: Path, board: HealthBoard | None, **kwargs: Any) -> Any:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    return create_app(map_path, tmp_path / "saves", {}, run_loop=False, health=board, **kwargs)


def test_health_without_a_board_is_just_ok(tmp_path: Path) -> None:
    with TestClient(application(tmp_path, None)) as connection:
        assert connection.get("/health").json() == {"status": "ok"}


def test_health_reports_each_model_and_still_answers_200(tmp_path: Path) -> None:
    board = HealthBoard({"jev": False, "claude": True})
    board.record("claude", ClaudeError("Claude account has no credit", 402))
    with TestClient(application(tmp_path, board)) as connection:
        response = connection.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["models"]["jev"]["status"], body["models"]["claude"]["status"]) == (
        "ok", "no_key", "no_credit")


def test_the_snapshot_carries_the_health_for_the_client_badges(tmp_path: Path) -> None:
    board = HealthBoard({"jev": True, "claude": False})
    with TestClient(application(tmp_path, board)) as connection:
        with connection.websocket_connect("/ws?session=device-test") as socket:
            ai = socket.receive_json()["ai"]
    assert ai["health"]["jev"]["status"] == "checking" and ai["health"]["claude"]["status"] == "no_key"


def test_the_probes_run_at_startup_and_fill_the_board(tmp_path: Path) -> None:
    async def jev_works() -> dict[str, Any]:
        return {}

    async def claude_refused() -> dict[str, Any]:
        raise ClaudeError("Claude HTTP 401", 401)

    board = HealthBoard({"jev": True, "claude": True})
    with TestClient(application(tmp_path, board, probes={"jev": jev_works, "claude": claude_refused})) as connection:
        for _ in range(5):
            connection.portal.call(asyncio.sleep, 0)
        models = connection.get("/health").json()["models"]
    assert (models["jev"]["status"], models["claude"]["status"]) == ("ok", "auth")


def test_the_default_app_reports_keys_missing_from_the_environment(monkeypatch: Any) -> None:
    from tavern.app import create_default_app

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(create_default_app()) as connection:
        models = connection.get("/health").json()["models"]
    assert (models["jev"]["status"], models["claude"]["status"]) == ("no_key", "no_key")


def test_the_default_app_asks_only_for_the_keys_it_has(monkeypatch: Any) -> None:
    from tavern.app import create_default_app

    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    application = create_default_app()
    assert application.state.sessions.health.snapshot()["jev"]["status"] == "checking"
