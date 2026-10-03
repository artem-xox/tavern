"""Headless evenings honour interrupts like the live runtime: a stale answer is dropped."""

import asyncio
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.agents import Evaluators
from tavern.app import TavernRuntime
from tavern.lockstep import Evening, Pace, run_evening
from tavern.metrics import attention_counts
from tavern.world import create_world

KEYED = {"typesafe_api_key": "fake", "model": "jev-latest", "timeout": 1.0, "temperature": 0.0}


def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a bar, a door and a tap, and Ada standing about."""
    return {"width": 9, "height": 6, "blocked": [], "objects": [
        {"id": "bar", "kind": "bar", "name": "Bar", "x": 1, "y": 0, "width": 3, "height": 1},
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 8, "y": 0, "interaction_spots": [[7, 0]], "stock": 20},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 1, "y": 3}]}


async def waiting(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
    """Score waiting highest, whatever the situation."""
    return {action["id"]: float(action["verb"] == "wait") for action in candidates}


def evening(closes_at: float | None, latency: float) -> Evening:
    """Play the hall with a slow model, closing at a time or never."""
    world = create_world(hall(), 3)
    world["closes_at"] = closes_at
    return asyncio.run(run_evening(world, KEYED, Random(3), Evaluators(waiting, waiting),
                                   Pace(step=0.1, model_latency=latency, time_limit=12.0)))


@pytest.mark.parametrize("closes_at, asked, first", [
    pytest.param(None, [0.1], (5.1, "Ada chose wait"), id="no-interrupt-answer-lands"),
    pytest.param(2.0, [0.1, 2.0], (7.0, "Ada chose leave"), id="closing-call-drops-the-stale-answer"),
])
def test_an_interrupt_replaces_a_pending_answer(closes_at: float | None, asked: list[float],
                                                first: tuple[float, str]) -> None:
    result = evening(closes_at, latency=5.0)
    times = [round(item["time"], 1) for item in result.choices if item["actor_id"] == "ada"]
    started = next(event for event in result.events if event["type"] == "action_started")
    assert (times[:len(asked)], (round(started["time"], 1), started["message"])) == (asked, first)


@pytest.mark.parametrize("closes_at, gazes", [
    pytest.param(None, 0, id="quiet-evening"),
    pytest.param(2.0, 1, id="closing-call-turns-heads"),
])
def test_the_runner_counts_turned_heads(closes_at: float | None, gazes: int) -> None:
    assert evening(closes_at, latency=5.0).gazes == gazes


@pytest.mark.parametrize("closes_at, replaced", [
    pytest.param(None, False, id="no-interrupt-keeps-the-pending-thought"),
    pytest.param(0.15, True, id="closing-call-cancels-and-asks-again"),
])
def test_the_live_runtime_drops_a_stale_thought(tmp_path: Path, closes_at: float | None, replaced: bool) -> None:
    async def play() -> tuple[bool, bool]:
        runtime = TavernRuntime(hall(), tmp_path / "save.json", {"typesafe_api_key": None})
        runtime.world["closes_at"] = closes_at
        runtime.advance(0.1)
        first = runtime.pending["ada"][0]
        runtime.advance(0.1)
        replaced = runtime.pending["ada"][0] is not first
        await asyncio.sleep(0)  # a cancelled task settles on the loop's next turn
        outcome = replaced, first.cancelled()
        await runtime.close()
        return outcome
    assert asyncio.run(play()) == (replaced, replaced)


def logged(*kinds: str) -> list[dict[str, Any]]:
    """Build an event log with one event of each type."""
    return [{"time": float(index), "actor_id": "ada", "type": kind, "message": f"Ada {kind}"}
            for index, kind in enumerate(kinds)]


@pytest.mark.parametrize("events, gazes, expected", [
    pytest.param([], 0, {"interrupts": 0, "alerts": 0, "glances": 0}, id="empty-evening"),
    pytest.param(logged("interrupted"), 1, {"interrupts": 1, "alerts": 0, "glances": 0}, id="single-interrupt"),
    pytest.param(logged("interrupted", "interrupted", "alerted", "arrival"), 7,
                 {"interrupts": 2, "alerts": 1, "glances": 4}, id="duplicates-and-glances"),
])
def test_attention_counts_split_turned_heads(events: list[dict[str, Any]], gazes: int,
                                             expected: dict[str, int]) -> None:
    assert attention_counts(Evening(events, [], [], ["ada"], 10.0, gazes)) == expected


def test_attention_counts_reject_more_alerts_than_turned_heads() -> None:
    with pytest.raises(ValueError, match="turned heads"):
        attention_counts(Evening(logged("interrupted", "alerted"), [], [], ["ada"], 10.0, 1))
