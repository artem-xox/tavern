"""A guest's intention in Jev's briefing, and Jev's guidance to weigh options against it."""

import asyncio
import json
from typing import Any

import httpx
import pytest

from tavern.briefing import brief
from tavern.jev import evaluate_actions


def observation(intention: dict[str, Any] | None, time: float | None = 100.0) -> dict[str, Any]:
    """A bare observation of Ada, holding an intention or none, at a game time or without a clock."""
    actor = {"id": "ada", "name": "Ada", "x": 1, "y": 1, "needs": {"thirst": 10.0}, "inventory": {"beer": 0},
             "intention": intention}
    return {"actor": actor, "objects": [], **({} if time is None else {"time": time})}


def written(at: float = 60.0) -> dict[str, Any]:
    """An intention written after a quarrel."""
    return {"thought": "Bea made a fool of me.", "intention": "Drink up and go home.", "written_at": at,
            "trigger": {"kind": "quarrel", "text": "Quarreled with Bea about the beer", "time": at}}


@pytest.mark.parametrize("prepared, expected", [
    pytest.param(observation(written()), 'Their own reading of things: "Bea made a fool of me." Their intention: '
                 'Drink up and go home (decided 40 s ago, after: Quarreled with Bea about the beer).',
                 id="written-40-seconds-ago"),
    pytest.param(observation(written(at=99.0)), "Their intention: Drink up and go home (decided just now, after: "
                 "Quarreled with Bea about the beer).", id="just-now"),
    pytest.param(observation(written(), time=None), "Their intention: Drink up and go home (after: Quarreled "
                 "with Bea about the beer).", id="no-clock"),
])
def test_the_briefing_shows_the_current_intention(prepared: dict[str, Any], expected: str) -> None:
    assert expected in brief(prepared, [])["situation"]


def without_field() -> dict[str, Any]:
    """An observation built outside the world, whose actor has no intention field."""
    prepared = observation(None)
    del prepared["actor"]["intention"]
    return prepared


@pytest.mark.parametrize("prepared", [
    pytest.param(observation(None), id="no-intention-yet"),
    pytest.param(without_field(), id="bare-actor-without-field"),
])
def test_no_intention_no_sentence(prepared: dict[str, Any]) -> None:
    assert "intention" not in brief(prepared, [])["situation"]


def test_jev_is_told_to_weigh_options_against_the_intention_without_ignoring_urgent_needs() -> None:
    bodies = []

    def handle(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"answers": {"wait": {"type": "score", "score": 1}}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await evaluate_actions({"actor": {"id": "ada"}, "objects": []},
                                   [{"id": "wait", "verb": "wait", "target_id": None}],
                                   {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 2.0}, client)
    asyncio.run(run())
    instructions = bodies[0]["questions"]["wait"]["instructions"]
    assert "weigh each option against their intention" in instructions
    assert "urgent need" in instructions
