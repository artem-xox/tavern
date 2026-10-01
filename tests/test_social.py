"""Seated tavern life, shared conversations, and solid furniture footprints."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.agents import build_candidates, choose_action
from tavern.app import TavernRuntime
from tavern.persistence import load_world, save_world
from tavern.world import create_world, observe_actor, start_action, step_world


def common_room() -> dict[str, Any]:
    """Build two seats at a shared table and a separate darts corner."""
    return {
        "width": 12, "height": 8, "blocked": [], "objects": [
            {"id": "table", "kind": "table", "x": 4, "y": 3, "width": 2, "height": 1},
            {"id": "left", "kind": "chair", "x": 3, "y": 3, "walkable": True,
             "table_id": "table", "interaction_spots": [[3, 3]]},
            {"id": "right", "kind": "chair", "x": 6, "y": 3, "walkable": True,
             "table_id": "table", "interaction_spots": [[6, 3]]},
            {"id": "tap", "kind": "tap", "x": 2, "y": 1,
             "interaction_spots": [[2, 2]], "stock": 5},
            {"id": "bar", "kind": "bar", "x": 7, "y": 1, "width": 4, "height": 1},
            {"id": "darts", "kind": "darts", "x": 10, "y": 5,
             "interaction_spots": [[9, 5]]},
        ], "actors": [
            {"id": "ada", "name": "Ada", "x": 3, "y": 3,
             "needs": {"social": 80, "boredom": 70}},
            {"id": "bea", "name": "Bea", "x": 6, "y": 3,
             "needs": {"social": 85}},
        ],
    }


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": f"{verb}:{target or 'self'}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance physical state without requesting decisions."""
    for _ in range(int(seconds * 10)):
        step_world(world, 0.1)


def seated_world() -> dict[str, Any]:
    """Seat both visitors before testing shared interactions."""
    world = create_world(common_room())
    for actor_id, seat in (("ada", "left"), ("bea", "right")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 20)
    return world


def test_seat_is_occupied_while_drinking_and_released_when_leaving() -> None:
    world = seated_world()
    actor = world["actors"][0]
    seat = next(item for item in world["map"]["objects"] if item["id"] == "left")
    assert actor["seat_id"] == "left"
    assert not start_action(world, "bea", command("sit", "left"))["accepted"]
    actor["inventory"]["beer"] = 1
    assert start_action(world, "ada", command("drink"))["accepted"]
    advance(world, 5)
    assert (actor["seat_id"], seat["reserved_by"], actor["inventory"]["beer"]) == ("left", "ada", 0)
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    assert (actor["seat_id"], seat["reserved_by"]) == (None, None)


def test_conversation_has_effects_and_memories_for_both_visitors() -> None:
    world = seated_world()
    before = [actor["needs"]["social"] for actor in world["actors"]]
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 10)
    for actor, previous in zip(world["actors"], before):
        assert actor["needs"]["social"] < previous
        assert any(event["type"] == "conversation" for event in actor["memory"])
        assert actor["seat_id"] is not None


def test_departing_partner_cancels_conversation_without_social_effect() -> None:
    world = seated_world()
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    before = world["actors"][0]["needs"]["social"]
    assert start_action(world, "bea", command("take_beer", "tap"))["accepted"]
    advance(world, 1)
    assert world["actors"][0]["needs"]["social"] >= before
    assert not any(event["type"] == "conversation" for event in world["events"])


@pytest.mark.parametrize("target", [
    pytest.param(None, id="empty-target"),
    pytest.param("ada", id="self-target"),
    pytest.param("missing", id="unknown-person"),
    pytest.param([], id="malformed-target"),
])
def test_invalid_conversation_target_is_rejected(target: Any) -> None:
    world = seated_world()
    assert not start_action(world, "ada", command("talk", target))["accepted"]


def test_only_one_conversation_can_involve_a_visitor() -> None:
    world = seated_world()
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    assert not start_action(world, "bea", command("talk", "ada"))["accepted"]


def test_darts_requires_arrival_and_relaxes_boredom() -> None:
    world = create_world(common_room())
    actor = world["actors"][0]
    before = actor["needs"]["boredom"]
    assert start_action(world, "ada", command("play_darts", "darts"))["accepted"]
    step_world(world, 0.1)
    assert actor["needs"]["boredom"] >= before
    advance(world, 25)
    assert (actor["x"], actor["y"]) == (9, 5)
    assert actor["needs"]["boredom"] < before


def test_bar_footprint_cannot_be_crossed() -> None:
    data = common_room()
    data["actors"][0].update(x=6, y=1)
    world = create_world(data)
    assert start_action(world, "ada", command("play_darts", "darts"))["accepted"]
    assert not any(y == 1 and 7 <= x <= 10 for x, y in world["actors"][0]["path"])


@pytest.mark.parametrize("mutation", [
    pytest.param("overlap", id="duplicate-footprint-cell"),
    pytest.param("outside", id="footprint-outside-room"),
    pytest.param("zero", id="empty-footprint"),
    pytest.param("malformed", id="malformed-size"),
])
def test_bad_furniture_footprints_fail_validation(mutation: str) -> None:
    data = common_room()
    bar = data["objects"][4]
    if mutation == "overlap":
        bar.update(x=4, y=3)
    elif mutation == "outside":
        bar["x"] = 11
    elif mutation == "zero":
        bar["width"] = 0
    else:
        bar["width"] = "four"
    with pytest.raises(ValueError):
        create_world(data)


def test_observation_exposes_visible_company_without_private_state() -> None:
    world = seated_world()
    view = observe_actor(world, "ada")
    assert [item["id"] for item in view["visitors"]] == ["bea"]
    assert not {"needs", "memory", "inventory", "traits", "knowledge"} & view["visitors"][0].keys()
    world["map"]["blocked"] = [[7, y] for y in range(8)]
    world["actors"][1].update(x=9, y=3, seat_id=None)
    assert observe_actor(world, "ada")["visitors"] == []


def test_new_actions_are_generated_from_personal_observation() -> None:
    world = seated_world()
    view = observe_actor(world, "ada")
    ids = {item["id"] for item in build_candidates(view)}
    assert {"sit:left", "talk:bea"} <= ids
    assert "sit:right" not in ids
    assert not any(item["target_id"] in {"table", "bar"} for item in build_candidates(view))


@pytest.mark.parametrize("visitors,expected", [
    pytest.param([], 0, id="empty-company"),
    pytest.param([{"id": "bea", "seat_id": "right", "table_id": "table", "available": True}], 1, id="one-neighbor"),
    pytest.param([{"id": "bea", "seat_id": "right", "table_id": "table", "available": True}] * 2, 1, id="duplicate-neighbor"),
])
def test_social_candidates_deduplicate_visible_neighbors(visitors: list[dict[str, Any]], expected: int) -> None:
    view = observe_actor(seated_world(), "ada")
    view["visitors"] = visitors
    assert sum(item["verb"] == "talk" for item in build_candidates(view)) == expected


def test_malformed_visible_visitor_fails_loudly() -> None:
    view = observe_actor(seated_world(), "ada")
    view["visitors"] = [{"id": []}]
    with pytest.raises(ValueError):
        build_candidates(view)


def test_seated_social_need_makes_local_policy_choose_company() -> None:
    view = observe_actor(seated_world(), "ada")
    view["actor"]["needs"].update(thirst=0, fatigue=0, bladder=0, social=100, boredom=0)
    result = asyncio.run(choose_action(view, {"temperature": 0}, Random(1)))
    assert result["action"]["id"] == "talk:bea"


def test_seated_conversation_survives_save_load(tmp_path: Path) -> None:
    world = seated_world()
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 2)
    path = tmp_path / "social.json"
    save_world(world, path)
    restored = load_world(path)
    assert restored == world
    advance(restored, 10)
    assert any(event["type"] == "conversation" for event in restored["actors"][1]["memory"])


def test_saved_invalid_seat_is_rejected(tmp_path: Path) -> None:
    world = deepcopy(seated_world())
    world["actors"][0]["seat_id"] = "missing"
    path = tmp_path / "bad-seat.json"
    save_world(world, path)
    with pytest.raises(ValueError):
        load_world(path)


def test_incoming_conversation_keeps_partner_at_table(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = TavernRuntime(common_room(), tmp_path / "world.json", {"temperature": 0})
        runtime.world = seated_world()
        start_action(runtime.world, "ada", command("talk", "bea"))
        runtime.advance(0.1)
        await asyncio.sleep(0)
        assert "bea" not in runtime.pending
        await runtime.close()
    asyncio.run(run())


def test_late_partner_decision_does_not_interrupt_conversation(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = TavernRuntime(common_room(), tmp_path / "world.json", {"temperature": 0})
        runtime.world = seated_world()
        task = asyncio.create_task(asyncio.sleep(0, result={
            "action": command("play_darts", "darts"), "source": "local", "scores": {}, "error": None}))
        await task
        runtime.pending["bea"] = (task, 0)
        start_action(runtime.world, "ada", command("talk", "bea"))
        runtime.advance(0.1)
        assert runtime.world["actors"][1]["seat_id"] == "right"
        await runtime.close()
    asyncio.run(run())


def test_obstacle_editor_protects_entire_counter(tmp_path: Path) -> None:
    runtime = TavernRuntime(common_room(), tmp_path / "world.json", {"temperature": 0})
    with pytest.raises(ValueError, match="Furniture"):
        runtime.command({"type": "block", "x": 9, "y": 1, "blocked": True})


def test_common_table_has_a_view_of_the_beer_tap() -> None:
    data = json.loads((Path(__file__).parents[1] / "data/tavern.json").read_text())
    world = create_world(data)
    assert start_action(world, "mara", command("sit", "chair-1"))["accepted"]
    advance(world, 20)
    assert "tap" in {item["id"] for item in observe_actor(world, "mara")["objects"]}


def test_conversation_can_share_a_known_beer_location() -> None:
    world = seated_world()
    assert "tap" not in world["actors"][1]["knowledge"]["objects"]
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 10)
    remembered = world["actors"][1]["knowledge"]["objects"]["tap"]
    assert (remembered["x"], remembered["y"], remembered["heard_from"]) == (2, 1, "ada")
