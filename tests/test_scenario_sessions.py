"""Scenario evenings in saves and sessions: version 2 saves, refused old saves, reset and seeds."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tavern.app import create_default_app
from tavern.server.api import create_app
from tavern.server.runtime import TavernRuntime
from tavern.server.sessions import TavernSessions
from tavern.adapters.persistence import load_world, save_world
from tavern.evening.scenario import Scenario, open_evening, parse_scenario
from tavern.hall.world import step_world

SESSION = "device-first"


def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a door in the bottom wall and a tap."""
    return {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5},
    ]}


def plan(*arrivals: float, seed: int | None = None) -> Scenario:
    """Expect one guest per arrival time, named ada, bea, cid… in order, before closing at 300 s."""
    guests = [{"id": name, "name": name.title(), "color": "#a08060", "sprite": "visitor", "traits": {},
               "arrives_at": time} for name, time in zip(("ada", "bea", "cid", "dan"), arrivals)]
    data = {"guests": guests, "arrival": {"needs": {"thirst": [40, 80]}}, "closes_at": 300}
    return parse_scenario({**data, **({} if seed is None else {"seed": seed})})


def walked_in(*arrivals: float) -> dict[str, Any]:
    """Open the hall for the given arrivals and let ten seconds pass."""
    world = open_evening(hall(), plan(*arrivals), seed=3)
    for _ in range(20):
        step_world(world, 0.5)
    return world


@pytest.mark.parametrize("arrivals", [
    pytest.param((0,), id="empty-expected-list"),
    pytest.param((0, 60), id="single-guest-expected"),
    pytest.param((0, 60, 60), id="duplicate-arrival-times"),
])
def test_scenario_evening_survives_save_and_load(tmp_path: Path, arrivals: tuple[float, ...]) -> None:
    world = walked_in(*arrivals)
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def expected_guest(world: dict[str, Any]) -> dict[str, Any]:
    """Return the first guest still on the way."""
    return world["expected"][0]


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=1), id="version-1-save"),
    pytest.param(lambda world: world.update(expected={}), id="malformed-expected"),
    pytest.param(lambda world: world.update(closes_at="late"), id="malformed-closing-time"),
    pytest.param(lambda world: expected_guest(world).pop("needs"), id="expected-without-needs"),
    pytest.param(lambda world: expected_guest(world)["needs"].update(thirst=150), id="need-out-of-range"),
    pytest.param(lambda world: expected_guest(world)["needs"].update(courage=10), id="unknown-need"),
    pytest.param(lambda world: expected_guest(world).update(sprite=""), id="expected-without-sprite"),
    pytest.param(lambda world: expected_guest(world).update(id="ada"), id="duplicate-of-a-present-guest"),
    pytest.param(lambda world: world["expected"].reverse(), id="out-of-arrival-order"),
    pytest.param(lambda world: expected_guest(world).update(arrives_at=400), id="arrives-after-closing"),
    pytest.param(lambda world: world["actors"][0].pop("sprite"), id="present-guest-without-sprite"),
])
def test_old_or_corrupt_evening_saves_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = walked_in(0, 60, 120)
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


def sessions(tmp_path: Path, scenario: Scenario | None = None) -> TavernSessions:
    """Serve the hall's scenario evenings from per-session files under tmp_path."""
    return TavernSessions(hall(), tmp_path, {"typesafe_api_key": None}, scenario=scenario or plan(0, 60))


def present(world: dict[str, Any]) -> tuple[list[str], list[str]]:
    """List who is inside and who is still expected."""
    return [item["id"] for item in world["actors"]], [item["id"] for item in world["expected"]]


def test_new_session_opens_the_scenarios_evening_at_the_door(tmp_path: Path) -> None:
    world = sessions(tmp_path).open(SESSION).world
    assert (present(world), world["closes_at"], world["tick"], world["paused"]) == ((["ada"], ["bea"]), 300, 0, True)


def version_1_save() -> str:
    """Encode an evening as the previous saved-world format did."""
    return json.dumps({**walked_in(0, 60), "schema_version": 1})


@pytest.mark.parametrize("autosave", [
    pytest.param("", id="empty-autosave"),
    pytest.param("{", id="malformed-autosave"),
    pytest.param(version_1_save(), id="version-1-autosave"),
])
def test_rejected_autosave_opens_a_new_evening_instead_of_failing(tmp_path: Path, autosave: str) -> None:
    (tmp_path / SESSION).mkdir()
    (tmp_path / SESSION / "autosave.json").write_text(autosave)
    world = sessions(tmp_path).open(SESSION).world
    assert (present(world), world["tick"], world["paused"]) == ((["ada"], ["bea"]), 0, True)
    assert any("could not be restored" in event["message"] for event in world["events"])


@pytest.mark.parametrize("seed, same", [
    pytest.param(7, True, id="seeded-scenario-replays"),
    pytest.param(None, False, id="unseeded-sessions-differ"),
])
def test_scenario_seed_opens_the_same_evening_in_every_session(tmp_path: Path, seed: int | None, same: bool) -> None:
    hub = sessions(tmp_path, plan(0, 60, seed=seed))
    worlds = [hub.open(session).world for session in ("device-first", "device-second")]
    thirst = [[item["needs"]["thirst"] for item in [*world["actors"], *world["expected"]]] for world in worlds]
    assert (thirst[0] == thirst[1]) is same


def test_restart_opens_a_new_evening_from_the_scenario(tmp_path: Path) -> None:
    runtime = TavernRuntime(hall(), tmp_path / "save.json", {"temperature": 0}, seed=5, scenario=plan(0, 60))
    first = runtime.world["actors"][0]["needs"]["thirst"]
    runtime.command({"type": "force_action", "actor_id": "ada",
                     "action": {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}})
    for _ in range(140):
        step_world(runtime.world, 0.5)
    arrived = present(runtime.world)
    runtime.command({"type": "reset"})
    world = runtime.world
    assert (arrived, present(world), world["tick"], world["paused"]) == (
        (["ada", "bea"], []), (["ada"], ["bea"]), 0, False)
    assert world["actors"][0]["needs"]["thirst"] != first


def test_default_app_opens_the_repository_scenario() -> None:
    world = create_default_app().state.sessions.open("device-scenario-test").world
    guests = [*world["actors"], *world["expected"]]
    # Hob the barkeep is at his bar before the guests come in, the first ones over the opening minute.
    assert (len(world["actors"]), len(world["expected"])) == (1, 6)
    assert {item["sprite"] for item in guests} == {"edda", "rurik", "toren", "cook", "courier", "visitor",
                                                   "bartender"}


@pytest.mark.parametrize("content", [
    pytest.param("", id="empty-file"),
    pytest.param(json.dumps({"guests": [], "arrival": {"needs": {}}, "closes_at": 300}), id="no-guests"),
])
def test_server_refuses_a_malformed_scenario_file(tmp_path: Path, content: str) -> None:
    (tmp_path / "map.json").write_text(json.dumps(hall()))
    (tmp_path / "scenario.json").write_text(content)
    with pytest.raises(ValueError):
        create_app(tmp_path / "map.json", tmp_path / "saves", {}, run_loop=False,
                   scenario_path=tmp_path / "scenario.json")
