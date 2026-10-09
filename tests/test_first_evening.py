"""The repository's first evening, offline: six guests arrive over time and the hall empties by closing."""

import asyncio
import json
from pathlib import Path
from random import Random
from typing import Any, Mapping

import pytest

from tavern.mind.agents import choose_action
from tavern.evening.scenario import Scenario, open_evening, parse_scenario
from tavern.hall.staff import guests
from tavern.hall.world import observe_actor, observe_people, start_action, step_world

ROOT = Path(__file__).parents[1]


def first_evening() -> tuple[dict[str, Any], Scenario]:
    """Load the repository's room and its first-evening scenario."""
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    return room, parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()))


def listening(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether someone is talking to this guest, who then waits for the chat to end."""
    return any(item["action"] and item["action"]["verb"] == "talk" and item["action"]["target_id"] == actor["id"]
               for item in world["actors"])


async def play(world: dict[str, Any], rng: Random, limit: float, tick: float = 0.25) -> int:
    """Run the evening with the offline policy, like the server, until no guest is left or time runs out.

    Staff decide nothing. Idle guests decide at most once a second. Ticks are coarser than the server's 0.1 s to keep
    the test quick; movement and timers accumulate the same way. Returns the most guests ever
    found sharing a cell.
    """
    ready: dict[str, float] = {}
    overlap = 0
    while (guests(world) or world["expected"]) and world["time"] < limit:
        for actor in guests(world):
            if actor["status"] != "idle" or world["time"] < ready.get(actor["id"], 0.0) or listening(world, actor):
                continue
            observation = {**observe_actor(world, actor["id"]), "people": observe_people(world, actor["id"])}
            decision = await choose_action(observation, {"temperature": 0.25}, rng)
            start_action(world, actor["id"], decision["action"])
            ready[actor["id"]] = world["time"] + 1.0
        step_world(world, tick)
        cells = [(item["x"], item["y"]) for item in world["actors"]]
        overlap = max(overlap, len(cells) - len(set(cells)))
    return overlap


# Left alone, the guests of these evenings would linger until 676 s and 761 s: closing at 420 s
# is what empties the hall.
@pytest.mark.parametrize("seed", [
    pytest.param(1, id="seed-1"),
    pytest.param(7, id="seed-7"),
])
def test_six_guests_arrive_over_time_and_all_go_home_by_closing(seed: int) -> None:
    room, scenario = first_evening()
    world = open_evening(room, scenario, seed)
    schedule = {item["id"]: item["arrives_at"] for item in scenario.guests}
    overlap = asyncio.run(play(world, Random(seed), limit=scenario.closes_at + 120))
    # A guest's arrival is when their visit began: they left `seconds` after it.
    arrived = {item["id"]: item["visit"]["left_at"] - item["visit"]["seconds"] for item in world["departed"]}
    last_out = max(item["visit"]["left_at"] for item in world["departed"])
    # The barkeep stays at his bar all night: the hall is empty of guests, not of people.
    assert (guests(world), world["expected"], overlap) == ([], [], 0)
    assert sorted(arrived) == sorted(schedule)
    assert [arrived[guest] >= time - 0.01 for guest, time in schedule.items()] == [True] * len(schedule)
    assert len({round(time) for time in arrived.values()}) >= 4
    assert last_out <= scenario.closes_at + 60


@pytest.mark.parametrize("seed", [
    pytest.param(1, id="seed-1"),
    pytest.param(7, id="seed-7"),
])
def test_every_guest_comes_in_with_full_energy(seed: int) -> None:
    # Energy is the `fatigue` need, as urgency: 0 is fully rested, so nobody lies down to sleep on arrival.
    room, scenario = first_evening()
    world = open_evening(room, scenario, seed)
    tonight = [*guests(world), *world["expected"]]
    assert len(tonight) == len(scenario.guests)
    # The one guest who comes in unwell (see `tavern.body.ailment`) is the exception.
    assert {item["needs"]["fatigue"] for item in tonight if not item.get("ailing")} == {0.0}
    assert [item["needs"]["fatigue"] for item in tonight if item.get("ailing")] == [80.0]
