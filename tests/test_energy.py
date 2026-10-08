"""Energy: every activity tires a little, a nap restores it, and sitting alone does not."""

from typing import Any

import pytest

from tavern.body.energy import tire
from tavern.hall.world import create_world, start_action, step_world

START = 50.0


def room() -> dict[str, Any]:
    """A room with a table, a chair and a door; Ada sits in the chair and Hob tends no bar."""
    return {"width": 8, "height": 6, "tile_size": 32, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2},
        {"id": "west", "kind": "chair", "name": "Table · west", "x": 2, "y": 2, "walkable": True,
         "table_id": "table", "interaction_spots": [[2, 2]]},
        {"id": "door", "kind": "door", "name": "Door", "x": 7, "y": 5, "interaction_spots": [[6, 5]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}]}


def doing(verb: str, status: str = "interacting") -> dict[str, Any]:
    """A world in which Ada is part-way through a verb, with a middling energy."""
    world = create_world(room())
    ada = world["actors"][0]
    ada["needs"]["fatigue"] = START
    ada.update(action={"id": verb, "verb": verb, "target_id": None}, status=status)
    return world


def fatigue(world: dict[str, Any]) -> float:
    """Ada's tiredness."""
    return world["actors"][0]["needs"]["fatigue"]


@pytest.mark.parametrize("verb, per_second", [
    pytest.param("take_beer", 0.25, id="fetching-ale"),
    pytest.param("drink", 0.2, id="a-sip-tires-a-little"),
    pytest.param("talk", 0.05, id="chatting"),
    pytest.param("join_conversation", 0.05, id="joining-a-chat"),
    pytest.param("stand_at_bar", 0.075, id="leaning-on-the-bar"),
    pytest.param("play_darts", 0.4, id="darts-tire-most-of-the-pastimes"),
    pytest.param("play_dice", 0.075, id="dice"),
    pytest.param("watch_dice", 0.05, id="watching-dice"),
    pytest.param("watch", 0.05, id="watching-the-fire"),
    pytest.param("use_toilet", 0.25, id="the-wc"),
    pytest.param("inspect", 0.25, id="looking-around"),
    pytest.param("give", 0.25, id="giving"),
    pytest.param("bring_drink", 0.25, id="fetching-for-someone"),
    pytest.param("leave", 0.25, id="going-home"),
    pytest.param("shove", 1.5, id="shoving"),
    pytest.param("start_fight", 2.5, id="fighting"),
    pytest.param("sit", 0.0, id="sitting-costs-nothing"),
    pytest.param("rest", 0.0, id="resting-costs-nothing"),
    pytest.param("wait", 0.0, id="waiting-costs-nothing"),
    pytest.param("doze", -0.75, id="sleep-restores"),
])
def test_an_activity_changes_energy_at_its_own_rate(verb: str, per_second: float) -> None:
    world = doing(verb)
    tire(world, 10.0)
    assert fatigue(world) == pytest.approx(START + 10 * per_second)


@pytest.mark.parametrize("status, per_second", [
    pytest.param("walking", 0.4, id="the-way-to-the-darts-tires-like-the-darts"),
    pytest.param("interacting", 0.4, id="the-darts"),
    pytest.param("waiting", 0.0, id="held-up-on-the-route"),
    pytest.param("queued", 0.0, id="standing-in-line"),
])
def test_only_walking_and_doing_tire(status: str, per_second: float) -> None:
    world = doing("play_darts", status)
    tire(world, 10.0)
    assert fatigue(world) == pytest.approx(START + 10 * per_second)


def test_an_idle_guest_is_not_tired_by_anything() -> None:
    world = create_world(room())
    world["actors"][0]["needs"]["fatigue"] = START
    tire(world, 10.0)
    assert fatigue(world) == START


@pytest.mark.parametrize("start, verb, expected", [
    pytest.param(99.0, "start_fight", 100.0, id="never-above-100"),
    pytest.param(10.0, "doze", 0.0, id="never-below-0"),
])
def test_energy_stays_between_none_and_full(start: float, verb: str, expected: float) -> None:
    world = doing(verb)
    world["actors"][0]["needs"]["fatigue"] = start
    tire(world, 100.0)
    assert fatigue(world) == expected


def test_staff_are_never_tired_by_their_work() -> None:
    world = doing("take_beer")
    world["actors"][0]["post"] = "bar"
    tire(world, 10.0)
    assert fatigue(world) == START


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


@pytest.mark.parametrize("seconds, restored", [
    pytest.param(40.0, 30.0, id="a-whole-nap"),
    pytest.param(20.0, 15.0, id="half-a-nap-restores-half"),
])
def test_a_nap_restores_energy_as_it_goes(seconds: float, restored: float) -> None:
    world = create_world(room())
    ada = world["actors"][0]
    assert start_action(world, "ada", {"id": "sit", "verb": "sit", "target_id": "west"})["accepted"]
    world["rules"]["need_rates"]["fatigue"] = 1e-9
    ada["needs"]["fatigue"] = 80.0
    assert start_action(world, "ada", {"id": "doze", "verb": "doze", "target_id": None})["accepted"]
    advance(world, seconds)
    assert ada["needs"]["fatigue"] == pytest.approx(80.0 - restored, abs=1.0)


@pytest.mark.parametrize("verb, target", [
    pytest.param("sit", "west", id="sitting"),
    pytest.param("rest", "west", id="resting"),
])
def test_sitting_down_no_longer_cures_tiredness(verb: str, target: str) -> None:
    world = create_world(room())
    ada = world["actors"][0]
    ada["needs"]["fatigue"] = 80.0
    assert start_action(world, "ada", {"id": verb, "verb": verb, "target_id": target})["accepted"]
    advance(world, 20.0)
    assert ada["needs"]["fatigue"] >= 80.0
