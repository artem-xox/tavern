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


@pytest.mark.parametrize("stored,expected_stock", [
    pytest.param(None, None, id="empty-database"),
    pytest.param("saved", 7, id="single-snapshot"),
])
def test_database_world_is_restored_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stored: str | None,
    expected_stock: int | None,
) -> None:
    from tavern import app as app_module

    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    saved = create_world(room())
    saved["tick"] = 7
    monkeypatch.setattr(app_module, "load_database_world", lambda url: deepcopy(saved) if stored else None)
    monkeypatch.setattr(app_module, "initialize_database", lambda url: None)
    application = create_app(map_path, tmp_path / "save.json", {}, run_loop=False,
                             database_url="postgresql://test")
    with TestClient(application):
        assert application.state.runtime.world["tick"] == (7 if expected_stock else 0)


def test_save_command_writes_to_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tavern import app as app_module

    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    writes: list[dict[str, Any]] = []
    monkeypatch.setattr(app_module, "load_database_world", lambda url: None)
    monkeypatch.setattr(app_module, "initialize_database", lambda url: None)
    monkeypatch.setattr(app_module, "save_database_world", lambda world, url: writes.append(deepcopy(world)))
    application = create_app(map_path, tmp_path / "save.json", {}, run_loop=False,
                             database_url="postgresql://test")
    with TestClient(application):
        application.state.runtime.command({"type": "save"})
    assert len(writes) == 1
    assert writes[0]["schema_version"] == 1


@pytest.mark.parametrize("payload", [
    pytest.param("", id="empty-input"),
    pytest.param("{", id="malformed-json"),
    pytest.param('{"schema_version": 1}', id="incomplete-state"),
])
def test_invalid_database_snapshot_fails_loudly(payload: str) -> None:
    from tavern.persistence import parse_world

    with pytest.raises(ValueError):
        parse_world(payload)
