"""A deployed world survives process replacement."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from tavern.server.api import create_app
from tavern.hall.world import create_world


def room() -> dict[str, Any]:
    return {"width": 4, "height": 4, "tile_size": 32, "blocked": [],
            "objects": [], "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]}


class FakeStore:
    """Keeps one session's worlds like the database does: by slot, None where nothing was saved."""

    def __init__(self, session_id: str, saved: dict[str, Any] | None, log: list[tuple[str, str, str, Any]]) -> None:
        self.session_id, self.saved, self.log = session_id, saved, log

    def load(self, slot: str) -> dict[str, Any] | None:
        self.log.append(("read", self.session_id, slot, None))
        return deepcopy(self.saved) if self.saved else None

    def save(self, world: dict[str, Any], slot: str) -> None:
        self.log.append(("write", self.session_id, slot, deepcopy(world)))


@pytest.mark.parametrize("stored,expected", [
    pytest.param(None, (0, True), id="empty-database"),
    pytest.param("saved", (7, True), id="single-running-snapshot"),
])
def test_stored_session_is_restored_paused(tmp_path: Path, stored: str | None, expected: tuple[int, bool]) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    saved = create_world(room())
    saved["tick"] = 7
    log: list[tuple[str, str, str, Any]] = []
    application = create_app(map_path, tmp_path / "saves", {}, run_loop=False,
                             store_for=lambda session_id: FakeStore(session_id, saved if stored else None, log))
    with TestClient(application):
        world = application.state.sessions.open("device-test").world
        assert (world["tick"], world["paused"]) == expected
    assert [(kind, who, slot) for kind, who, slot, _ in log if kind == "read"] == [("read", "device-test", "auto")]


def test_save_command_writes_to_the_store(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    log: list[tuple[str, str, str, Any]] = []
    application = create_app(map_path, tmp_path / "saves", {}, run_loop=False,
                             store_for=lambda session_id: FakeStore(session_id, None, log))
    with TestClient(application):
        application.state.sessions.open("device-test").command({"type": "save"})
    assert [(world["schema_version"], session_id, slot)
            for kind, session_id, slot, world in log if kind == "write"] == [
        (13, "device-test", "manual"), (13, "device-test", "auto"),
    ]


@pytest.mark.parametrize("payload", [
    pytest.param("", id="empty-input"),
    pytest.param("{", id="malformed-json"),
    pytest.param('{"schema_version": 1}', id="incomplete-state"),
])
def test_invalid_database_snapshot_fails_loudly(payload: str) -> None:
    from tavern.adapters.persistence import parse_world

    with pytest.raises(ValueError):
        parse_world(payload)
