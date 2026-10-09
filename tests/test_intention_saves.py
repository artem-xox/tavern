"""Saved evenings keep each guest's intention (schema version 12) and refuse corrupt ones."""

from pathlib import Path
from typing import Any, Callable

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world


def hall() -> dict[str, Any]:
    """A small hall with a door, Ada and Bea."""
    return {"width": 9, "height": 6, "blocked": [], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]}],
        "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}, {"id": "bea", "name": "Bea", "x": 3, "y": 1}]}


def minded() -> dict[str, Any]:
    """Ada has an intention written at 0 s; Bea has none yet."""
    world = create_world(hall())
    world["actors"][0]["intention"] = {"thought": "Warm in here.", "intention": "Find a seat by the fire.",
                                       "goal": None, "written_at": 0.0, "trigger": {"kind": "arrival", "text": "Ada came in",
                                                                      "time": 0.0}}
    return world


def test_new_worlds_are_version_15() -> None:
    assert create_world(hall())["schema_version"] == 16


def test_intentions_survive_save_and_load(tmp_path: Path) -> None:
    world = minded()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def depart(world: dict[str, Any]) -> None:
    """Move Ada to the departed with a malformed intention."""
    ada = world["actors"].pop(0)
    ada["visit"]["left_at"] = 1.0
    ada["intention"]["trigger"] = "arrival"
    world["departed"].append(ada)


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=4), id="version-4-save"),
    pytest.param(lambda world: world["actors"][1].pop("intention"), id="missing-intention"),
    pytest.param(lambda world: world["actors"][0]["intention"].pop("thought"), id="intention-without-thought"),
    pytest.param(lambda world: world["actors"][0]["intention"].update(intention=""), id="empty-intention"),
    pytest.param(lambda world: world["actors"][0]["intention"].update(written_at=-1), id="negative-time"),
    pytest.param(lambda world: world["actors"][0]["intention"]["trigger"].pop("text"), id="trigger-without-text"),
    pytest.param(lambda world: world["actors"][0].update(intention="Find a seat"), id="malformed-intention"),
    pytest.param(depart, id="departed-guest-with-malformed-trigger"),
])
def test_corrupt_intentions_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = minded()
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
