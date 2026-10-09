"""Lean requests: a fixture such as inspecting or waiting is put to the model only when the guest's state makes it worth weighing."""

import asyncio
from random import Random
from typing import Any

import pytest

from tavern.body.activities import ACTIVITIES
from tavern.mind.agents import Evaluators, choose_action
from tavern.mind.local_policy import ASK_FLOOR
from tavern.mind.selection import read_lean, read_switch, worth_asking


def act(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build a candidate action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


FLOORS = {"inspect": 0.3, "wait": 0.1, "leave": 0.25}


@pytest.mark.parametrize("ids, scores, kept, expected", [
    pytest.param([], {}, [], [], id="empty"),
    pytest.param(["inspect"], {"inspect": 0.1}, [], ["inspect"], id="single-option-under-its-floor-is-kept"),
    pytest.param(["sit:s1", "inspect", "wait"], {"sit:s1": 0.6, "inspect": 0.1, "wait": 0.05}, [], ["sit:s1"],
                 id="fixtures-under-their-floors-are-left-out"),
    pytest.param(["sit:s1", "inspect", "wait"], {"sit:s1": 0.6, "inspect": 0.4, "wait": 0.05}, [], ["sit:s1", "inspect"],
                 id="a-fixture-over-its-floor-is-kept-in-order"),
    pytest.param(["sit:s1", "inspect"], {"sit:s1": 0.6, "inspect": 0.3}, [], ["sit:s1", "inspect"],
                 id="a-score-at-the-floor-is-kept"),
    pytest.param(["inspect", "wait"], {"inspect": 0.1, "wait": 0.05}, [], ["inspect", "wait"],
                 id="all-under-their-floors-are-all-kept"),
    pytest.param(["talk:bea", "talk:cid"], {"talk:bea": 0.0, "talk:cid": 0.0}, [], ["talk:bea", "talk:cid"],
                 id="verbs-without-a-floor-are-always-kept"),
    pytest.param(["sit:s1", "inspect", "inspect:again"], {"sit:s1": 0.6, "inspect": 0.1, "inspect:again": 0.1}, [],
                 ["sit:s1"], id="duplicate-fixtures-are-both-left-out"),
    pytest.param(["leave:door", "inspect", "wait"], {"leave:door": 0.3, "inspect": 0.1, "wait": 0.05}, [],
                 ["leave:door", "inspect", "wait"], id="an-exit-alone-would-leave-no-way-to-stay"),
    pytest.param(["leave:door", "sit:s1", "wait"], {"leave:door": 0.3, "sit:s1": 0.6, "wait": 0.05}, [],
                 ["leave:door", "sit:s1"], id="an-exit-beside-a-seat-is-an-ordinary-option"),
    pytest.param(["sit:s1", "inspect", "wait"], {"sit:s1": 0.6, "inspect": 0.1, "wait": 0.05}, ["wait"],
                 ["sit:s1", "wait"], id="an-option-kept-by-the-caller-stays"),
])
def test_only_options_worth_a_slot_are_asked(ids: list[str], scores: dict[str, float], kept: list[str],
                                             expected: list[str]) -> None:
    candidates = [act(item.split(":")[0], item.split(":", 1)[1] if ":" in item else None) for item in ids]
    assert [item["id"] for item in worth_asking(candidates, scores, FLOORS, kept)] == expected


def test_the_floors_name_only_known_verbs() -> None:
    assert set(ASK_FLOOR) <= set(ACTIVITIES)


def seat_in_sight(**needs: float) -> dict[str, Any]:
    """Ada knows one free table chair and no tap; her needs are calm unless set."""
    chair = {"id": "chair", "kind": "chair", "x": 3, "y": 2, "reserved_by": None, "table_id": "table"}
    return {"actor": {"id": "ada", "name": "Ada", "x": 1, "y": 1, "inventory": {"beer": 0},
                      "needs": {"thirst": 20, "fatigue": 20, "bladder": 20, **needs},
                      "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5}},
            "objects": [chair], "memory": []}


def asked_verbs(view: dict[str, Any], key: str | None, lean: bool | None = True) -> list[str]:
    """The verbs of the options the first-stage evaluator is given."""
    seen: list[str] = []

    async def evaluate(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        seen.extend([] if seen else [item["verb"] for item in candidates])
        return {item["id"]: 1.0 for item in candidates}

    settings = {"typesafe_api_key": key, "model": "jev-latest", "timeout": 2.0, "temperature": 0.0,
                **({} if lean is None else {"lean": lean})}
    asyncio.run(choose_action(view, settings, Random(0), Evaluators(evaluate, evaluate)))
    return seen


@pytest.mark.parametrize("view, expected", [
    pytest.param(seat_in_sight(), ["seating", "wait"], id="calm-guest-is-not-asked-about-wandering-but-may-linger"),
    pytest.param(seat_in_sight(thirst=60), ["seating", "inspect"],
                 id="thirst-with-no-known-tap-is-worth-a-look-round-and-no-time-to-linger"),
])
def test_the_model_is_asked_only_about_options_worth_weighing(view: dict[str, Any], expected: list[str]) -> None:
    assert asked_verbs(view, "test") == expected


@pytest.mark.parametrize("lean, expected", [
    pytest.param(True, ["seating", "wait"], id="lean-requests-leave-out-the-fixtures"),
    pytest.param(False, ["seating", "inspect", "wait"], id="a-plain-request-holds-every-option"),
    pytest.param(None, ["seating", "inspect", "wait"], id="lean-requests-are-off-unless-the-config-asks"),
])
def test_lean_requests_are_a_setting_of_the_config(lean: bool | None, expected: list[str]) -> None:
    assert asked_verbs(seat_in_sight(), "test", lean) == expected


def test_without_a_key_the_lean_setting_changes_nothing() -> None:
    assert asked_verbs(seat_in_sight(), None, True) == []


@pytest.mark.parametrize("config, expected", [
    pytest.param({}, False, id="absent-is-off"),
    pytest.param({"lean": True}, True, id="on"),
    pytest.param({"lean": False}, False, id="off"),
])
def test_the_lean_setting_is_read_from_the_config(config: dict[str, Any], expected: bool) -> None:
    assert read_lean(config) is expected


@pytest.mark.parametrize("config", [
    pytest.param({"lean": "yes"}, id="a-string"),
    pytest.param({"lean": 1}, id="a-number"),
    pytest.param({"lean": None}, id="none"),
])
def test_a_lean_setting_that_is_not_a_bool_fails_loudly(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="lean"):
        read_lean(config)


@pytest.mark.parametrize("text, default, expected", [
    pytest.param(None, True, True, id="absent-takes-the-default"),
    pytest.param("", False, False, id="empty-takes-the-default"),
    pytest.param("true", False, True, id="true"),
    pytest.param("false", True, False, id="false"),
])
def test_a_switch_is_read_from_the_environment(text: str | None, default: bool, expected: bool) -> None:
    assert read_switch(text, default, "AI_LEAN") is expected


def test_a_switch_that_is_neither_true_nor_false_fails_loudly() -> None:
    with pytest.raises(ValueError, match="AI_LEAN"):
        read_switch("maybe", True, "AI_LEAN")
