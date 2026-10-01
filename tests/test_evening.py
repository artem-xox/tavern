"""An evening at the inn: arrival, seat appeal, own seats, grievances and departures."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from tavern.app import TavernRuntime, create_app
from tavern.persistence import load_world, save_world
from tavern.world import create_world, observe_actor, observe_people, start_action, step_world


def table(table_id: str, x: int, y: int) -> list[dict[str, Any]]:
    """Build a one-cell table with a chair on each side."""
    def chair(side: str, dx: int) -> dict[str, Any]:
        return {"id": f"{table_id}-{side}", "kind": "chair", "name": f"{table_id} · {side}",
                "x": x + dx, "y": y, "walkable": True, "table_id": table_id,
                "interaction_spots": [[x + dx, y]]}
    return [{"id": table_id, "kind": "table", "name": f"{table_id.title()} table", "x": x, "y": y},
            chair("west", -1), chair("east", 1)]


def inn() -> dict[str, Any]:
    """Build a 14×9 room: a door below, a walled WC, a tap, a fireplace and two tables."""
    walls = [[11, y] for y in range(5)] + [[x, 8] for x in range(14) if x != 5]
    return {
        "width": 14, "height": 9, "blocked": walls, "objects": [
            {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 8,
             "interaction_spots": [[5, 7]]},
            {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0,
             "interaction_spots": [[1, 1]], "stock": 5},
            {"id": "toilet", "kind": "toilet", "name": "WC", "x": 12, "y": 1,
             "interaction_spots": [[12, 2]]},
            {"id": "hearth", "kind": "fireplace", "name": "Fireplace", "x": 9, "y": 0,
             "appeal": 0.6, "reach": 3},
            *table("warm", 9, 2), *table("plain", 3, 4),
        ],
        "actors": [{"id": "ada", "name": "Ada", "x": 4, "y": 7},
                   {"id": "bea", "name": "Bea", "x": 6, "y": 7}],
    }


def source(kind: str, x: int, y: int, appeal: float, reach: int) -> dict[str, Any]:
    """Describe a window or fireplace that makes nearby tables appealing."""
    return {"id": f"{kind}-{x}-{y}", "kind": kind, "name": kind.title(), "x": x, "y": y,
            "appeal": appeal, "reach": reach}


def appeal_room(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an empty room around one table at (5, 2) with the given comfort sources."""
    return {"width": 10, "height": 6, "blocked": [], "actors": [],
            "objects": [*table("solo", 5, 2), *sources]}


def command(verb: str, target: Any = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance physical state without requesting decisions."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def visitor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a present or departed visitor."""
    return next(item for item in [*world["actors"], *world["departed"]] if item["id"] == actor_id)


def furniture(world: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    """Find an object on the map."""
    return next(item for item in world["map"]["objects"] if item["id"] == object_id)


def seated_inn() -> dict[str, Any]:
    """Seat Ada and Bea opposite each other at the warm table."""
    world = create_world(inn())
    for actor_id, seat in (("ada", "warm-west"), ("bea", "warm-east")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 20)
    return world


def evening() -> dict[str, Any]:
    """Play a short evening: Bea takes Ada's seat, then Ada walks out."""
    world = create_world(inn())
    assert start_action(world, "ada", command("sit", "warm-west"))["accepted"]
    advance(world, 20)
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    assert start_action(world, "bea", command("sit", "warm-west"))["accepted"]
    advance(world, 20)
    assert start_action(world, "ada", command("leave", "door"))["accepted"]
    advance(world, 10)
    return world


@pytest.mark.parametrize("ranges", [
    pytest.param({}, id="empty-ranges"),
    pytest.param({"thirst": [55, 90]}, id="single-need"),
    pytest.param({"thirst": [40, 60], "fatigue": [40, 60]}, id="duplicate-ranges"),
    pytest.param({"bladder": [10, 10]}, id="fixed-value"),
])
def test_arriving_needs_are_drawn_from_their_ranges(ranges: dict[str, list[int]]) -> None:
    data = inn()
    data["arrival"] = {"needs": ranges}
    actors = create_world(data, seed=7)["actors"]
    inside = [low <= actor["needs"][need] <= high
              for actor in actors for need, (low, high) in ranges.items()]
    untouched = [actor["needs"][need] for actor in actors
                 for need in sorted(actor["needs"].keys() - ranges.keys())]
    assert inside == [True] * len(inside)
    assert untouched == [30] * len(untouched)


@pytest.mark.parametrize("arrival", [
    pytest.param({"needs": {"thirst": [90, 50]}}, id="reversed-range"),
    pytest.param({"needs": {"thirst": [-5, 50]}}, id="below-the-scale"),
    pytest.param({"needs": {"courage": [10, 20]}}, id="unknown-need"),
    pytest.param({"needs": {"thirst": [50]}}, id="incomplete-range"),
    pytest.param({"needs": {"thirst": "high"}}, id="malformed-range"),
    pytest.param({"needs": []}, id="malformed-needs"),
    pytest.param([], id="malformed-arrival"),
])
def test_malformed_arrival_fails_loudly(arrival: Any) -> None:
    data = inn()
    data["arrival"] = arrival
    with pytest.raises(ValueError):
        create_world(data)


def test_each_evening_seed_draws_its_own_reproducible_needs() -> None:
    data = inn()
    data["arrival"] = {"needs": {"thirst": [0, 100]}}
    thirst = [[actor["needs"]["thirst"] for actor in create_world(data, seed)["actors"]]
              for seed in (1, 1, 2)]
    assert thirst[0] == thirst[1]
    assert thirst[0] != thirst[2]


@pytest.mark.parametrize("arrival, expected", [
    pytest.param(None, {"door", "plain", "plain-west", "plain-east"}, id="no-arrival-keeps-near-sight"),
    pytest.param({"needs": {}}, {"door", "tap", "hearth", "warm", "warm-west", "warm-east",
                                 "plain", "plain-west", "plain-east"}, id="arrival-glances-around-the-hall"),
])
def test_arriving_visitors_look_around_the_hall_but_not_behind_walls(
        arrival: dict[str, Any] | None, expected: set[str]) -> None:
    data = inn()
    if arrival is not None:
        data["arrival"] = arrival
    world = create_world(data)
    assert set(visitor(world, "ada")["knowledge"]["objects"]) == expected


@pytest.mark.parametrize("sources, appeal, comforts", [
    pytest.param([], 0.0, [], id="empty-plain-corner"),
    pytest.param([source("window", 5, 0, 0.3, 3)], 0.3, ["window"], id="single-window-two-cells-away"),
    pytest.param([source("window", 4, 0, 0.3, 3), source("window", 6, 0, 0.3, 3)], 0.6, ["window"],
                 id="duplicate-windows-add-up"),
    pytest.param([source("window", 0, 5, 0.3, 3)], 0.0, [], id="window-out-of-reach"),
    pytest.param([source("window", 2, 0, 0.3, 3)], 0.0, [], id="diagonal-beyond-straight-line-reach"),
    pytest.param([source("fireplace", 5, 1, 1.0, 2), source("window", 4, 0, 0.3, 3)], 1.0,
                 ["fireplace", "window"], id="capped-at-one"),
])
def test_seat_appeal_comes_from_nearby_windows_and_fireplace(
        sources: list[dict[str, Any]], appeal: float, comforts: list[str]) -> None:
    world = create_world(appeal_room(sources))
    seats = [furniture(world, object_id) for object_id in ("solo", "solo-west", "solo-east")]
    assert [item["appeal"] for item in seats] == pytest.approx([appeal] * 3)
    assert [item["comforts"] for item in seats] == [comforts] * 3


@pytest.mark.parametrize("field, value", [
    pytest.param("appeal", 1.5, id="appeal-above-one"),
    pytest.param("appeal", "cosy", id="malformed-appeal"),
    pytest.param("reach", 0, id="empty-reach"),
    pytest.param("reach", 2.5, id="fractional-reach"),
])
def test_malformed_comfort_source_fails_loudly(field: str, value: Any) -> None:
    window = source("window", 5, 0, 0.3, 3)
    window[field] = value
    with pytest.raises(ValueError):
        create_world(appeal_room([window]))


def test_leaving_visitor_walks_out_and_stays_inspectable() -> None:
    world = create_world(inn())
    assert start_action(world, "ada", command("leave", "door"))["accepted"]
    advance(world, 0.2)
    assert [actor["id"] for actor in world["actors"]] == ["ada", "bea"]
    advance(world, 3)
    assert [actor["id"] for actor in world["actors"]] == ["bea"]
    assert [actor["id"] for actor in world["departed"]] == ["ada"]
    assert 1.0 < visitor(world, "ada")["visit"]["left_at"] < 3.2
    assert world["events"][-1]["type"] == "departure"


def test_departure_frees_the_seat_and_removes_the_visitor_from_view() -> None:
    world = seated_inn()
    assert start_action(world, "ada", command("leave", "door"))["accepted"]
    advance(world, 6)
    assert furniture(world, "warm-west")["reserved_by"] is None
    assert observe_actor(world, "bea")["visitors"] == []


@pytest.mark.parametrize("target", [
    pytest.param(None, id="empty-target"),
    pytest.param("plain-west", id="chair-is-not-a-way-out"),
    pytest.param("missing", id="unknown-door"),
    pytest.param(["door"], id="malformed-target"),
])
def test_leaving_requires_the_door(target: Any) -> None:
    world = create_world(inn())
    assert not start_action(world, "ada", command("leave", target))["accepted"]
    advance(world, 3)
    assert world["departed"] == []


@pytest.mark.parametrize("walled, expected", [
    pytest.param(False, ["bea"], id="across-the-hall"),
    pytest.param(True, [], id="behind-a-wall"),
])
def test_seated_company_is_seen_across_the_hall_but_not_through_walls(walled: bool, expected: list[str]) -> None:
    world = create_world(inn())
    assert start_action(world, "bea", command("sit", "warm-east"))["accepted"]
    advance(world, 5)
    if walled:
        world["map"]["blocked"].extend([x, 5] for x in range(11))
    assert [item["id"] for item in observe_actor(world, "ada")["visitors"]] == expected


@pytest.mark.parametrize("trouble, field, learned", [
    pytest.param("busy", "reserved_by", "bea", id="someone-else-at-the-tap"),
    pytest.param("dry", "stock", 0, id="the-beer-ran-out"),
])
def test_refused_visitor_learns_why_from_afar(trouble: str, field: str, learned: Any) -> None:
    data = inn()
    data["arrival"] = {"needs": {}}
    world = create_world(data)
    if trouble == "busy":
        assert start_action(world, "bea", command("take_beer", "tap"))["accepted"]
    else:
        furniture(world, "tap")["stock"] = 0
    assert not start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    assert visitor(world, "ada")["knowledge"]["objects"]["tap"][field] == learned


@pytest.mark.parametrize("walled, expected", [
    pytest.param(False, [("bea", None, "take_beer", "Tap")], id="someone-fetching-ale-in-sight"),
    pytest.param(True, [], id="nobody-seen-through-a-wall"),
])
def test_visitors_see_what_others_are_doing(walled: bool, expected: list[tuple[Any, ...]]) -> None:
    world = create_world(inn())
    assert start_action(world, "bea", command("take_beer", "tap"))["accepted"]
    advance(world, 0.5)
    if walled:
        world["map"]["blocked"].extend([x, 5] for x in range(11))
        visitor(world, "ada").update(x=2, y=3)
    people = observe_people(world, "ada")
    assert [(item["id"], item["seat_id"], item["doing"], item["target"]) for item in people] == expected
    assert observe_actor(world, "ada")["time"] == pytest.approx(world["time"])


def test_first_seat_becomes_the_visitors_own_for_the_visit() -> None:
    world = create_world(inn())
    assert start_action(world, "ada", command("sit", "warm-west"))["accepted"]
    advance(world, 20)
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    advance(world, 1)
    ada = visitor(world, "ada")
    assert (ada["seat_id"], ada["favorite_seat_id"]) == (None, "warm-west")


@pytest.mark.parametrize("sitter, grievances", [
    pytest.param("ada", [], id="owner-returns-to-own-seat"),
    pytest.param("bea", ["Bea took my seat (warm · west)"], id="someone-else-takes-it"),
])
def test_taking_someones_seat_aggrieves_its_owner(sitter: str, grievances: list[str]) -> None:
    world = create_world(inn())
    assert start_action(world, "ada", command("sit", "warm-west"))["accepted"]
    advance(world, 20)
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    advance(world, 1)
    assert start_action(world, sitter, command("sit", "warm-west"))["accepted"]
    advance(world, 20)
    ada = visitor(world, "ada")
    assert ada["visit"]["grievances"] == grievances
    assert sum(event["type"] == "seat_taken" for event in ada["memory"]) == len(grievances)
    assert visitor(world, sitter)["favorite_seat_id"] == "warm-west"


def test_visit_keeps_count_of_time_and_beers() -> None:
    world = create_world(inn())
    ada = visitor(world, "ada")
    ada["inventory"]["beer"] = 2
    for _ in range(2):
        assert start_action(world, "ada", command("drink"))["accepted"]
        advance(world, 4)
    assert ada["visit"]["beers"] == 2
    assert ada["visit"]["seconds"] == pytest.approx(world["time"])


@pytest.mark.parametrize("beers, patience, outcome", [
    pytest.param(0, 0.0, "conversation", id="sober-impatient-pair-stays-friendly"),
    pytest.param(3, 0.0, "quarrel", id="tipsy-impatient-pair-quarrels"),
    pytest.param(3, 1.0, "conversation", id="tipsy-patient-pair-stays-friendly"),
])
def test_ale_and_impatience_turn_talk_into_quarrels(beers: int, patience: float, outcome: str) -> None:
    world = seated_inn()
    world["rules"].update(quarrel_per_beer=1.0, quarrel_max=1.0)
    for actor in world["actors"]:
        actor["visit"]["beers"] = beers
        actor["traits"]["patience"] = patience
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 10)
    assert {event["type"] for event in world["events"]} & {"conversation", "quarrel"} == {outcome}


def test_quarrel_aggrieves_both_and_leaves_them_lonely() -> None:
    world = seated_inn()
    world["rules"].update(quarrel_per_beer=1.0, quarrel_max=1.0)
    for actor in world["actors"]:
        actor["visit"]["beers"] = 3
        actor["traits"]["patience"] = 0.0
    before = [actor["needs"]["social"] for actor in world["actors"]]
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 10)
    after = [actor["needs"]["social"] for actor in world["actors"]]
    assert [len(actor["visit"]["grievances"]) for actor in world["actors"]] == [1, 1]
    assert [later >= earlier for earlier, later in zip(before, after)] == [True, True]
    assert visitor(world, "ada")["visit"]["grievances"][0].startswith("Quarreled with Bea")


def watchable_inn() -> dict[str, Any]:
    """Give the inn a window and a spot before the fireplace, so both can be watched."""
    data = inn()
    hearth = next(item for item in data["objects"] if item["id"] == "hearth")
    hearth["interaction_spots"] = [[9, 1]]
    data["objects"].append({**source("window", 0, 6, 0.3, 3), "id": "window", "interaction_spots": [[1, 6]]})
    return data


@pytest.mark.parametrize("target", [
    pytest.param("hearth", id="fireplace"),
    pytest.param("window", id="window"),
])
def test_watching_the_fire_or_the_view_eases_boredom(target: str) -> None:
    world = create_world(watchable_inn())
    ada = visitor(world, "ada")
    ada["needs"]["boredom"] = 80
    assert start_action(world, "ada", command("watch", target))["accepted"]
    step_world(world, 0.1)
    assert ada["needs"]["boredom"] >= 80
    advance(world, 15)
    assert ada["needs"]["boredom"] < 50
    assert [ada["x"], ada["y"]] in furniture(world, target)["interaction_spots"]


@pytest.mark.parametrize("target, busy", [
    pytest.param(None, False, id="empty-target"),
    pytest.param("tap", False, id="a-tap-is-no-view"),
    pytest.param("hearth", True, id="duplicate-watcher"),
    pytest.param(["hearth"], False, id="malformed-target"),
])
def test_watching_needs_a_free_window_or_fireplace(target: Any, busy: bool) -> None:
    world = create_world(watchable_inn())
    if busy:
        assert start_action(world, "bea", command("watch", "hearth"))["accepted"]
    assert not start_action(world, "ada", command("watch", target))["accepted"]


def test_evening_state_survives_save_and_load(tmp_path: Path) -> None:
    world = evening()
    path = tmp_path / "evening.json"
    save_world(world, path)
    assert load_world(path) == world


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world["actors"][0].update(visit={}), id="empty-visit"),
    pytest.param(lambda world: world.update(departed={}), id="malformed-departed"),
    pytest.param(lambda world: world["departed"].append(deepcopy(world["actors"][0])), id="duplicate-visitor"),
    pytest.param(lambda world: world["actors"][0].update(favorite_seat_id="missing"), id="unknown-own-seat"),
    pytest.param(lambda world: world["actors"][0]["visit"].update(beers=-1), id="negative-beers"),
    pytest.param(lambda world: world["actors"][0].update(visit=[]), id="malformed-visit"),
    pytest.param(lambda world: world["actors"][0]["visit"].update(grievances=[None]), id="malformed-grievance"),
])
def test_corrupt_evening_state_is_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = evening()
    corrupt(world)
    path = tmp_path / "corrupt.json"
    save_world(world, path)
    with pytest.raises(ValueError):
        load_world(path)


def test_server_opens_an_evening_that_waits_for_start(tmp_path: Path) -> None:
    data = inn()
    data["arrival"] = {"needs": {"thirst": [50, 90]}}
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(data))
    world = create_app(map_path, tmp_path / "save.json", {}, run_loop=False).state.runtime.world
    assert (world["paused"], world["tick"]) == (True, 0)
    assert [(actor["x"], actor["y"]) for actor in world["actors"]] == [(4, 7), (6, 7)]


def test_restart_opens_a_new_running_evening(tmp_path: Path) -> None:
    data = inn()
    data["arrival"] = {"needs": {"thirst": [0, 100]}}
    runtime = TavernRuntime(data, tmp_path / "save.json", {"temperature": 0})
    first = [actor["needs"]["thirst"] for actor in runtime.world["actors"]]
    runtime.world.update(paused=True, tick=50)
    runtime.world["departed"].append(runtime.world["actors"].pop())
    runtime.command({"type": "reset"})
    world = runtime.world
    assert (world["paused"], world["tick"], world["departed"], len(world["actors"])) == (False, 0, [], 2)
    assert [actor["needs"]["thirst"] for actor in world["actors"]] != first


def test_late_decision_for_a_departed_visitor_is_dropped(tmp_path: Path) -> None:
    async def run() -> None:
        runtime = TavernRuntime(inn(), tmp_path / "save.json", {"temperature": 0})
        task = asyncio.create_task(asyncio.sleep(0, result={
            "action": command("wait"), "source": "local", "scores": {}, "error": None}))
        await task
        runtime.pending["ada"] = (task, 0)
        runtime.world["departed"].append(runtime.world["actors"].pop(0))
        runtime.advance(0.1)
        assert "ada" not in runtime.pending
        await runtime.close()
    asyncio.run(run())


def test_seat_choice_is_kept_with_the_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seat = {"source": "local", "scores": {"sit:warm-west": 0.8}, "error": None}

    async def choose(observation: Any, config: Any, rng: Any) -> dict[str, Any]:
        return {"action": command("sit", "warm-west"), "source": "local",
                "scores": {"seating": 0.9}, "error": None, "seat": seat}

    async def run() -> None:
        runtime = TavernRuntime(inn(), tmp_path / "save.json", {"temperature": 0})
        runtime.advance(0.1)
        await asyncio.sleep(0)
        runtime.advance(0.1)
        assert visitor(runtime.world, "ada")["decision"]["seat"] == seat
        await runtime.close()
    monkeypatch.setattr("tavern.app.choose_action", choose)
    asyncio.run(run())


def demo() -> dict[str, Any]:
    """Load the repository's tavern layout."""
    return json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def test_demo_inn_has_four_identical_two_seat_tables() -> None:
    objects = create_world(demo())["map"]["objects"]
    tables = [item for item in objects if item["kind"] == "table"]
    sides = [sorted((chair["x"] - item["x"], chair["y"] - item["y"])
                    for chair in objects if chair.get("table_id") == item["id"]) for item in tables]
    assert [(item.get("width", 1), item.get("height", 1)) for item in tables] == [(1, 1)] * 4
    assert sides == [[(-1, 0), (1, 0)]] * 4


def test_demo_tables_are_ranked_by_their_surroundings() -> None:
    objects = create_world(demo())["map"]["objects"]
    appeal = {item["name"]: item["appeal"] for item in objects if item["kind"] == "table"}
    assert appeal["Hearth table"] > appeal["Window table"] > appeal["Corner table"]
    assert len(set(appeal.values())) == 4


def test_demo_evening_begins_with_everyone_inside_the_door() -> None:
    world = create_world(demo())
    door = next(item for item in world["map"]["objects"] if item["kind"] == "door")
    spot_x, spot_y = door["interaction_spots"][0]
    assert [abs(actor["x"] - spot_x) + abs(actor["y"] - spot_y) <= 1 for actor in world["actors"]] == [True] * 3
    assert ["tap" in actor["knowledge"]["objects"] for actor in world["actors"]] == [True] * 3


def test_demo_visitors_arrive_wanting_a_seat_and_a_beer() -> None:
    arrivals = [actor["needs"] for seed in range(20) for actor in create_world(demo(), seed)["actors"]]
    biased = [min(needs["thirst"], needs["fatigue"]) > max(needs["bladder"], needs["boredom"])
              for needs in arrivals]
    assert biased == [True] * len(arrivals)
    assert len({round(needs["thirst"]) for needs in arrivals}) > 10
