"""Candidate generation and reproducible autonomous decisions."""

import asyncio
from random import Random
from typing import Any

import pytest

from tavern.agents import Evaluator, Evaluators, build_candidates, choose_action
from tavern.jev import JevError


def observation(objects=None, beer=0, needs=None, traits=None):
    return {
        "actor": {
            "id": "visitor", "name": "Visitor", "x": 1, "y": 1,
            "inventory": {"beer": beer},
            "needs": needs or {"thirst": 20, "fatigue": 20, "bladder": 20},
            "traits": traits or {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5},
        },
        "objects": objects or [], "memory": [],
    }


def resource(kind, object_id="resource", **fields):
    return {"id": object_id, "kind": kind, "x": 3, "y": 2,
            "reserved_by": None, **fields}


def config(**fields):
    return {"typesafe_api_key": None, "model": "jev-latest",
            "timeout": 2.0, "temperature": 0.0, **fields}


@pytest.mark.parametrize("view,expected", [
    pytest.param(observation(), ["inspect", "wait"], id="empty-known-world"),
    pytest.param(observation(beer=1), ["drink", "inspect", "wait"], id="single-own-beer"),
    pytest.param(observation([resource("tap", stock=2)]),
                 ["take_beer:resource", "inspect", "wait"], id="single-known-tap"),
    pytest.param(observation([resource("tap")]), ["inspect", "wait"], id="unknown-stock"),
    pytest.param(observation([resource("tap", stock=0)]), ["inspect", "wait"], id="empty-tap"),
    pytest.param(observation([resource("chair"), resource("chair")]),
                 ["rest:resource", "inspect", "wait"], id="duplicate-known-object"),
    pytest.param(observation([resource("toilet", reserved_by="other")]),
                 ["inspect", "wait"], id="reserved-by-another"),
    pytest.param(observation([resource("tap", stock=2)], beer=1),
                 ["drink", "inspect", "wait"], id="finish-owned-beer-first"),
])
def test_candidates_use_only_observed_resources(view, expected):
    assert [action["id"] for action in build_candidates(view)] == expected


@pytest.mark.parametrize("view", [
    pytest.param({}, id="empty-observation"),
    pytest.param(observation(beer=-1), id="malformed-inventory"),
    pytest.param(observation([resource("magic")]), id="malformed-kind"),
    pytest.param(observation([resource("tap", stock="many")]), id="malformed-stock"),
    pytest.param(observation([resource("chair"), resource("tap", stock=2)]), id="conflicting-duplicates"),
    pytest.param(observation(needs={"thirst": float("nan"), "fatigue": 0, "bladder": 0}), id="malformed-need"),
])
def test_candidates_reject_malformed_observations(view):
    with pytest.raises(ValueError):
        build_candidates(view)


@pytest.mark.parametrize("needs,expected", [
    pytest.param({"thirst": 100, "fatigue": 0, "bladder": 0}, "drink", id="urgent-thirst"),
    pytest.param({"thirst": 0, "fatigue": 100, "bladder": 0}, "rest:chair", id="urgent-fatigue"),
    pytest.param({"thirst": 0, "fatigue": 0, "bladder": 100}, "use_toilet:toilet", id="urgent-bladder"),
])
def test_local_policy_prioritizes_urgent_needs(needs, expected):
    view = observation([resource("chair", "chair"), resource("toilet", "toilet")], beer=1, needs=needs)
    result = asyncio.run(choose_action(view, config(), Random(4)))
    assert (result["action"]["id"], result["source"], result["error"]) == (expected, "local", None)


@pytest.mark.parametrize("seed", [
    pytest.param(0, id="seed-zero"),
    pytest.param(12, id="seed-twelve"),
])
def test_stochastic_selection_is_reproducible(seed):
    view = observation([resource("tap", stock=2), resource("chair", "chair")])
    settings = config(temperature=0.25)
    left, right = Random(seed), Random(seed)
    left_results = [asyncio.run(choose_action(view, settings, left))["action"] for _ in range(8)]
    right_results = [asyncio.run(choose_action(view, settings, right))["action"] for _ in range(8)]
    assert left_results == right_results


@pytest.mark.parametrize("traits,expected", [
    pytest.param({"curiosity": 1, "patience": 0}, "inspect", id="curious-exploration"),
    pytest.param({"curiosity": 0, "patience": 1}, "wait", id="patient-waiting"),
])
def test_traits_affect_offline_choice(traits, expected):
    view = observation(needs={"thirst": 0, "fatigue": 0, "bladder": 0}, traits=traits)
    assert asyncio.run(choose_action(view, config(), Random(0)))["action"]["id"] == expected


@pytest.mark.parametrize("temperature", [
    pytest.param(-1, id="negative"),
    pytest.param(float("nan"), id="not-finite"),
    pytest.param("warm", id="malformed"),
])
def test_invalid_temperature_fails_loudly(temperature):
    with pytest.raises(ValueError):
        asyncio.run(choose_action(observation(), config(temperature=temperature), Random(0)))

async def no_seat_judgement(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
    raise AssertionError("This test expects no judgement of seats")


def test_jev_success_uses_only_supplied_candidates():
    async def evaluate(view, candidates, settings):
        return {action["id"]: float(action["verb"] == "wait") for action in candidates}

    result = asyncio.run(choose_action(observation(), config(typesafe_api_key="test"), Random(0),
                                       Evaluators(evaluate, no_seat_judgement)))
    assert result == {"action": {"id": "wait", "verb": "wait", "target_id": None},
                      "source": "jev", "scores": {"inspect": 0.0, "wait": 1.0}, "error": None}


def test_jev_error_produces_visible_local_fallback():
    async def evaluate(view, candidates, settings):
        raise JevError("Jev request timed out")

    result = asyncio.run(choose_action(observation(), config(typesafe_api_key="test"), Random(0),
                                       Evaluators(evaluate, no_seat_judgement)))
    assert (result["source"], result["error"]) == ("local", "Jev request timed out")


@pytest.mark.parametrize("view", [
    pytest.param(observation([resource("chair", reserved_by=123)]), id="malformed-reservation"),
    pytest.param({**observation(), "actor": {**observation()["actor"], "id": ""}}, id="empty-actor-id"),
])
def test_malformed_actor_or_reservation_is_not_silently_ignored(view):
    with pytest.raises(ValueError):
        build_candidates(view)


def preferring(verb: str) -> Evaluator:
    """Build a fake evaluator that scores one verb highest."""
    async def evaluate(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["verb"] == verb) for action in candidates}
    return evaluate


async def timing_out(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
    """Fail like the Jev adapter does on a timeout."""
    raise JevError("Jev request timed out")


def tired_newcomer() -> dict[str, Any]:
    """A tired visitor who knows a table with two free chairs."""
    chairs = [resource("chair", f"chair-{side}", table_id="table", x=x) for side, x in (("west", 2), ("east", 4))]
    return observation(chairs, needs={"thirst": 0, "fatigue": 90, "bladder": 0})


@pytest.mark.parametrize("view, evaluators, expected", [
    pytest.param(observation(), Evaluators(preferring("wait"), preferring("sit")),
                 ("wait", "jev", None, None), id="action-evaluator-scores-the-next-activity"),
    pytest.param(tired_newcomer(), Evaluators(preferring("seating"), preferring("sit")),
                 ("sit", "jev", None, "jev"), id="seat-evaluator-scores-the-chairs"),
    pytest.param(observation(), Evaluators(timing_out, preferring("sit")),
                 ("inspect", "local", "Jev request timed out", None), id="failure-falls-back-to-local"),
])
def test_explicit_evaluators_score_the_decision(
        view: dict[str, Any], evaluators: Evaluators, expected: tuple[Any, ...]) -> None:
    result = asyncio.run(choose_action(view, config(typesafe_api_key="test"), Random(0), evaluators))
    assert (result["action"]["verb"], result["source"], result["error"],
            result.get("seat", {}).get("source")) == expected


def test_without_a_key_explicit_evaluators_are_not_asked() -> None:
    result = asyncio.run(choose_action(observation(), config(), Random(0), Evaluators(timing_out, timing_out)))
    assert (result["source"], result["error"]) == ("local", None)


def test_a_model_key_without_evaluators_fails_loudly():
    with pytest.raises(ValueError, match="needs evaluators"):
        asyncio.run(choose_action(observation(), config(typesafe_api_key="test"), Random(0)))
