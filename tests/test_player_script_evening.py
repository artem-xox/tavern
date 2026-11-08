"""A scripted player in a headless evening: each step runs at the tick it falls in, a refused step is logged."""

import asyncio
from random import Random
from typing import Any

from tavern.evening.lockstep import Evening, Pace, run_evening
from tavern.evening.player_script import PlayerScript, Step
from tavern.mind.agents import Evaluators
from test_player_hands import TAKE_BEER, played

CONFIG = {"model": "jev-latest", "timeout": 1.0, "temperature": 0.25, "typesafe_api_key": None}
BOGUS = {"id": "juggle:tap", "verb": "juggle", "target_id": "tap"}


async def never_asked(*arguments: Any) -> dict[str, float]:
    raise AssertionError("Jev was asked in an offline evening")


def play(script: PlayerScript | None, until: float = 6.0) -> Evening:
    return asyncio.run(run_evening(played(), CONFIG, Random(1), Evaluators(never_asked, never_asked),
                                   Pace(step=0.25, model_latency=1.0, time_limit=until), script=script))


def act(at: float, action: dict[str, Any]) -> Step:
    return Step(at, {"type": "act", "action": action})


def test_a_step_runs_in_the_tick_it_falls_in() -> None:
    evening = play(PlayerScript("ada", (act(1.1, TAKE_BEER),)))
    [chosen] = [item for item in evening.events if item["type"] == "player_act"]
    assert 1.1 <= chosen["time"] < 1.1 + 0.25


def test_steps_with_the_same_time_run_in_order() -> None:
    evening = play(PlayerScript("ada", (Step(1.0, {"type": "steer", "on": False}), Step(1.0, {"type": "steer", "on": True}),
                                        act(1.0, TAKE_BEER))))
    kinds = [item["type"] for item in evening.events if item["type"] in ("steer", "player_act")]
    assert kinds == ["steer", "steer", "player_act"]


def test_a_refused_step_is_logged_and_the_evening_goes_on() -> None:
    evening = play(PlayerScript("ada", (act(1.0, BOGUS), act(3.0, TAKE_BEER))))
    refusals = [item["message"] for item in evening.events if item["type"] == "control"
                and item["message"].startswith("Player script: act refused: ")]
    assert (len(refusals), [item["time"] >= 3.0 for item in evening.events if item["type"] == "player_act"]) == (
        1, [True])


def test_an_evening_without_a_script_has_no_player_steps() -> None:
    evening = play(None)
    assert not [item for item in evening.events if item["type"] == "player_act"]
