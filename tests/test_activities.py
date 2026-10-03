"""The activity table as the client sees it: names, statuses, poses, and targets per verb."""

from pathlib import Path
from typing import Any

import pytest

from tavern.server.runtime import TavernRuntime


def room() -> dict[str, Any]:
    return {"width": 6, "height": 4, "tile_size": 32, "blocked": [], "objects": [],
            "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 1}]}


def client_activities(tmp_path: Path) -> dict[str, Any]:
    runtime = TavernRuntime(room(), tmp_path / "save.json", {"typesafe_api_key": None})
    return runtime.snapshot()["activities"]


def test_snapshot_offers_every_world_verb_but_not_decision_steps(tmp_path: Path) -> None:
    activities = client_activities(tmp_path)
    world_verbs = set(TavernRuntime(room(), tmp_path / "save.json", {}).world["rules"]["durations"])
    assert set(activities) == world_verbs
    assert "seating" not in activities


@pytest.mark.parametrize(("verb", "expected"), [
    pytest.param("take_beer", {"label": "Get a beer", "status": "getting ale", "pose": "TakeBeer",
                               "target_kinds": ["tap"], "partner": False}, id="object-target"),
    pytest.param("watch", {"label": "Watch the fire or the view", "status": "at the window", "pose": None,
                           "target_kinds": ["window", "fireplace"], "partner": False}, id="several-kinds"),
    pytest.param("talk", {"label": "Chat with a neighbor", "status": "chatting", "pose": "Talking",
                          "target_kinds": [], "partner": True}, id="person-target"),
    pytest.param("rest", {"label": "Rest", "status": None, "pose": "Seated",
                          "target_kinds": ["chair"], "partner": False}, id="no-status"),
    pytest.param("wait", {"label": "Wait a little", "status": None, "pose": None,
                          "target_kinds": [], "partner": False}, id="no-target"),
])
def test_snapshot_describes_a_verb_for_the_client(tmp_path: Path, verb: str, expected: dict[str, Any]) -> None:
    assert client_activities(tmp_path)[verb] == expected
