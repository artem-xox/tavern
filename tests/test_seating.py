"""Visitors' choices: two-stage seat choice, own seats, watching and going home."""

import asyncio
from collections import Counter
import json
from pathlib import Path
from random import Random
from typing import Any, Awaitable, Callable

import httpx
import pytest

from tavern.mind.agents import Evaluators, build_candidates, build_seat_candidates, choose_action
from tavern.adapters.jev import JevError, evaluate_actions, evaluate_seats
from tavern.hall.world import create_world, observe_actor


def view(objects: list[dict[str, Any]] | None = None, needs: dict[str, float] | None = None,
         visitors: list[dict[str, Any]] | None = None, **actor: Any) -> dict[str, Any]:
    """Build a personal observation; keywords override the visitor's own state."""
    calm = {"thirst": 10, "fatigue": 10, "bladder": 10, "social": 10, "boredom": 10}
    own = {"id": "ada", "name": "Ada", "x": 5, "y": 5, "inventory": {"beer": 0},
           "needs": {**calm, **(needs or {})},
           "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5},
           "favorite_seat_id": None, "visit": {"seconds": 0.0, "beers": 0, "grievances": []}}
    return {"actor": {**own, **actor}, "objects": objects or [], "visitors": visitors or [], "memory": []}


def company(seat_id: str, table_id: str) -> dict[str, Any]:
    """Describe Bea, seen seated at a table."""
    return {"id": "bea", "name": "Bea", "x": 5, "y": 3, "seat_id": seat_id, "table_id": table_id, "available": True}


def seat(seat_id: str, appeal: float = 0.0, **fields: Any) -> dict[str, Any]:
    """Describe a known chair at its own table."""
    return {"id": seat_id, "kind": "chair", "x": 5, "y": 3, "table_id": f"table-{seat_id}",
            "appeal": appeal, "comforts": [], "reserved_by": None, **fields}


def door(**fields: Any) -> dict[str, Any]:
    """Describe the known way out."""
    return {"id": "door", "kind": "door", "x": 5, "y": 9, "reserved_by": None, **fields}


def sight(kind: str, object_id: str, **fields: Any) -> dict[str, Any]:
    """Describe a known window or fireplace with a spot to watch it from."""
    return {"id": object_id, "kind": kind, "x": 0, "y": 3, "interaction_spots": [[1, 3]],
            "reserved_by": None, **fields}


def tap(stock: int) -> dict[str, Any]:
    """Describe a known beer tap with its last observed stock."""
    return {"id": "tap", "kind": "tap", "x": 1, "y": 1, "stock": stock, "reserved_by": None}


def config(**fields: Any) -> dict[str, Any]:
    """Build an offline decision configuration unless a key is supplied."""
    return {"typesafe_api_key": None, "model": "jev-latest", "timeout": 2.0, "temperature": 0.0, **fields}


def visit(seconds: float, beers: int, grievances: list[str]) -> dict[str, Any]:
    """Describe what has happened to a visitor during this visit."""
    return {"seconds": seconds, "beers": beers, "grievances": grievances}


async def no_seat_judgement(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
    raise AssertionError("This test expects no judgement of seats")


def request_body(candidates: list[dict[str, Any]], evaluate: Callable[..., Awaitable[Any]] = evaluate_actions,
                 observation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Capture the JSON body a Jev evaluation would send."""
    captured: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"answers": {
            action["id"]: {"type": "score", "score": 2} for action in candidates}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await evaluate(observation or view(), candidates, config(typesafe_api_key="test"), client)
    asyncio.run(run())
    return captured[0]


@pytest.mark.parametrize("seats, own, expected", [
    pytest.param([], None, [], id="empty-no-known-seat"),
    pytest.param([seat("s1")], None, ["seating"], id="single-free-seat"),
    pytest.param([seat("s1"), seat("s2")], None, ["seating"], id="duplicate-free-seats-one-choice"),
    pytest.param([seat("s1"), seat("s2")], "s1", ["sit:s1"], id="own-seat-is-free"),
    pytest.param([seat("s1", reserved_by="bea"), seat("s2")], "s1", ["seating"], id="own-seat-was-taken"),
    pytest.param([seat("s1", reserved_by="bea")], None, [], id="every-seat-taken"),
])
def test_seats_are_one_seating_choice_until_a_visitor_owns_one(
        seats: list[dict[str, Any]], own: str | None, expected: list[str]) -> None:
    candidates = build_candidates(view(seats, favorite_seat_id=own))
    assert [action["id"] for action in candidates if action["verb"] in ("seating", "sit")] == expected


@pytest.mark.parametrize("seats, visitors, expected", [
    pytest.param([seat("own", table_id="alone"), seat("free", table_id="shared")], [], ["sit:own"],
                 id="empty-hall-keeps-own-seat"),
    pytest.param([seat("own", table_id="alone"), seat("free", table_id="shared"),
                  seat("busy", table_id="shared", reserved_by="bea")], [company("busy", "shared")],
                 ["sit:own", "seating"], id="single-companion-to-join"),
    pytest.param([seat("own", table_id="alone"), seat("free", table_id="shared"),
                  seat("busy", table_id="shared", reserved_by="bea")], [company("busy", "shared")] * 2,
                 ["sit:own", "seating"], id="duplicate-companion-sighting"),
    pytest.param([seat("own", table_id="alone"), seat("busy", table_id="full", reserved_by="bea"),
                  seat("taken", table_id="full", reserved_by="cid")], [company("busy", "full")],
                 ["sit:own"], id="companions-table-is-full"),
    pytest.param([seat("own", table_id="ours"), seat("mate", table_id="ours", reserved_by="bea"),
                  seat("free", table_id="shared")], [company("mate", "ours")],
                 ["sit:own"], id="company-already-at-own-table"),
])
def test_seated_visitor_may_move_only_to_join_company(seats: list[dict[str, Any]], visitors: list[dict[str, Any]],
                                                      expected: list[str]) -> None:
    candidates = build_candidates(view(seats, visitors=visitors, favorite_seat_id="own"))
    assert [action["id"] for action in candidates if action["verb"] in ("seating", "sit")] == expected


def test_lonely_visitor_moves_to_sit_with_company() -> None:
    seats = [seat("own", table_id="alone"), seat("free", table_id="shared"),
             seat("busy", table_id="shared", reserved_by="bea")]
    observation = view(seats, needs={"social": 90}, visitors=[company("busy", "shared")], favorite_seat_id="own")
    result = asyncio.run(choose_action(observation, config(), Random(0)))
    assert (max(result["scores"], key=result["scores"].get), result["action"]["id"]) == ("seating", "sit:free")


@pytest.mark.parametrize("seats, expected", [
    pytest.param([], [], id="empty"),
    pytest.param([seat("s1")], ["sit:s1"], id="single-free-seat"),
    pytest.param([seat("s1"), seat("s1")], ["sit:s1"], id="duplicate-observation"),
    pytest.param([seat("s1", reserved_by="bea"), seat("s2"),
                  {"id": "stool", "kind": "chair", "x": 1, "y": 1, "reserved_by": None}],
                 ["sit:s2"], id="taken-and-tableless-chairs-skipped"),
])
def test_seat_choice_lists_free_table_chairs(seats: list[dict[str, Any]], expected: list[str]) -> None:
    assert [action["id"] for action in build_seat_candidates(view(seats))] == expected


@pytest.mark.parametrize("observation", [
    pytest.param(view(favorite_seat_id=42), id="malformed-own-seat"),
    pytest.param(view(visit=visit(-1, 0, [])), id="negative-visit-time"),
    pytest.param(view(visit={"seconds": 0, "beers": "two", "grievances": []}), id="malformed-beer-count"),
    pytest.param(view(visit={"seconds": 0, "beers": 0, "grievances": "none"}), id="malformed-grievances"),
    pytest.param(view([seat("s1", reserved_by=5)]), id="malformed-seat-reservation"),
])
def test_malformed_seating_state_fails_loudly(observation: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        build_seat_candidates(observation)


@pytest.mark.parametrize("objects, offered", [
    pytest.param([], False, id="empty-door-unknown"),
    pytest.param([door()], True, id="single-known-door"),
    pytest.param([door(), door()], True, id="duplicate-door-observation"),
    pytest.param([door(reserved_by="bea")], False, id="door-busy"),
])
def test_leaving_needs_a_known_free_door(objects: list[dict[str, Any]], offered: bool) -> None:
    assert ("leave:door" in [action["id"] for action in build_candidates(view(objects))]) == offered


@pytest.mark.parametrize("objects, expected", [
    pytest.param([], [], id="empty-nothing-to-watch"),
    pytest.param([sight("fireplace", "hearth")], ["watch:hearth"], id="single-fireplace"),
    pytest.param([sight("window", "w1"), sight("window", "w1")], ["watch:w1"], id="duplicate-window-observation"),
    pytest.param([sight("window", "w1", reserved_by="bea"), sight("window", "w2")], ["watch:w2"],
                 id="busy-window-skipped"),
    pytest.param([sight("window", "w3", interaction_spots=[])], [], id="window-without-a-spot"),
])
def test_known_windows_and_fireplace_can_be_watched(objects: list[dict[str, Any]], expected: list[str]) -> None:
    assert [action["id"] for action in build_candidates(view(objects)) if action["verb"] == "watch"] == expected


def test_malformed_watching_spot_fails_loudly() -> None:
    with pytest.raises(ValueError):
        build_candidates(view([sight("window", "w1", interaction_spots="by the glass")]))


@pytest.mark.parametrize("comfort, boredom, expected", [
    pytest.param(0.9, 40, "watch:hearth", id="cosy-soul-watches-the-fire"),
    pytest.param(0.1, 90, "play_darts:darts", id="restless-soul-plays-darts"),
])
def test_local_policy_picks_a_pastime_by_temperament(comfort: float, boredom: float, expected: str) -> None:
    darts = {"id": "darts", "kind": "darts", "x": 2, "y": 9, "reserved_by": None}
    observation = view([sight("fireplace", "hearth"), darts], needs={"boredom": boredom},
                       traits={"patience": 0.5, "comfort": comfort, "curiosity": 0.5})
    assert asyncio.run(choose_action(observation, config(), Random(0)))["action"]["id"] == expected


def test_watch_question_describes_a_quiet_pastime() -> None:
    body = request_body([{"id": "watch:hearth", "verb": "watch", "target_id": "hearth"}])
    instructions = body["questions"]["watch:hearth"]["instructions"]
    assert ("boredom" in instructions, "fire" in instructions, "window" in instructions) == (True, True, True)


def test_seating_resolves_to_the_cosiest_seat_for_a_comfort_lover() -> None:
    observation = view([seat("plain"), seat("hearth", appeal=0.5, comforts=["fireplace"])],
                       needs={"fatigue": 100}, traits={"patience": 0.5, "comfort": 1.0, "curiosity": 0.5})
    result = asyncio.run(choose_action(observation, config(), Random(0)))
    assert result["action"] == {"id": "sit:hearth", "verb": "sit", "target_id": "hearth"}
    assert max(result["scores"], key=result["scores"].get) == "seating"
    assert (sorted(result["seat"]["scores"]), result["seat"]["source"]) == (["sit:hearth", "sit:plain"], "local")


def test_jev_judges_both_the_wish_to_sit_and_the_seat() -> None:
    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["verb"] == "seating") for action in candidates}

    async def seats(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["target_id"] == "plain") for action in candidates}

    observation = view([seat("plain"), seat("hearth", appeal=0.5)])
    result = asyncio.run(choose_action(observation, config(typesafe_api_key="test"), Random(0),
                                       Evaluators(actions, seats)))
    assert (result["action"]["id"], result["source"], result["seat"]) == (
        "sit:plain", "jev", {"source": "jev", "scores": {"sit:hearth": 0.0, "sit:plain": 1.0}, "error": None})


def test_failed_seat_judgement_falls_back_visibly() -> None:
    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["verb"] == "seating") for action in candidates}

    async def seats(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        raise JevError("Jev request timed out")

    observation = view([seat("plain"), seat("hearth", appeal=0.5)])
    result = asyncio.run(choose_action(observation, config(typesafe_api_key="test"), Random(0),
                                       Evaluators(actions, seats)))
    assert (result["action"]["verb"], result["seat"]["source"], result["seat"]["error"]) == (
        "sit", "local", "Jev request timed out")


@pytest.mark.parametrize("history, needs, patience, objects, leaves", [
    pytest.param(visit(0, 0, []), {}, 0.5, [door()], False, id="newcomer-stays"),
    pytest.param(visit(600, 3, []), {}, 0.5, [door()], True, id="content-regular-goes-home"),
    pytest.param(visit(120, 0, ["Bea took my seat"]), {"thirst": 40, "fatigue": 40, "bladder": 40}, 0.9,
                 [door()], False, id="single-grievance-patient-visitor-stays"),
    pytest.param(visit(120, 0, ["Bea took my seat"] * 2), {"thirst": 40, "fatigue": 40, "bladder": 40}, 0.3,
                 [door()], True, id="duplicate-grievances-walk-out"),
    pytest.param(visit(120, 1, []), {"thirst": 90}, 0.5, [door(), tap(stock=0)], True,
                 id="dry-tap-ends-the-evening"),
])
def test_local_policy_decides_when_to_go_home(history: dict[str, Any], needs: dict[str, float], patience: float,
                                              objects: list[dict[str, Any]], leaves: bool) -> None:
    observation = view(objects, needs=needs, visit=history,
                       traits={"patience": patience, "comfort": 0.5, "curiosity": 0.5})
    result = asyncio.run(choose_action(observation, config(), Random(0)))
    assert (result["action"]["verb"] == "leave") == leaves


@pytest.mark.parametrize("leave_score, drawn", [
    pytest.param(0.0, False, id="pointless-exit-never-drawn"),
    pytest.param(0.25, False, id="slightly-worthwhile-exit-never-drawn"),
    pytest.param(0.5, True, id="moderately-worthwhile-exit-may-be-drawn"),
    pytest.param(1.0, True, id="clearly-best-exit-drawn"),
])
def test_walking_out_needs_the_evaluators_endorsement(leave_score: float, drawn: bool) -> None:
    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: leave_score if action["verb"] == "leave" else 0.5 for action in candidates}

    settings = config(typesafe_api_key="test", temperature=0.25)
    verbs = {asyncio.run(choose_action(view([door()]), settings, Random(seed),
                                       Evaluators(actions, no_seat_judgement)))["action"]["verb"]
             for seed in range(100)}
    assert ("leave" in verbs) == drawn


@pytest.mark.parametrize("seen_ago, offered", [
    pytest.param(2.0, False, id="busy-moments-ago"),
    pytest.param(30.0, True, id="probably-free-again"),
])
def test_old_sightings_of_a_busy_place_expire(seen_ago: float, offered: bool) -> None:
    observation = {**view([{**tap(stock=5), "reserved_by": "bea", "last_seen": 100.0 - seen_ago}],
                          needs={"thirst": 80}), "time": 100.0}
    assert ("take_beer:tap" in [action["id"] for action in build_candidates(observation)]) == offered


def test_a_chair_seen_occupied_is_taken_whatever_memory_says() -> None:
    observation = {**view([seat("s1", last_seen=0.0), seat("s2", last_seen=0.0)],
                          visitors=[company("s1", "table-s1")]), "time": 100.0}
    assert [action["id"] for action in build_seat_candidates(observation)] == ["sit:s2"]


@pytest.mark.parametrize("runner_up, drawn", [
    pytest.param(0.9, True, id="close-second-is-sometimes-drawn"),
    pytest.param(0.7, False, id="clearly-worse-option-never-drawn"),
])
def test_only_options_close_to_the_best_are_drawn(runner_up: float, drawn: bool) -> None:
    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: 1.0 if action["verb"] == "wait" else runner_up for action in candidates}

    settings = config(typesafe_api_key="test", temperature=0.25)
    verbs = {asyncio.run(choose_action(view(), settings, Random(seed),
                                       Evaluators(actions, no_seat_judgement)))["action"]["verb"]
             for seed in range(100)}
    assert ("inspect" in verbs) == drawn


@pytest.mark.parametrize("seats, seated, offered", [
    pytest.param([], False, True, id="empty-no-seat-known-drinks-standing"),
    pytest.param([seat("own", reserved_by="ada")], True, True, id="single-seated-visitor-sips"),
    pytest.param([seat("free"), seat("free")], False, False, id="duplicate-free-seat-carry-the-mug-there"),
    pytest.param([seat("taken", reserved_by="bea")], False, True, id="every-seat-taken-drinks-standing"),
])
def test_beer_is_drunk_seated_when_a_seat_is_to_be_had(seats: list[dict[str, Any]], seated: bool,
                                                       offered: bool) -> None:
    own = "own" if seated else None
    observation = view(seats, inventory={"beer": 1}, seat_id=own, favorite_seat_id=own)
    assert ("drink" in [action["id"] for action in build_candidates(observation)]) == offered


def test_jev_reads_a_briefing_instead_of_raw_maps() -> None:
    sent: list[Any] = []

    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        sent.append(observation)
        return {action["id"]: 0.5 for action in candidates}

    layout = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
    observation = observe_actor(create_world(layout), "mara")
    asyncio.run(choose_action(observation, config(typesafe_api_key="test"), Random(0),
                              Evaluators(actions, no_seat_judgement)))
    assert set(sent[0]) == {"situation", "options", "self"}
    assert set(sent[0]["options"]) == {action["id"] for action in build_candidates(observation)}
    assert "knowledge" not in sent[0]["self"]


def test_demo_newcomers_mostly_head_for_a_seat_or_the_tap() -> None:
    layout = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
    verbs: Counter[str] = Counter()
    for seed in range(12):
        world, rng = create_world(layout, seed), Random(seed)
        for actor in world["actors"]:
            decision = asyncio.run(choose_action(observe_actor(world, actor["id"]), config(temperature=0.25), rng))
            verbs[decision["action"]["verb"]] += 1
    assert (verbs["sit"] + verbs["take_beer"]) / sum(verbs.values()) >= 2 / 3


@pytest.mark.parametrize("phrase", [
    pytest.param("visit.beers", id="drank-their-fill"),
    pytest.param("visit.seconds", id="stayed-a-good-while"),
    pytest.param("stock 0", id="beer-ran-out"),
    pytest.param("took their seat", id="seat-was-taken"),
    pytest.param("quarrel", id="was-offended"),
    pytest.param("just arrived", id="newcomers-stay"),
])
def test_leave_question_explains_when_a_visitor_goes_home(phrase: str) -> None:
    body = request_body([{"id": "leave:door", "verb": "leave", "target_id": "door"}])
    assert phrase in body["questions"]["leave:door"]["instructions"]


def test_seat_questions_have_their_own_rubric_about_appeal_and_company() -> None:
    sit = [{"id": "sit:s1", "verb": "sit", "target_id": "s1"}]
    seat_question = request_body(sit, evaluate_seats)["questions"]["sit:s1"]
    action_question = request_body(sit)["questions"]["sit:s1"]
    instructions = seat_question["instructions"]
    assert (len(seat_question["criteria"]), seat_question["criteria"] != action_question["criteria"]) == (5, True)
    assert ("appeal" in instructions, "comfort" in instructions, "company" in instructions) == (True, True, True)


@pytest.mark.parametrize("evaluate, action", [
    pytest.param(evaluate_actions, {"id": "wait", "verb": "wait", "target_id": None}, id="action-question"),
    pytest.param(evaluate_seats, {"id": "sit:s1", "verb": "sit", "target_id": "s1"}, id="seat-question"),
])
def test_questions_quote_the_briefing_and_name_the_guest(evaluate: Callable[..., Awaitable[Any]],
                                                         action: dict[str, Any]) -> None:
    briefed = {"situation": "Ada sits by the fire.", "self": {"name": "Ada"},
               "options": {action["id"]: "do the briefed thing"}}
    instructions = request_body([action], evaluate, briefed)["questions"][action["id"]]["instructions"]
    assert ("do the briefed thing" in instructions, "Ada" in instructions) == (True, True)


def test_unknown_verb_cannot_be_described_to_jev() -> None:
    with pytest.raises(ValueError):
        request_body([{"id": "fly", "verb": "fly", "target_id": None}])
