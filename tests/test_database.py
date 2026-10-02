"""A deployed world survives process replacement."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from tavern.app import create_app
from tavern.world import create_world


def room() -> dict[str, Any]:
    return {"width": 4, "height": 4, "tile_size": 32, "blocked": [],
            "objects": [], "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]}


@pytest.mark.parametrize("stored,expected", [
    pytest.param(None, (0, True), id="empty-database"),
    pytest.param("saved", (7, True), id="single-running-snapshot"),
])
def test_database_session_is_restored_paused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stored: str | None,
    expected: tuple[int, bool],
) -> None:
    from tavern import app as app_module

    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    saved = create_world(room())
    saved["tick"] = 7
    reads: list[tuple[str, str]] = []
    def load(url: str, session_id: str, slot: str) -> dict[str, Any] | None:
        reads.append((session_id, slot))
        return deepcopy(saved) if stored else None
    monkeypatch.setattr(app_module, "load_database_world", load)
    monkeypatch.setattr(app_module, "initialize_database", lambda url: None)
    monkeypatch.setattr(app_module, "save_database_world", lambda world, url, session_id, slot: None)
    application = create_app(map_path, tmp_path / "saves", {}, run_loop=False,
                             database_url="postgresql://test")
    with TestClient(application):
        world = application.state.sessions.open("device-test").world
        assert (world["tick"], world["paused"]) == expected
    assert reads == [("device-test", "auto")]


def test_save_command_writes_to_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tavern import app as app_module

    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    writes: list[tuple[dict[str, Any], str, str]] = []
    monkeypatch.setattr(app_module, "load_database_world", lambda url, session_id, slot: None)
    monkeypatch.setattr(app_module, "initialize_database", lambda url: None)
    monkeypatch.setattr(app_module, "save_database_world",
                        lambda world, url, session_id, slot: writes.append((deepcopy(world), session_id, slot)))
    application = create_app(map_path, tmp_path / "saves", {}, run_loop=False,
                             database_url="postgresql://test")
    with TestClient(application):
        application.state.sessions.open("device-test").command({"type": "save"})
    assert [(world["schema_version"], session_id, slot) for world, session_id, slot in writes] == [
        (2, "device-test", "manual"), (2, "device-test", "auto"),
    ]


@pytest.mark.parametrize("payload", [
    pytest.param("", id="empty-input"),
    pytest.param("{", id="malformed-json"),
    pytest.param('{"schema_version": 1}', id="incomplete-state"),
])
def test_invalid_database_snapshot_fails_loudly(payload: str) -> None:
    from tavern.persistence import parse_world

    with pytest.raises(ValueError):
        parse_world(payload)
