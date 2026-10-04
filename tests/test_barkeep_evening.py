"""The first evening with its barkeep, played offline in lockstep: Hob pours every mug, keeps to his cells and talks."""

import asyncio
import json
from random import Random
from typing import Any

import pytest

from tavern.evening.lockstep import Evening, Pace, run_evening
from tavern.evening.metrics import bar_metrics
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.staff import guests, on_staff
from tavern.mind.agents import Evaluators
from staff_hall import LAYOUT, ROOT, cards, hob_of

CONFIG = {"model": "jev-latest", "timeout": 1.0, "temperature": 0.25, "typesafe_api_key": None}


async def never_asked(*arguments: Any) -> dict[str, float]:
    """A Jev evaluator that must not be called: the evening is played by the local policy."""
    raise AssertionError("Jev was asked in an offline evening")


def first_evening(seed: int) -> dict[str, Any]:
    """The repository's first evening, opened with its guests and its barkeep."""
    data = json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text())
    return open_evening(LAYOUT, parse_scenario(data, cards("characters"), cards("staff")), seed)


def play(world: dict[str, Any], seed: int, until: float = 1200.0) -> Evening:
    """Play the evening on to a game time, or to its end."""
    return asyncio.run(run_evening(world, CONFIG, Random(seed), Evaluators(never_asked, never_asked),
                                   Pace(step=0.25, model_latency=1.0, time_limit=until)))


@pytest.mark.parametrize("seed", [pytest.param(1, id="seed-1"), pytest.param(4, id="seed-4")])
def test_hob_pours_every_mug_and_talks_through_the_evening(seed: int) -> None:
    world = first_evening(seed)
    evening = play(world, seed)
    mugs = [event for event in evening.events if event["type"] == "action_completed"
            and event["message"].endswith("completed take_beer")]
    bar = bar_metrics(evening.events, [item["id"] for item in world["actors"] if on_staff(item)])
    assert (guests(world), bar["served"] == len(mugs) > 0, bar["lines"] > 0) == ([], True, True)


@pytest.mark.parametrize("seed", [pytest.param(1, id="seed-1"), pytest.param(4, id="seed-4")])
def test_hob_never_stands_outside_his_staff_cells(seed: int) -> None:
    world = first_evening(seed)
    cells = [list(cell) for item in world["map"]["objects"] for cell in item.get("staff_cells", [])]
    seen = []
    for until in range(10, 600, 10):
        play(world, seed, float(until))
        seen.append([hob_of(world)["x"], hob_of(world)["y"]] in cells)
        if not guests(world) and not world["expected"]:
            break
    assert (len(seen) > 20, all(seen)) == (True, True)
