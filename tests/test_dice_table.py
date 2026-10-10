"""The dice table in the hall: furniture that guests can see and walk round, but never sit at as at a chair."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.attention import attend
from tavern.hall.memory import record_event
from tavern.hall.world import create_world, observe_actor, start_action
from tavern.mind.agents import build_candidates, build_seat_candidates
from tavern.mind.briefing import brief
from tavern.mind.hall_view import place_words
from tavern.mind.observation import known_objects

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def hall(*extra: dict[str, Any], without: tuple[str, ...] = ()) -> dict[str, Any]:
    """The repository's hall with objects added, and some taken away by ID."""
    room = deepcopy(LAYOUT)
    room["objects"] = [item for item in room["objects"] if item["id"] not in without] + list(extra)
    return room


def dice_table(**fields: Any) -> dict[str, Any]:
    """A dice table of its own in the lower middle of the hall."""
    return {"id": "table-x", "kind": "dice_table", "name": "Spare dice table", "x": 8, "y": 9,
            "interaction_spots": [[8, 10]], **fields}


def seat(kind: str, table_id: str, **fields: Any) -> dict[str, Any]:
    """A seat beside the spare table."""
    return {"id": "seat-x", "kind": kind, "name": "Spare seat", "x": 7, "y": 9, "walkable": True,
            "table_id": table_id, "facing": "east", "interaction_spots": [[7, 9]], **fields}


def objects_of(kind: str) -> list[dict[str, Any]]:
    """The repository hall's objects of a kind, after validation."""
    return [item for item in create_world(LAYOUT)["map"]["objects"] if item["kind"] == kind]


def test_the_hall_has_one_dice_table_with_a_chair_on_each_side_facing_it() -> None:
    [table] = objects_of("dice_table")
    chairs = objects_of("dice_chair")
    sides = sorted((chair["x"] - table["x"], chair["y"] - table["y"], chair["facing"]) for chair in chairs)
    assert [chair["table_id"] for chair in chairs] == [table["id"]] * 2
    assert sides == [(-1, 0, "east"), (1, 0, "west")]


def test_the_dice_table_leaves_room_for_onlookers() -> None:
    [table] = objects_of("dice_table")
    assert len(table["interaction_spots"]) >= 4


def test_a_hall_without_a_dice_table_is_still_a_hall() -> None:
    world = create_world(hall(without=("dice-table", "dice-chair-1", "dice-chair-2")))
    assert {item["kind"] for item in world["map"]["objects"]}.isdisjoint({"dice_table", "dice_chair"})


def test_a_dice_table_is_not_rated_for_appeal_like_a_table_to_sit_at() -> None:
    [table] = objects_of("dice_table")
    assert "appeal" not in table
    assert [("appeal" in chair) for chair in objects_of("dice_chair")] == [False, False]


def test_guests_see_the_dice_table_and_never_offer_its_chairs_to_themselves() -> None:
    world = create_world(LAYOUT)
    observation = {**observe_actor(world, "edda"), "people": []}
    known = {item["id"] for item in known_objects(observation)}
    assert {"dice-table", "dice-chair-1", "dice-chair-2"} <= known
    options = [item for option in build_candidates(observation) for item in option.get("members", [option])]
    assert not [item for item in options if (item["target_id"] or "").startswith("dice-")]
    assert not [item for item in build_seat_candidates(observation) if item["target_id"].startswith("dice-")]


def standing(*cells: tuple[int, int]) -> dict[str, Any]:
    """The hall with Ada, Bea and so on standing on the cells, and no arrival draws."""
    room = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    names = ["ada", "bea", "cid"]
    return create_world({**room, "actors": [{"id": names[i], "name": names[i].capitalize(), "x": x, "y": y}
                                            for i, (x, y) in enumerate(cells)]})


def test_a_guest_by_the_dice_table_is_told_to_stand_near_it_and_not_near_its_chair() -> None:
    world = standing((9, 8))
    assert "standing near the dice table" in brief(observe_actor(world, "ada"), [])["situation"]


def test_a_noise_at_a_dice_chair_is_placed_by_the_dice_table() -> None:
    world = standing((13, 8), (9, 8))
    record_event(world, world["actors"][1], "quarrel", "Bea and Cid quarreled about dice")
    attend(world)
    heard = [item["message"] for item in world["actors"][0]["memory"] if item["type"] in ("interrupted", "alerted")]
    assert heard and all("near the Dice table:" in message for message in heard)


def test_the_dice_table_is_named_as_a_place() -> None:
    [table] = objects_of("dice_table")
    assert place_words(table) == "the dice table"


@pytest.mark.parametrize("verb", [
    pytest.param("sit", id="sit"),
    pytest.param("rest", id="rest"),
])
def test_nobody_sits_or_rests_on_a_dice_chair(verb: str) -> None:
    world = create_world(LAYOUT)
    result = start_action(world, "edda", {"id": f"{verb}:dice-chair-1", "verb": verb, "target_id": "dice-chair-1"})
    assert result == {"accepted": False, "reason": "Target does not support this action"}


def test_a_world_with_a_dice_table_survives_a_save() -> None:
    world = create_world(LAYOUT)
    assert parse_world(json.dumps(world)) == world


@pytest.mark.parametrize("extra, message", [
    pytest.param([dice_table(), seat("dice_chair", "table-x")], None, id="a-spare-table-and-seat-are-fine"),
    pytest.param([seat("dice_chair", "table-1")], "dice table", id="dice-chair-at-a-regular-table"),
    pytest.param([dice_table(), seat("chair", "table-x")], "regular table", id="chair-at-a-dice-table"),
    pytest.param([dice_table(walkable=True)], "Only seats", id="walkable-dice-table"),
    pytest.param([dice_table(interaction_spots=[])], "interaction spot", id="dice-table-without-spots"),
    pytest.param([seat("dice_chair", "nowhere")], "existing table", id="dice-chair-at-no-table"),
])
def test_the_map_checks_dice_furniture(extra: list[dict[str, Any]], message: str | None) -> None:
    if message is None:
        create_world(hall(*extra))
        return
    with pytest.raises(ValueError, match=message):
        create_world(hall(*extra))
