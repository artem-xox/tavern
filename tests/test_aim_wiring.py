"""The aim stage in the rest of the machine: the decision applied to the world, the recorded choices, the trace."""

import asyncio
from random import Random
from typing import Any

from tavern.adapters.jev import request_body
from tavern.adapters.tracing import traced_scores
from tavern.evening.decisions import apply_decision
from tavern.evening.lockstep import Pace, run_evening
from tavern.hall.world import create_world, start_action, step_world
from tavern.mind.agents import Evaluators
from test_aim_choice import favouring
from test_tracing import JEV, scorer, tracer, named
from social_hall import actor, advance, command, spotted_hall

AIM = {"id": "win_over@talk:bea", "verb": "talk", "target_id": "bea", "aim": "win_over"}


def test_a_decision_with_an_aim_starts_its_action_with_it_and_keeps_the_stage_for_the_inspector() -> None:
    world = create_world(spotted_hall(), 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 8)
    ada = actor(world, "ada")
    stage = {"name": "win_over", "source": "jev", "scores": {"win_over@talk:bea": 0.8}, "error": None}
    apply_decision(world, ada, lambda: {"action": {"id": "talk:bea", "verb": "talk", "target_id": "bea",
                                                     "aim": "win_over"}, "source": "jev", "scores": {"talk": 1.0},
                                        "error": None, "aim": stage})
    assert (ada["action"]["aim"], ada["decision"]["aim"]) == ("win_over", stage)


def test_the_aim_stage_is_recorded_as_a_choice_of_the_evening() -> None:
    world = create_world(spotted_hall(), 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    for _ in range(80):
        step_world(world, 0.1)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    config = {"typesafe_api_key": "fake", "model": "jev-latest", "timeout": 1.0, "temperature": 0.0, "aims": True}
    evaluators = Evaluators(favouring(("talk", "company")), favouring("sit"), aims=favouring("win_over"))
    result = asyncio.run(run_evening(world, config, Random(3), evaluators, Pace(0.1, 1.0, 30.0)))
    kinds = {item["kind"] for item in result.choices}
    started = [item["message"] for item in result.events if item["type"] == "aim_set"]
    assert ("aims" in kinds, bool(started) and started[0].endswith("(win_over)")) == (True, True)


def test_a_traced_aim_run_carries_the_aim_question() -> None:
    traces = tracer()
    scores = asyncio.run(traced_scores("aims", scorer(), traces)({"self": {"name": "Edda"}}, [AIM], JEV))
    [run] = named(traces, "jev.aims")
    assert (run["run_type"], run["inputs"], run["outputs"]["scores"]) == (
        "llm", request_body({"self": {"name": "Edda"}}, [AIM], "jev-latest", aims=True), scores[0])
