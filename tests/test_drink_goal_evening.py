"""The goal of bringing a drink in a headless evening: set by the mind, served by the choice, done by the world."""

import asyncio
from collections.abc import Mapping
from random import Random
from typing import Any

from tavern.evening.lockstep import Pace, run_evening
from tavern.mind.agents import Evaluators
from tavern.mind.intentions import Written
from social_hall import know
from test_lockstep import seated_pair

CONFIG = {"typesafe_api_key": None, "model": "none", "timeout": 1.0, "temperature": 0.0}


async def unasked(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
    raise AssertionError("Without a key no model is asked")


async def kind_mind(view: Mapping[str, Any]) -> Written:
    """A fake mind: Ada, when shown someone to bring a drink, sets out to do it; everyone else wants nothing."""
    if view["actor_id"] == "ada" and view["fetchable"]:
        target = next(iter(view["fetchable"]))
        return {"thought": "They have nothing to drink.", "intention": "Fetch them a mug of ale.",
                "goal": {"kind": "bring_drink", "target": target, "status": "active"}}
    return {"thought": "A quiet evening.", "intention": "Stay seated and wait."}


def test_a_goal_to_bring_a_drink_is_served_by_the_choice_and_done_when_it_is_taken() -> None:
    world = seated_pair()
    know(world, "ada", "tap")
    result = asyncio.run(run_evening(world, CONFIG, Random(3), Evaluators(unasked, unasked), Pace(0.1, 1.0, 400.0),
                                     intender=kind_mind))
    story = [(event["actor_id"], event["type"]) for event in result.events
             if event["type"] in ("goal_set", "fetch_begun", "fetch_done", "goal_done")]
    assert story[:4] == [("ada", "goal_set"), ("ada", "fetch_begun"), ("ada", "fetch_done"), ("ada", "goal_done")]
    # The goal's events say which kind of goal they are about, so a count can tell them apart.
    assert {event["goal"] for event in result.events if event["type"] in ("goal_set", "goal_done")} == {"bring_drink"}
