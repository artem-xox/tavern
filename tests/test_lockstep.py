"""Headless evenings in lockstep: virtual model latency, the runtime's decision rules, replay."""

import asyncio
from collections.abc import Sequence
from itertools import count
from random import Random
from typing import Any

import pytest

from tavern.agents import Evaluator, Evaluators
from tavern.jev import JevError
from tavern.lockstep import Evening, Pace, evening_mode, evening_over, run_evening
from tavern.recording import Record, format_record, parse_records, record_calls, replay_calls
from tavern.world import create_world, start_action, step_world

KEYED = {"typesafe_api_key": "fake", "model": "jev-latest", "timeout": 1.0, "temperature": 0.0}


def hall(guests: Sequence[str] = ("ada", "bea")) -> dict[str, Any]:
    """Build a 9×6 hall with a door, a tap and one two-chair table, and the named guests."""
    def chair(side: str, x: int) -> dict[str, Any]:
        return {"id": f"table-{side}", "kind": "chair", "name": f"Table · {side}", "x": x, "y": 2,
                "walkable": True, "table_id": "table", "interaction_spots": [[x, 2]]}
    places = {"ada": (1, 4), "bea": (7, 4)}
    return {"width": 9, "height": 6, "blocked": [], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 8, "y": 0, "interaction_spots": [[7, 0]], "stock": 20},
        {"id": "table", "kind": "table", "name": "Table", "x": 4, "y": 2}, chair("west", 3), chair("east", 5),
    ], "actors": [{"id": guest, "name": guest.title(), "x": places[guest][0], "y": places[guest][1]}
                  for guest in guests]}


def preferring(verbs: dict[str, str] | str) -> Evaluator:
    """Build a fake evaluator that scores one verb highest, per guest name or for everyone."""
    async def evaluate(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        verb = verbs if isinstance(verbs, str) else verbs.get(view["self"]["name"], "wait")
        return {action["id"]: float(action["verb"] == verb) for action in candidates}
    return evaluate


def evening(evaluate: Evaluator, guests: Sequence[str] = ("ada", "bea"), latency: float = 1.0,
            limit: float = 60.0, world: dict[str, Any] | None = None) -> tuple[Evening, dict[str, Any]]:
    """Run a headless evening in the hall with one evaluator for both decision stages."""
    world = world or create_world(hall(guests), 3)
    result = asyncio.run(run_evening(world, KEYED, Random(3), Evaluators(evaluate, evaluate),
                                     Pace(step=0.1, model_latency=latency, time_limit=limit)))
    return result, world


def first(result: Evening, actor_id: str, kind: str = "action_started", after: float = -1.0) -> dict[str, Any]:
    """Find a guest's first event of a kind after a game time."""
    return next(event for event in result.events
                if event["actor_id"] == actor_id and event["type"] == kind and event["time"] > after)


@pytest.mark.parametrize("guests, time, limit, over", [
    pytest.param([], 0.0, 60.0, True, id="empty-hall-everyone-left"),
    pytest.param(["ada"], 10.0, 60.0, False, id="single-guest-before-the-limit"),
    pytest.param(["ada", "bea"], 10.0, 60.0, False, id="duplicate-guests-before-the-limit"),
    pytest.param(["ada"], 60.0, 60.0, True, id="time-limit-reached"),
])
def test_evening_ends_when_everyone_left_or_time_is_up(
        guests: list[str], time: float, limit: float, over: bool) -> None:
    world = create_world(hall(guests))
    world["time"] = time
    assert evening_over(world, limit) is over


@pytest.mark.parametrize("pace", [
    pytest.param({"step": 0.0, "model_latency": 1.0, "time_limit": 60.0}, id="empty-step"),
    pytest.param({"step": 0.1, "model_latency": -1.0, "time_limit": 60.0}, id="negative-latency"),
    pytest.param({"step": 0.1, "model_latency": 1.0, "time_limit": 0.0}, id="no-time-at-all"),
    pytest.param({"step": float("nan"), "model_latency": 1.0, "time_limit": 60.0}, id="malformed-step"),
])
def test_invalid_pace_fails_loudly(pace: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        Pace(**pace)


@pytest.mark.parametrize("latency, started", [
    pytest.param(0.0, 0.2, id="instant-model-acts-next-tick"),
    pytest.param(0.5, 0.6, id="half-second-model"),
    pytest.param(2.0, 2.1, id="slow-model"),
])
def test_decision_takes_effect_after_the_virtual_model_latency(latency: float, started: float) -> None:
    result, _world = evening(preferring("wait"), ["ada"], latency, limit=5.0)
    event = first(result, "ada")
    assert (event["time"], event["message"]) == (pytest.approx(started), "Ada chose wait")


def test_wall_clock_speed_of_the_model_does_not_change_the_evening() -> None:
    instant = preferring("wait")

    async def slow(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        for _ in range(len(candidates) * 3):
            await asyncio.sleep(0)
        return await instant(view, candidates, settings)
    assert evening(slow)[0] == evening(instant)[0]


def seated_pair() -> dict[str, Any]:
    """Seat Bea and Ada at the table; Bea is listed first, so her answers apply first."""
    world = create_world(hall(["bea", "ada"]), 3)
    for actor_id, seat in (("ada", "table-west"), ("bea", "table-east")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    for _ in range(300):
        step_world(world, 0.1)
    return world


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def test_partner_is_not_pulled_from_a_chat_by_a_late_answer() -> None:
    world = seated_pair()
    seated = world["time"]
    result, _world = evening(preferring({"Bea": "talk", "Ada": "wait"}), limit=60.0, world=world)
    answered = [item for item in result.choices if item["actor_id"] == "ada"]
    acted = [event for event in result.events if event["actor_id"] == "ada"
             and event["type"] == "action_started" and event["time"] > seated]
    assert (first(result, "bea", after=seated)["message"], len(answered) > 1, acted) == ("Bea chose talk", True, [])


def test_complete_event_log_outlives_the_worlds_trimmed_log() -> None:
    result, world = evening(preferring("wait"), latency=0.0, limit=120.0)
    assert (len(result.events) > 200, len(world["events"]) <= 200) == (True, True)
    assert (result.events[0]["time"], result.events[-len(world["events"]):]) == (
        pytest.approx(0.2), world["events"])


@pytest.mark.parametrize("verb, early, staying", [
    pytest.param("leave", True, [], id="everyone-leaves"),
    pytest.param("wait", False, ["ada", "bea"], id="time-limit-ends-it"),
])
def test_evening_runs_until_everyone_left_or_the_limit(verb: str, early: bool, staying: list[str]) -> None:
    result, world = evening(preferring(verb), limit=60.0)
    assert (result.end_time < 60.0, [actor["id"] for actor in world["actors"]], result.guests) == (
        early, staying, ["ada", "bea"])


@pytest.mark.parametrize("latency, still_until", [
    pytest.param(0.0, 0.2, id="instant-model"),
    pytest.param(1.0, 1.1, id="one-second-model"),
    pytest.param(2.5, 2.6, id="slow-model"),
])
def test_standing_without_an_action_is_logged_as_a_spell(latency: float, still_until: float) -> None:
    result, _world = evening(preferring("leave"), ["ada"], latency)
    assert result.spells == [{"actor_id": "ada", "start": 0.0, "end": pytest.approx(still_until)}]


async def timing_out(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
    """Fail like the Jev adapter does on a timeout."""
    raise JevError("Jev request timed out")


@pytest.mark.parametrize("evaluate, sources", [
    pytest.param(preferring("wait"), {("actions", "jev", None)}, id="model-answers"),
    pytest.param(timing_out, {("actions", "local", "Jev request timed out"), ("seats", "local", "Jev request timed out")},
                 id="model-fails-and-local-policy-picks-a-seat"),
])
def test_every_choice_is_logged_with_its_source(evaluate: Evaluator, sources: set[tuple[Any, ...]]) -> None:
    result, _world = evening(evaluate, ["ada"], limit=10.0)
    assert {(item["kind"], item["source"], item["error"]) for item in result.choices} == sources


def sampling(fail_every: int) -> Any:
    """A fake metered model whose scores change on every call, failing every n-th call.

    It never sends anyone home, so the evening runs to its time limit.
    """
    calls = count(1)

    async def evaluate(view: Any, candidates: Sequence[Any], settings: Any) -> Any:
        turn = next(calls)
        if turn % fail_every == 0:
            raise JevError("Jev HTTP 500")
        scores = {action["id"]: 0.0 if action["verb"] == "leave" else Random(f"{turn}:{action['id']}").random()
                  for action in candidates}
        return scores, {"input_tokens": 100 * len(candidates), "output_tokens": len(candidates)}
    return evaluate


def ticking() -> Any:
    """A fake clock that advances a quarter second per reading."""
    readings = count(0.0, 0.25)
    return lambda: next(readings)


def run(evaluators: Evaluators) -> Evening:
    """Run a two-guest evening with a sampling temperature, so the random draws matter too."""
    return asyncio.run(run_evening(create_world(hall(), 5), {**KEYED, "temperature": 0.25}, Random(5), evaluators,
                                   Pace(step=0.1, model_latency=1.0, time_limit=180.0)))


@pytest.mark.parametrize("fail_every", [
    pytest.param(10_000, id="every-call-answered"),
    pytest.param(4, id="some-calls-fail"),
])
def test_recorded_evening_replays_to_an_identical_event_log(fail_every: int) -> None:
    records: list[Record] = []
    model = sampling(fail_every)
    live = run(Evaluators(record_calls("actions", model, records.append, ticking(), JevError),
                          record_calls("seats", model, records.append, ticking(), JevError)))
    stored = parse_records("".join(map(format_record, records)))
    replay = run(Evaluators(replay_calls("actions", stored, JevError), replay_calls("seats", stored, JevError)))
    assert (replay.events, replay.choices, replay.spells) == (live.events, live.choices, live.spells)
    assert (len(live.events) > 20, {item["kind"] for item in records}) == (True, {"actions", "seats"})


@pytest.mark.parametrize("requested, keyed, expected", [
    pytest.param(None, True, ("live", None), id="default-is-live-with-a-key"),
    pytest.param(None, False, ("local", "No TYPESAFE_API_KEY in .env, so the labeled local policy decides"),
                 id="default-falls-back-to-local-without-a-key"),
    pytest.param("local", True, ("local", None), id="local-on-request"),
    pytest.param("replay", False, ("replay", None), id="replay-needs-no-key"),
    pytest.param("live", True, ("live", None), id="live-on-request"),
])
def test_mode_defaults_to_live_when_a_key_is_present(
        requested: str | None, keyed: bool, expected: tuple[str, str | None]) -> None:
    assert evening_mode(requested, keyed) == expected


@pytest.mark.parametrize("requested, keyed", [
    pytest.param("live", False, id="live-without-a-key"),
    pytest.param("", True, id="empty-mode"),
    pytest.param("jev", True, id="unknown-mode"),
])
def test_impossible_mode_fails_loudly(requested: str, keyed: bool) -> None:
    with pytest.raises(ValueError, match="mode"):
        evening_mode(requested, keyed)
