"""The live server writes lines with Haiku when a Claude key is configured, and says which writer is active."""

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tavern.app import TavernRuntime, create_app, create_default_app


def room() -> dict[str, Any]:
    """A one-guest room."""
    return {"width": 4, "height": 4, "blocked": [], "objects": [], "actors": [{"id": "ada", "name": "Ada", "x": 1,
                                                                               "y": 1}]}


async def fake_writer(view: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    """A turn writer that is never asked here."""
    raise AssertionError("not asked")


@pytest.mark.parametrize("kwargs, label", [
    pytest.param({}, "scripted", id="default-scripted"),
    pytest.param({"writer": fake_writer, "writer_label": "haiku"}, "haiku", id="haiku-wired"),
])
def test_snapshot_names_the_active_writer(tmp_path: Path, kwargs: dict[str, Any], label: str) -> None:
    runtime = TavernRuntime(room(), tmp_path / "save.json", {"typesafe_api_key": None}, **kwargs)
    assert runtime.snapshot()["ai"]["writer"] == label


def test_app_hands_its_writer_to_every_session(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    app = create_app(map_path, tmp_path, {"typesafe_api_key": None}, run_loop=False, writer=fake_writer,
                     writer_label="haiku")
    runtime = app.state.sessions.open("device-test")
    assert (runtime.writer, runtime.snapshot()["ai"]["writer"]) == (fake_writer, "haiku")


@pytest.mark.parametrize("key, label", [
    pytest.param("test-key-not-sent", "haiku", id="claude-key-configured"),
    pytest.param("", "scripted", id="empty-key"),
])
def test_default_app_writes_with_haiku_only_when_keyed(monkeypatch: pytest.MonkeyPatch, key: str,
                                                       label: str) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    snapshot = create_default_app().state.sessions.open("device-test").snapshot()
    assert snapshot["ai"]["writer"] == label
    assert key == "" or key not in json.dumps(snapshot)
