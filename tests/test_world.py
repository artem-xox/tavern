"""Authoritative actions, personal knowledge, and resource accounting."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.body.items import empty_inventory
from tavern.hall.world import create_world, observe_actor, start_action, step_world


def room() -> dict[str, Any]:
    """Create a compact fixture with reachable interaction points."""
    return {
        "width": 8, "height": 6, "tile_size": 32, "blocked": [],
        "objects": [
            {"id": "tap", "kind": "tap", "name": "Beer", "x": 4, "y": 1, "interaction_spots": [[3, 1]], "stock": 2},
            {"id": "chair", "kind": "chair", "name": "Chair", "x": 4, "y": 3, "interaction_spots": [[3, 3]]},
            {"id": "toilet", "kind": "toilet", "name": "Toilet", "x": 7, "y": 4, "interaction_spots": [[6, 4]]},
        ],
        "actors": [
            {"id": "ada", "name": "Ada", "x": 1, "y": 1, "needs": {"thirst": 80, "fatigue": 60, "bladder": 70}},
            {"id": "bea", "name": "Bea", "x": 1, "y": 3},
        ],
    }


def action(verb: str, target_id: str | None = None) -> dict[str, Any]:
    """Create the shared action wire format."""
    return {"id": f"{verb}:{target_id or 'self'}", "verb": verb, "target_id": target_id}


def advance(world: dict[str, Any], seconds: float = 10) -> None:
    """Advance enough fixed ticks to complete a short action."""
    for _ in range(int(seconds * 10)):
        step_world(world, 0.1)


@pytest.mark.parametrize(
    "actors, expected",
    [
        pytest.param([], 0, id="empty-actors"),
        pytest.param([{ "id": "ada", "name": "Ada", "x": 1, "y": 1}], 1, id="single-actor"),
    ],
)
def test_world_is_serializable(actors: list[dict[str, Any]], expected: int) -> None:
    data = room()
    data["actors"] = actors
    world = create_world(data)
    assert len(json.loads(json.dumps(world))["actors"]) == expected


@pytest.mark.parametrize("mutation", [
    pytest.param("duplicate", id="duplicate-actor"),
    pytest.param("blocked", id="actor-inside-object"),
    pytest.param("malformed", id="malformed-needs"),
    pytest.param("bad-spot", id="interaction-inside-object"),
])
def test_world_rejects_invalid_layout(mutation: str) -> None:
    data = room()
    if mutation == "duplicate":
        data["actors"].append(deepcopy(data["actors"][0]))
    elif mutation == "blocked":
        data["actors"][0]["x"] = 4
    elif mutation == "bad-spot":
        data["objects"][0]["interaction_spots"] = [[4, 1]]
    else:
        data["actors"][0]["needs"] = {"thirst": "bad"}
    with pytest.raises(ValueError):
        create_world(data)


def test_demo_layout_contains_three_visitors_and_valid_objects() -> None:
    data = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
    world = create_world(data)
    assert (world["map"]["width"], world["map"]["height"], len(world["actors"])) == (20, 14, 3)


def test_beer_effect_requires_arrival_and_happens_once() -> None:
    world = create_world(room())
    result = start_action(world, "ada", action("take_beer", "tap"))
    assert result == {"accepted": True, "reason": None}
    assert world["actors"][0]["inventory"]["beer"] == 0
    step_world(world, 0.1)
    assert world["map"]["objects"][0]["stock"] == 2
    advance(world)
    assert world["actors"][0]["inventory"]["beer"] == 1
    assert world["map"]["objects"][0]["stock"] == 1
    assert (world["actors"][0]["x"], world["actors"][0]["y"]) == (3, 1)
    assert world["map"]["objects"][0]["reserved_by"] is None
    advance(world)
    assert world["map"]["objects"][0]["stock"] == 1


@pytest.mark.parametrize("verb, target, need", [
    pytest.param("drink", None, "thirst", id="drink-own-beer"),
    pytest.param("rest", "chair", "fatigue", id="rest-at-chair"),
    pytest.param("use_toilet", "toilet", "bladder", id="toilet-at-spot"),
])
def test_completed_actions_relieve_corresponding_need(verb: str, target: str | None, need: str) -> None:
    world = create_world(room())
    actor = world["actors"][0]
    actor["inventory"]["beer"] = 1
    before = actor["needs"][need]
    assert start_action(world, "ada", action(verb, target))["accepted"]
    advance(world)
    assert actor["needs"][need] < before
    if verb == "drink":
        assert actor["inventory"]["beer"] == 0
        assert actor["needs"]["bladder"] > 70


def test_one_actor_reserves_single_capacity_target() -> None:
    world = create_world(room())
    assert start_action(world, "ada", action("use_toilet", "toilet"))["accepted"]
    assert not start_action(world, "bea", action("use_toilet", "toilet"))["accepted"]
    advance(world)
    assert start_action(world, "bea", action("use_toilet", "toilet"))["accepted"]


def test_cancellation_releases_previous_reservation() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    start_action(world, "ada", action("wait"))
    assert world["map"]["objects"][0]["reserved_by"] is None


def test_resource_is_revalidated_after_walk() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    world["map"]["objects"][0]["stock"] = 0
    advance(world)
    assert world["actors"][0]["inventory"]["beer"] == 0
    assert world["map"]["objects"][0]["stock"] == 0
    assert world["map"]["objects"][0]["reserved_by"] is None
    assert any(item["type"] == "action_failed" for item in world["actors"][0]["memory"])


def test_blocked_route_replans_and_unblocking_recovers() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    world["map"]["blocked"] = [[2, 1]]
    advance(world)
    assert world["actors"][0]["inventory"]["beer"] == 1
    assert all((actor["x"], actor["y"]) != (2, 1) for actor in world["actors"])


def test_blocked_spot_fails_visibly_without_effect() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    world["map"]["blocked"] = [[3, 1]]
    advance(world)
    assert world["actors"][0]["inventory"]["beer"] == 0
    assert world["actors"][0]["status"] == "idle"
    assert world["map"]["objects"][0]["reserved_by"] is None


@pytest.mark.parametrize("verb,target", [
    pytest.param("drink", None, id="empty-inventory"),
    pytest.param("take_beer", "missing", id="unknown-target"),
    pytest.param("rest", "tap", id="wrong-kind"),
    pytest.param("invalid", None, id="malformed-action"),
])
def test_invalid_action_fails_without_mutating_inventory(verb: str, target: str | None) -> None:
    world = create_world(room())
    assert not start_action(world, "ada", action(verb, target))["accepted"]
    assert world["actors"][0]["inventory"] == empty_inventory()


def test_individual_observation_does_not_leak_unknown_resources_or_private_state() -> None:
    data = room()
    data["width"] = 20
    data["objects"][0]["x"] = 15
    data["objects"][0]["interaction_spots"] = [[14, 1]]
    world = create_world(data)
    observation = observe_actor(world, "ada")
    assert "tap" not in observation["actor"]["knowledge"]["objects"]
    assert all(item["id"] != "tap" for item in observation["objects"])
    assert "actors" not in observation
    assert "bea" not in json.dumps(observation)


def test_remembered_stock_refreshes_only_on_visibility() -> None:
    world = create_world(room())
    observe_actor(world, "ada")
    actor = world["actors"][0]
    actor["x"], actor["y"] = 0, 5
    world["map"]["objects"][0]["stock"] = 0
    assert observe_actor(world, "ada")["actor"]["knowledge"]["objects"]["tap"]["stock"] == 2
    actor["x"], actor["y"] = 3, 1
    assert observe_actor(world, "ada")["actor"]["knowledge"]["objects"]["tap"]["stock"] == 0


def test_pause_and_speed_control_time() -> None:
    world = create_world(room())
    world["paused"] = True
    step_world(world, 1)
    assert world["time"] == 0
    world["paused"] = False
    world["speed"] = 2
    step_world(world, 1)
    assert world["time"] == 2


def test_exploration_destination_does_not_reserve_another_visitors_cell() -> None:
    world = create_world(room())
    bea = world["actors"][1]
    bea.update(action=action("inspect"), _spot=[1, 1], path=[[1, 2], [1, 1]], status="walking")
    assert start_action(world, "ada", action("take_beer", "tap"))["accepted"]


def test_visitor_can_leave_cell_reserved_by_another_arriving_visitor() -> None:
    world = create_world(room())
    world["actors"][0].update(x=3, y=1)
    assert start_action(world, "bea", action("take_beer", "tap"))["accepted"]
    assert start_action(world, "ada", action("rest", "chair"))["accepted"]


def test_unblocking_waiting_route_allows_completion() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    world["map"]["blocked"] = [[3, 1]]
    advance(world, 1)
    assert world["actors"][0]["status"] == "waiting"
    world["map"]["blocked"] = []
    advance(world)
    assert world["actors"][0]["inventory"]["beer"] == 1


def test_json_round_trip_resumes_action_without_repeating_effects() -> None:
    world = create_world(room())
    start_action(world, "ada", action("take_beer", "tap"))
    advance(world, 1)
    loaded = json.loads(json.dumps(world))
    advance(loaded)
    advance(loaded)
    assert loaded["actors"][0]["inventory"]["beer"] == 1
    assert loaded["map"]["objects"][0]["stock"] == 1
    assert loaded["map"]["objects"][0]["reserved_by"] is None


def test_visitors_wait_and_yield_without_occupying_the_same_cell() -> None:
    world = create_world(room())
    world["actors"][0].update(x=3, y=1)
    start_action(world, "bea", action("take_beer", "tap"))
    for _ in range(100):
        step_world(world, 0.1)
        positions = [(actor["x"], actor["y"]) for actor in world["actors"]]
        assert len(positions) == len(set(positions))
    assert world["actors"][1]["inventory"]["beer"] == 1


def test_wall_hides_objects_until_observed_from_accessible_side() -> None:
    data = room()
    data["blocked"] = [[2, 1]]
    world = create_world(data)
    assert "tap" not in observe_actor(world, "ada")["actor"]["knowledge"]["objects"]
    world["actors"][0].update(x=3, y=1)
    assert observe_actor(world, "ada")["actor"]["knowledge"]["objects"]["tap"]["stock"] == 2


def test_inspection_refreshes_oldest_reachable_memory_before_nearby_known_object() -> None:
    data = room()
    data["width"] = 20
    data["objects"][2].update(x=17, interaction_spots=[[16, 4]])
    world = create_world(data)
    world["time"] = 10
    actor = world["actors"][0]
    actor["knowledge"]["objects"]["toilet"] = {**world["map"]["objects"][2], "last_seen": 0}
    actor["knowledge"]["cells"] = [[x, y] for y in range(6) for x in range(20)]
    observe_actor(world, "ada")
    assert start_action(world, "ada", action("inspect"))["accepted"]
    assert actor["_spot"] == [16, 4]


def test_unreachable_unexplored_cells_do_not_prevent_refreshing_known_empty_tap() -> None:
    data = room()
    data["blocked"] = [[0, 4], [1, 5]]
    world = create_world(data)
    actor = world["actors"][0]
    actor["knowledge"]["cells"] = [[x, y] for y in range(6) for x in range(8) if (x, y) != (0, 5)]
    actor["knowledge"]["objects"] = {"tap": {**world["map"]["objects"][0], "last_seen": 0}}
    assert start_action(world, "ada", action("inspect"))["accepted"]
    assert actor["_spot"] == [3, 1]


def test_visitors_do_not_choose_the_same_inspection_destination() -> None:
    world = create_world(room())
    for actor in world["actors"]:
        actor["knowledge"]["cells"] = [[x, y] for y in range(6) for x in range(8)]
        actor["knowledge"]["objects"] = {"tap": {**world["map"]["objects"][0], "last_seen": 0}}
    assert start_action(world, "ada", action("inspect"))["accepted"]
    assert start_action(world, "bea", action("inspect"))["accepted"]
    assert world["actors"][0]["_spot"] != world["actors"][1]["_spot"]


def corridor(ada_y: int, bea_y: int) -> dict[str, Any]:
    """Build an open room where Ada walks east to the darts while Bea walks west to the tap."""
    return {"width": 10, "height": 5, "blocked": [], "objects": [
        {"id": "tap", "kind": "tap", "x": 0, "y": 2, "interaction_spots": [[1, 2]], "stock": 3},
        {"id": "darts", "kind": "darts", "x": 9, "y": 2, "interaction_spots": [[8, 2]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": ada_y}, {"id": "bea", "name": "Bea", "x": 7, "y": bea_y}]}


@pytest.mark.parametrize("ada_y, bea_y", [
    pytest.param(2, 2, id="head-on-in-the-same-row"),
    pytest.param(2, 1, id="offset-by-one-row"),
    pytest.param(1, 3, id="parallel-rows"),
])
def test_visitors_walking_towards_each_other_get_past(ada_y: int, bea_y: int) -> None:
    world = create_world(corridor(ada_y, bea_y))
    assert start_action(world, "ada", action("play_darts", "darts"))["accepted"]
    assert start_action(world, "bea", action("take_beer", "tap"))["accepted"]
    advance(world, 20)
    assert [(actor["x"], actor["y"], actor["action"]) for actor in world["actors"]] == [(8, 2, None), (1, 2, None)]
    assert world["actors"][1]["inventory"]["beer"] == 1
