"""Measures of a headless evening: activities, social outcomes, decisions, cost and stuck time."""

from collections.abc import Sequence
from typing import Any

import pytest

from tavern.evening.lockstep import Choice, Evening, Spell
from tavern.evening.metrics import completed_activities, evening_metrics, stuck_time
from tavern.evening.recording import Record, request_key


def event(kind: str, message: str, time: float = 1.0, actor_id: str | None = "ada") -> dict[str, Any]:
    """Build a logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


def done(verb: str, name: str = "Ada") -> dict[str, Any]:
    """Build the event of a completed activity."""
    return event("action_completed", f"{name} completed {verb}")


def spell(actor_id: str, start: float, end: float) -> Spell:
    """Build a stalled spell."""
    return {"actor_id": actor_id, "start": start, "end": end}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {}, id="empty-log"),
    pytest.param([done("drink")], {"drink": 1}, id="single-activity"),
    pytest.param([done("drink"), done("drink", "Bea")], {"drink": 2}, id="duplicate-verbs-add-up"),
    pytest.param([done("wait"), event("action_started", "Ada chose drink"), done("play_darts")],
                 {"play_darts": 1, "wait": 1}, id="only-completions-count-in-verb-order"),
    pytest.param([done("sit", "Ada completed")], {"sit": 1}, id="name-containing-the-phrase"),
])
def test_completed_activities_are_counted_per_verb(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert completed_activities(events) == expected


@pytest.mark.parametrize("message", [
    pytest.param("Ada finished her drink", id="malformed-message"),
    pytest.param("Ada completed ", id="empty-verb"),
    pytest.param("Ada completed Drink!", id="not-a-verb"),
])
def test_unreadable_completion_fails_loudly(message: str) -> None:
    with pytest.raises(ValueError, match="completed"):
        completed_activities([event("action_completed", message)])


@pytest.mark.parametrize("spells, guests, expected", [
    pytest.param([], [], {}, id="empty-evening"),
    pytest.param([], ["ada"], {"ada": (0.0, 0.0)}, id="guest-never-stalled"),
    pytest.param([spell("ada", 0.0, 1.1)], ["ada"], {"ada": (0.0, 1.1)}, id="single-pause-for-the-model"),
    pytest.param([spell("ada", 10.0, 15.0)], ["ada"], {"ada": (5.0, 5.0)}, id="single-stuck-spell"),
    pytest.param([spell("ada", 0.0, 4.0), spell("ada", 10.0, 14.0), spell("ada", 20.0, 21.0)], ["ada"],
                 {"ada": (8.0, 4.0)}, id="duplicate-spells-add-up"),
    pytest.param([spell("bea", 0.0, 31.0), spell("ada", 0.0, 1.0)], ["ada", "bea"],
                 {"ada": (0.0, 1.0), "bea": (31.0, 31.0)}, id="per-guest-in-guest-order"),
])
def test_stuck_time_counts_spells_longer_than_the_threshold(
        spells: list[Spell], guests: list[str], expected: dict[str, tuple[float, float]]) -> None:
    result = stuck_time(spells, guests, 3.0)
    assert (result, list(result)) == ({guest: {"seconds": pytest.approx(seconds), "longest": pytest.approx(longest)}
                                       for guest, (seconds, longest) in expected.items()}, guests)


@pytest.mark.parametrize("spells, guests, threshold", [
    pytest.param([spell("ada", 5.0, 4.0)], ["ada"], 3.0, id="malformed-spell-ends-before-it-starts"),
    pytest.param([spell("eve", 0.0, 4.0)], ["ada"], 3.0, id="spell-of-an-unknown-guest"),
    pytest.param([], ["ada"], -1.0, id="negative-threshold"),
])
def test_impossible_stuck_time_input_fails_loudly(spells: list[Spell], guests: list[str], threshold: float) -> None:
    with pytest.raises(ValueError):
        stuck_time(spells, guests, threshold)


def choice(source: str, error: str | None = None, kind: str = "actions") -> Choice:
    """Build a logged decision stage."""
    return {"time": 1.0, "actor_id": "ada", "kind": kind, "source": source, "error": error}


def call(kind: str, input_tokens: int) -> Record:
    """Build a recorded model call with reported usage."""
    request = {"observation": {}, "candidates": []}
    return {"kind": kind, "key": request_key(kind, request), "request": request, "response": {},
            "error": None, "usage": {"input_tokens": input_tokens, "output_tokens": 1}, "latency": 0.5}


def night(events: Sequence[dict[str, Any]], choices: Sequence[Choice]) -> Evening:
    """Build a finished two-guest evening."""
    return Evening(list(events), list(choices), [spell("ada", 0.0, 4.5)], ["ada", "bea"], 600.0)


def test_evening_metrics_sum_up_the_log() -> None:
    events = [done("talk"), event("conversation", "Ada and Bea chatted about darts", 9.0),
              event("conversation", "Ada and Bea chatted about darts", 9.0, "bea"),
              event("quarrel", "Ada and Bea quarreled about beer", 20.0),
              event("quarrel", "Ada and Bea quarreled about beer", 20.0, "bea"),
              event("conversation", "Ada and Bea chatted about darts", 30.0), done("leave"),
              event("departure", "Ada left the inn after 2 beers", 40.0)]
    choices = [choice("jev"), choice("jev", kind="seats"), choice("local", "Jev request timed out")]
    metrics = evening_metrics(night(events, choices), [call("actions", 2_000_000), call("seats", 1_000_000)], 0.042, 3.0)
    assert {**metrics, "cost": {kind: item["usd"] for kind, item in metrics["cost"].items()}} == {
        "game_seconds": 600.0, "guests": 2, "departures": 1, "completed": {"leave": 1, "talk": 1},
        "conversations": 2, "quarrels": 1, "decisions": {"jev": 2, "local": 1}, "errors": 1,
        "cost": {"actions": pytest.approx(0.084), "seats": pytest.approx(0.042)},
        "stuck": {"ada": {"seconds": 4.5, "longest": 4.5}, "bea": {"seconds": 0.0, "longest": 0.0}}}
