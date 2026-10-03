"""Drunkenness: beers raise it by tolerance, it wears off, its stages change speech, gait and dozing."""

import math
from pathlib import Path
from typing import Any, Callable

import pytest

from tavern.server.runtime import TavernRuntime
from tavern.mind.briefing import brief
from tavern.body.drunkenness import (STAGES, drink_beer, drunk_stage, fight_accuracy, inhibition_modifier, sober_up,
                                speech_instruction)
from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, observe_actor, start_action, step_world

RULES = {"per_beer": 0.2, "per_second": 0.0005, "doze_per_second": 0.01}


@pytest.mark.parametrize("level, stage", [
    pytest.param(0.0, "sober", id="empty-glass-sober"),
    pytest.param(0.19, "sober", id="just-below-tipsy"),
    pytest.param(0.2, "tipsy", id="tipsy"),
    pytest.param(0.449, "tipsy", id="just-below-drunk"),
    pytest.param(0.45, "drunk", id="drunk"),
    pytest.param(0.75, "wasted", id="wasted"),
    pytest.param(1.0, "wasted", id="as-drunk-as-can-be"),
])
def test_drunkenness_falls_into_stages(level: float, stage: str) -> None:
    assert drunk_stage(level).name == stage


@pytest.mark.parametrize("level", [
    pytest.param(-0.01, id="negative"),
    pytest.param(1.01, id="above-one"),
    pytest.param(math.nan, id="not-a-number"),
    pytest.param("merry", id="malformed-text"),
    pytest.param(True, id="malformed-boolean"),
])
def test_impossible_drunkenness_fails_loudly(level: Any) -> None:
    with pytest.raises(ValueError):
        drunk_stage(level)


def test_each_stage_loosens_inhibitions_and_spoils_aim_more() -> None:
    levels = [stage.floor for stage in STAGES]
    inhibitions, accuracy = [inhibition_modifier(level) for level in levels], [fight_accuracy(level) for level in levels]
    assert ([stage.name for stage in STAGES], inhibitions == sorted(set(inhibitions)),
            accuracy == sorted(set(accuracy), reverse=True), inhibitions[0], accuracy[0]) == (
        ["sober", "tipsy", "drunk", "wasted"], True, True, 1.0, 1.0)


@pytest.mark.parametrize("level, words", [
    pytest.param(0.0, "", id="sober-speaks-as-usual"),
    pytest.param(0.3, "louder", id="tipsy-speaks-up"),
    pytest.param(0.6, "slur", id="drunk-slurs"),
    pytest.param(0.9, "ramble", id="wasted-rambles"),
])
def test_speech_follows_the_stage(level: float, words: str) -> None:
    speech = speech_instruction(level)
    assert (words in speech, bool(speech)) == (True, bool(words))


@pytest.mark.parametrize("level, tolerance, expected", [
    pytest.param(0.0, 0.5, 0.2, id="middling-tolerance"),
    pytest.param(0.0, 1.0, 0.1, id="hard-drinker"),
    pytest.param(0.0, 0.0, 0.3, id="lightweight"),
    pytest.param(0.3, 0.5, 0.5, id="second-beer-adds-up"),
    pytest.param(0.9, 0.0, 1.0, id="capped-at-one"),
])
def test_a_beer_raises_drunkenness_by_tolerance(level: float, tolerance: float, expected: float) -> None:
    assert drink_beer(level, tolerance, RULES) == pytest.approx(expected)


@pytest.mark.parametrize("level, seconds, expected", [
    pytest.param(0.5, 0.0, 0.5, id="no-time-no-change"),
    pytest.param(0.5, 100.0, 0.45, id="wears-off-slowly"),
    pytest.param(0.03, 100.0, 0.0, id="never-below-sober"),
    pytest.param(0.0, 50.0, 0.0, id="sober-stays-sober"),
])
def test_drunkenness_wears_off_over_time(level: float, seconds: float, expected: float) -> None:
    assert sober_up(level, seconds, RULES) == pytest.approx(expected)


@pytest.mark.parametrize("change", [
    pytest.param(lambda: drink_beer(0.0, 1.5, RULES), id="tolerance-above-one"),
    pytest.param(lambda: drink_beer(-0.1, 0.5, RULES), id="negative-drunkenness"),
    pytest.param(lambda: sober_up(0.5, -1.0, RULES), id="time-running-backwards"),
])
def test_malformed_drinking_fails_loudly(change: Callable[[], float]) -> None:
    with pytest.raises(ValueError):
        change()


def table_room(**traits: float) -> dict[str, Any]:
    """Build a room with a door and a table; Ada sits at it."""
    return {"width": 8, "height": 6, "tile_size": 32, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2},
        {"id": "west", "kind": "chair", "name": "Table · west", "x": 2, "y": 2, "walkable": True,
         "table_id": "table", "interaction_spots": [[2, 2]]},
        {"id": "door", "kind": "door", "name": "Door", "x": 7, "y": 5, "interaction_spots": [[6, 5]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2, "traits": traits}]}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


@pytest.mark.parametrize("traits, expected", [
    pytest.param({}, 0.2, id="no-tolerance-trait-counts-as-middling"),
    pytest.param({"tolerance": 1.0}, 0.1, id="hard-drinker"),
])
def test_drinking_a_beer_in_the_inn_goes_to_the_head(traits: dict[str, float], expected: float) -> None:
    world = create_world(table_room(**traits))
    ada = world["actors"][0]
    ada["inventory"]["beer"] = 1
    assert start_action(world, "ada", command("drink"))["accepted"]
    advance(world, 3.1)
    assert ada["drunkenness"] == pytest.approx(expected, abs=0.01)


def test_drunkenness_wears_off_in_the_inn() -> None:
    world = create_world(table_room())
    world["actors"][0]["drunkenness"] = 0.5
    advance(world, 100)
    assert world["actors"][0]["drunkenness"] == pytest.approx(0.45)


def sleepy(drunkenness: float, sit: bool) -> dict[str, Any]:
    """Ada, at a given drunkenness, sitting at the table or standing by the door, sure to doze if she can."""
    world = create_world(table_room())
    world["rules"]["drunkenness"]["doze_per_second"] = 1000.0
    world["actors"][0]["drunkenness"] = drunkenness
    if sit:
        assert start_action(world, "ada", command("sit", "west"))["accepted"]
    else:
        world["actors"][0].update(x=5, y=4)
    return world


@pytest.mark.parametrize("drunkenness, sit, dozes", [
    pytest.param(0.9, True, True, id="wasted-at-the-table-dozes"),
    pytest.param(0.6, True, False, id="merely-drunk-stays-awake"),
    pytest.param(0.9, False, False, id="wasted-on-their-feet-stays-awake"),
])
def test_a_wasted_guest_dozes_off_at_the_table(drunkenness: float, sit: bool, dozes: bool) -> None:
    world = sleepy(drunkenness, sit)
    advance(world, 0.2)
    ada = world["actors"][0]
    assert ((ada["action"] or {}).get("verb") == "doze", (ada["emote"] or {}).get("kind") == "sleep",
            ada["seat_id"]) == (dozes, dozes, "west" if sit else None)


def test_a_dozing_guest_wakes_after_a_while() -> None:
    world = sleepy(0.9, sit=True)
    advance(world, 0.2)
    world["rules"]["drunkenness"]["doze_per_second"] = 0.0
    advance(world, world["rules"]["durations"]["doze"] + 1)
    ada = world["actors"][0]
    assert (ada["action"], ada["status"], ada["seat_id"]) == (None, "idle", "west")


def test_the_briefing_says_how_drink_colours_their_speech() -> None:
    world = create_world(table_room())
    world["actors"][0]["drunkenness"] = 0.6
    assert "slur" in brief(observe_actor(world, "ada"), [])["situation"]


def test_the_snapshot_tells_the_client_how_much_to_sway(tmp_path: Path) -> None:
    runtime = TavernRuntime(table_room(), tmp_path / "save.json", {"typesafe_api_key": None})
    runtime.world["actors"][0]["drunkenness"] = 0.9
    mind = runtime.snapshot()["minds"]["ada"]
    assert (mind["drunkenness"], mind["stage"], mind["sway"]) == (0.9, "wasted", drunk_stage(0.9).sway)


def test_drunkenness_survives_save_and_load(tmp_path: Path) -> None:
    world = sleepy(0.9, sit=True)
    advance(world, 0.2)
    save_world(world, tmp_path / "world.json")
    assert load_world(tmp_path / "world.json") == world


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world["actors"][0].update(drunkenness=1.5), id="beyond-wasted"),
    pytest.param(lambda world: world["actors"][0].update(drunkenness="merry"), id="malformed-drunkenness"),
    pytest.param(lambda world: world["actors"][0].pop("drunkenness"), id="missing-drunkenness"),
    pytest.param(lambda world: world["rules"]["drunkenness"].update(per_beer=-0.2), id="negative-rule"),
])
def test_corrupt_drunkenness_is_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = create_world(table_room())
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
