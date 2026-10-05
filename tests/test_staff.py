"""The staff cells behind the bar: what a hall must say about them, and how guests keep out."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.evening.decisions import decision_requests
from tavern.evening.lockstep import Pace, run_evening
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.staff import off_limits
from tavern.hall.world import create_world, start_action, step_world
from tavern.mind.agents import Evaluators
from tavern.mind.intentions import INTENTION_RULES, intention_requests
from tavern.server.controls import forced_action, toggle_block
from staff_hall import HOB, ROOT, cards, hob_of, opened, plan

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
CELLS = [[2, 1], [3, 1], [4, 1], [5, 1]]


def room(**bar: Any) -> dict[str, Any]:
    """The repository's hall with fields of its bar replaced; a value of None removes the field."""
    data = deepcopy(LAYOUT)
    item = next(item for item in data["objects"] if item["id"] == "bar")
    for key, value in bar.items():
        item.pop(key, None) if value is None else item.update({key: value})
    return data


def amended(object_id: str, **fields: Any) -> dict[str, Any]:
    """The repository's hall with fields of one object replaced."""
    data = deepcopy(LAYOUT)
    next(item for item in data["objects"] if item["id"] == object_id).update(fields)
    return data


def guest(actor_id: str, x: int, y: int) -> dict[str, Any]:
    """Describe a visitor standing on a cell."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": x, "y": y}


def hall_with(*actors: dict[str, Any]) -> dict[str, Any]:
    """The repository's hall, without its arrival draws, holding the given visitors."""
    data = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    return create_world({**data, "actors": list(actors)})


def tiny_hall(darts_spot: list[int]) -> dict[str, Any]:
    """A 7×3 hall whose only floor is one corridor, (1, 1) to (5, 1), with a tap and darts below it.

    The tap's spot is (1, 1), and the staff cell (2, 1) is the only one next to the tap. With the darts'
    spot at (3, 1) it lies between the two places; with the darts' spot at (1, 1) it cuts nothing off.
    """
    walls = [[x, 0] for x in range(7)] + [[0, 1], [6, 1], [0, 2], [1, 2], [4, 2], [6, 2]]
    return {"width": 7, "height": 3, "blocked": walls, "objects": [
        {"id": "tap", "kind": "tap", "x": 2, "y": 2, "interaction_spots": [[1, 1]], "stock": 5},
        {"id": "darts", "kind": "darts", "x": 3, "y": 2, "interaction_spots": [darts_spot]},
        {"id": "bar", "kind": "bar", "x": 5, "y": 2, "staff_cells": [[2, 1]], "staff_facing": "south"}]}


def test_the_repository_bar_has_four_staff_cells_and_one_is_next_to_the_tap() -> None:
    bar = next(item for item in create_world(LAYOUT)["map"]["objects"] if item["id"] == "bar")
    assert (bar["staff_cells"], bar["staff_facing"], [5, 1] in bar["staff_cells"]) == (CELLS, "south", True)


@pytest.mark.parametrize("data, message", [
    pytest.param(amended("tap", staff_cells=[[5, 1]], staff_facing="south"), "belong to a bar", id="on-a-tap"),
    pytest.param(room(staff_cells=[]), "nonempty list of cells", id="empty"),
    pytest.param(room(staff_cells=[[5]]), "nonempty list of cells", id="malformed-cell"),
    pytest.param(room(staff_cells=[[4, 1], [4, 1], [5, 1]]), "distinct", id="repeated-cell"),
    pytest.param(room(staff_cells=[[5, 1], [5, 99]]), "inside the hall", id="outside-the-hall"),
    pytest.param(room(staff_cells=[[5, 1], [5, 0]]), "free floor", id="on-a-wall"),
    pytest.param(room(staff_cells=[[5, 1], [5, 2]]), "free floor", id="on-the-bar"),
    pytest.param(room(staff_cells=[[5, 1], [4, 1], [10, 5]]), "free floor", id="on-a-table"),
    pytest.param(room(staff_cells=[[2, 1], [3, 1], [5, 1]]), "one stretch", id="with-a-gap"),
    pytest.param(amended("tap", interaction_spots=[[5, 1]]), "keep off", id="on-the-taps-spot"),
    pytest.param(amended("tap", queue_spots=[[7, 4], [8, 4], [9, 4], [10, 4], [11, 4], [4, 1]]), "keep off",
                 id="on-a-queue-spot"),
    pytest.param(room(staff_cells=[[2, 1], [3, 1], [4, 1]]), "next to a tap", id="no-tap-beside"),
    pytest.param(room(staff_facing=None), "staff_facing", id="no-facing"),
    pytest.param(room(staff_facing="up"), "staff_facing", id="unknown-facing"),
    pytest.param(room(staff_cells=None), "staff_facing", id="facing-without-cells"),
])
def test_a_hall_with_bad_staff_cells_is_refused(data: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_world(data)


def test_staff_cells_that_cut_one_place_off_from_another_are_refused() -> None:
    with pytest.raises(ValueError, match="cut"):
        create_world(tiny_hall([3, 1]))


def test_the_same_hall_opens_once_the_cells_cut_nothing_off() -> None:
    assert create_world(tiny_hall([1, 1]))["map"]["objects"][-1]["staff_cells"] == [[2, 1]]


def test_off_limits_lists_every_staff_cell_to_a_guest() -> None:
    world = hall_with(guest("ada", 1, 4))
    assert sorted(off_limits(world["map"], world["actors"][0])) == [(2, 1), (3, 1), (4, 1), (5, 1)]


def test_a_guest_sent_to_explore_never_heads_for_the_staff_cells() -> None:
    world = hall_with(guest("ada", 2, 2))
    ada = world["actors"][0]
    # The staff cells are the only cells Ada has not seen: nothing else is left to find.
    ada["knowledge"]["cells"] = [[x, y] for x in range(world["map"]["width"]) for y in range(world["map"]["height"])
                                 if [x, y] not in CELLS]
    assert start_action(world, "ada", {"id": "inspect", "verb": "inspect", "target_id": None})["accepted"]
    assert ada["_spot"] not in CELLS


def test_a_walker_cannot_push_an_idle_guest_onto_a_staff_cell() -> None:
    # Ada's only free neighbour is (2, 1), a staff cell: Bob, walking into her cell, must not send her there.
    world = hall_with(guest("ada", 2, 2), guest("dan", 1, 2), guest("bob", 2, 3))
    assert start_action(world, "bob", {"id": "beer", "verb": "take_beer", "target_id": "tap"})["accepted"]
    bob = next(item for item in world["actors"] if item["id"] == "bob")
    bob.update(path=[[2, 2]], status="walking")
    step_world(world, 0.4)
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    assert (ada["x"], ada["y"], ada["action"]) == (2, 2, None)


@pytest.mark.parametrize("cell", [
    pytest.param(cell, id=f"{cell[0]}-{cell[1]}") for cell in CELLS])
def test_the_operator_cannot_block_or_clear_a_cell_behind_the_bar(cell: list[int]) -> None:
    world = hall_with()
    with pytest.raises(ValueError, match="behind the bar"):
        toggle_block(world, LAYOUT["blocked"], {"x": cell[0], "y": cell[1], "blocked": True})


# --- B2: the barkeep on duty -------------------------------------------------------------------------------

def test_the_barkeep_opens_the_evening_behind_the_bar_facing_the_hall() -> None:
    world = opened(HOB)
    hob = hob_of(world)
    assert ((hob["x"], hob["y"], hob["post"], hob["facing"], set(hob["needs"].values()), hob["status"]),
            [item["message"] for item in world["events"] if item["type"] == "on_duty"]) == (
        (5, 1, "bar", "south", {0.0}, "idle"), ["Hob took his place behind the Oak bar"])


def test_guests_have_no_post() -> None:
    assert {item["id"]: item["post"] for item in opened(HOB)["actors"]} == {"hob": "bar", "ada": None, "bea": None}


def test_the_repository_evening_starts_with_hob_cast_from_his_card() -> None:
    data = json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text())
    world = open_evening(LAYOUT, parse_scenario(data, cards("characters"), cards("staff")), seed=1)
    hob = hob_of(world)
    assert (hob["card"]["id"], hob["traits"]["patience"], hob["sprite"], (hob["x"], hob["y"])) == (
        "hob", 0.8, "bartender", (5, 1))


@pytest.mark.parametrize("staff, message", [
    pytest.param({key: value for key, value in HOB.items() if key != "traits"} | {"card": "nobody"},
                 "Unknown character card", id="unknown-card"),
    pytest.param({**HOB, "card": "hob"}, "names the card by ID", id="card-and-traits"),
    pytest.param({**HOB, "id": "ada"}, "unique|repeated|Duplicate", id="id-of-a-guest"),
    pytest.param({key: value for key, value in HOB.items() if key != "post"}, "post", id="no-post"),
    pytest.param({**HOB, "arrives_at": 5}, "unknown", id="unknown-field"),
    pytest.param({**HOB, "post": ""}, "post", id="empty-post"),
])
def test_a_bad_staff_member_is_refused(staff: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_scenario(plan(staff), cards("characters"), cards("staff"))


@pytest.mark.parametrize("staff, message", [
    pytest.param([{**HOB, "post": "tap"}], "bar with staff cells", id="post-is-not-a-bar"),
    pytest.param([{**HOB, "post": "nowhere"}], "bar with staff cells", id="unknown-post"),
    pytest.param([HOB, {**HOB, "id": "pip", "name": "Pip"}], "already", id="two-at-one-bar"),
])
def test_a_post_must_be_a_bar_with_one_member(staff: list[dict[str, Any]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        opened(*staff)


def test_a_bar_without_staff_cells_has_no_post() -> None:
    with pytest.raises(ValueError, match="bar with staff cells"):
        open_evening(room(staff_cells=None, staff_facing=None), parse_scenario(plan(HOB)), seed=1)


def test_over_five_minutes_the_barkeep_decides_nothing_needs_nothing_and_never_leaves_his_cells() -> None:
    world = opened(HOB)
    asked, minded = set(), set()
    for _ in range(600):
        step_world(world, 0.5)
        asked.update(actor_id for actor_id, _ in decision_requests(world, set(), {}))
        minded.update(actor_id for actor_id, _ in intention_requests(world, set(), {}, INTENTION_RULES))
    hob = hob_of(world)
    assert (("hob" in asked, "hob" in minded), set(hob["needs"].values()), [hob["x"], hob["y"]] in CELLS) == (
        (False, True), {0.0}, True)
    assert {"ada", "bea"} <= asked


@pytest.mark.parametrize("command", [
    pytest.param({"id": "wait", "verb": "wait", "target_id": None}, id="wait"),
    pytest.param({"id": "beer", "verb": "take_beer", "target_id": "tap"}, id="take-a-beer"),
])
def test_nothing_starts_an_action_for_the_barkeep(command: dict[str, Any]) -> None:
    world = opened(HOB)
    result = start_action(world, "hob", command)
    assert (result, hob_of(world)["action"]) == ({"accepted": False, "reason": "Hob works behind the bar"}, None)


def test_the_operator_cannot_force_an_action_on_the_barkeep() -> None:
    with pytest.raises(ValueError, match="works behind the bar"):
        forced_action(opened(HOB), {"actor_id": "hob", "action": {"id": "wait", "verb": "wait"}})


def test_the_evening_ends_when_the_last_guest_leaves_although_the_barkeep_stays() -> None:
    world = open_evening(LAYOUT, parse_scenario(plan(HOB, closes_at=150)), seed=1)
    config = {"model": "jev-latest", "timeout": 1.0, "temperature": 0.25, "typesafe_api_key": None}
    evening = asyncio.run(run_evening(world, config, Random(1), Evaluators(never_asked, never_asked),
                                      Pace(step=0.25, model_latency=1.0, time_limit=600.0)))
    assert ([item["id"] for item in world["actors"]], sorted(item["id"] for item in world["departed"]),
            evening.guests, world["time"] < 600.0) == (["hob"], ["ada", "bea"], ["ada", "bea"], True)


def test_a_world_with_the_barkeep_survives_a_save() -> None:
    world = opened(HOB)
    assert parse_world(json.dumps(world)) == json.loads(json.dumps(world))


def twin_of_hob(world: dict[str, Any]) -> None:
    """A second barkeep on the same bar."""
    world["actors"].append({**deepcopy(hob_of(world)), "id": "pip", "x": 4})


def retire(world: dict[str, Any]) -> None:
    """Hob goes home like a guest."""
    hob = hob_of(world)
    world["actors"].remove(hob)
    hob["visit"]["left_at"] = 1.0
    world["departed"].append(hob)


@pytest.mark.parametrize("damage", [
    pytest.param(lambda world: hob_of(world).update(x=2, y=2), id="off-the-staff-cells"),
    pytest.param(twin_of_hob, id="two-at-one-post"),
    pytest.param(retire, id="departed"),
    pytest.param(lambda world: world["actors"][1].update(x=3, y=1), id="a-guest-on-a-staff-cell"),
    pytest.param(lambda world: hob_of(world).pop("post"), id="actor-without-a-post"),
    pytest.param(lambda world: hob_of(world).update(post="tap"), id="post-is-not-a-bar"),
    pytest.param(lambda world: hob_of(world).update(post=7), id="post-is-not-a-string"),
])
def test_a_save_with_a_broken_staff_record_is_refused(damage: Callable[[dict[str, Any]], None]) -> None:
    world = opened(HOB)
    damage(world)
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(json.dumps(world))


async def never_asked(*arguments: Any) -> dict[str, float]:
    """A Jev evaluator that must not be called: the evening is played by the local policy."""
    raise AssertionError("Jev was asked in an offline evening")
