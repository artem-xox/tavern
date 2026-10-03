"""A session's worlds in JSON files: the manual save at a path, the autosave beside it."""

from pathlib import Path
from typing import Any

import pytest

from tavern.persistence import FileStore
from tavern.world import create_world


def world(tick: int = 0) -> dict[str, Any]:
    made = create_world({"width": 4, "height": 4, "tile_size": 32, "blocked": [], "objects": [],
                         "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]})
    made["tick"] = tick
    return made


@pytest.mark.parametrize("slot", [
    pytest.param("manual", id="manual"),
    pytest.param("auto", id="auto"),
])
def test_an_empty_slot_holds_nothing(tmp_path: Path, slot: str) -> None:
    assert FileStore(tmp_path / "save.json").load(slot) is None


def test_slots_keep_their_own_worlds_in_files_beside_each_other(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "session" / "save.json")
    store.save(world(1), "manual")
    store.save(world(2), "auto")
    assert (store.load("manual")["tick"], store.load("auto")["tick"]) == (1, 2)
    assert sorted(path.name for path in (tmp_path / "session").iterdir()) == ["autosave.json", "save.json"]


def test_saving_again_replaces_the_slot(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "save.json")
    store.save(world(1), "manual")
    store.save(world(5), "manual")
    assert store.load("manual")["tick"] == 5


@pytest.mark.parametrize("text", [
    pytest.param("", id="empty-file"),
    pytest.param("{", id="malformed-json"),
    pytest.param('{"schema_version": 1}', id="old-format"),
])
def test_a_damaged_file_fails_loudly(tmp_path: Path, text: str) -> None:
    path = tmp_path / "save.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="Could not load the world"):
        FileStore(path).load("manual")
