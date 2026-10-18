"""Goals in the evening metrics: set, done, failed and expired."""

from typing import Any

import pytest

from tavern.evening.goal_metrics import chased_counts, goal_counts, goal_kind_counts, promise_counts


def event(kind: str) -> dict[str, Any]:
    """A logged event."""
    return {"time": 1.0, "actor_id": "ada", "type": kind, "message": f"ada: {kind}"}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"set": 0, "done": 0, "failed": 0, "expired": 0}, id="empty"),
    pytest.param([event("goal_set")], {"set": 1, "done": 0, "failed": 0, "expired": 0}, id="single"),
    pytest.param([event("goal_set"), event("goal_set"), event("goal_done"), event("goal_done")],
                 {"set": 2, "done": 2, "failed": 0, "expired": 0}, id="duplicates"),
    pytest.param([event("goal_failed"), event("turn"), event("goal_expired")],
                 {"set": 0, "done": 0, "failed": 1, "expired": 1}, id="mixed-with-other-events"),
])
def test_goals_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert goal_counts(events) == expected


def test_malformed_event_fails_loudly() -> None:
    with pytest.raises(KeyError):
        goal_counts([{"time": 1.0, "message": "no type"}])


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"made": 0, "kept": 0, "broken": 0, "void": 0}, id="empty"),
    pytest.param([event("promise_made")], {"made": 1, "kept": 0, "broken": 0, "void": 0}, id="single"),
    pytest.param([event("promise_made"), event("promise_made"), event("promise_kept"), event("promise_kept")],
                 {"made": 2, "kept": 2, "broken": 0, "void": 0}, id="duplicates"),
    pytest.param([event("promise_broken"), event("turn"), event("promise_void")],
                 {"made": 0, "kept": 0, "broken": 1, "void": 1}, id="mixed-with-other-events"),
])
def test_promises_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert promise_counts(events) == expected


def test_a_promise_event_without_a_type_fails_loudly() -> None:
    with pytest.raises(KeyError):
        promise_counts([{"time": 1.0, "message": "no type"}])


def setting(message: str) -> dict[str, Any]:
    """A logged goal set out."""
    return {"time": 1.0, "actor_id": "ada", "type": "goal_set", "message": message}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {}, id="empty"),
    pytest.param([setting("Ada set out to talk with Bea")], {"talk_to": 1}, id="single"),
    pytest.param([setting("Ada set out to play a game of dice with Bea"),
                  setting("Cy set out to play a game of dice with Ada")], {"play_with": 2}, id="duplicates"),
    pytest.param([setting("Ada set out to buy Bea an ale"), setting("Ada set out to have it out with Cy"),
                  setting("Ada set out to sit at the same table as Bea"), event("goal_done")],
                 {"treat": 1, "have_it_out": 1, "sit_with": 1}, id="every-kind-and-other-events"),
])
def test_goals_are_counted_by_kind(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert goal_kind_counts(events) == expected


def test_a_goal_in_words_the_table_lacks_fails_loudly() -> None:
    with pytest.raises(ValueError):
        goal_kind_counts([setting("Ada set out to fetch the moon")])


def intention(who: str, tail: str = "") -> dict[str, Any]:
    """A logged intention, with what it chases when told."""
    return {"time": 1.0, "actor_id": who, "type": "intention",
            "message": f"{who} thinks: Hm. Intends: Stay. (after: arrival){tail}"}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {}, id="empty"),
    pytest.param([intention("ada", " Chasing: get someone else to pay.")], {"ada": 1}, id="single"),
    pytest.param([intention("ada", " Chasing: a."), intention("ada", " Chasing: b."), intention("bea", " Chasing: a.")],
                 {"ada": 2, "bea": 1}, id="duplicates-and-two-guests"),
    pytest.param([intention("ada"), event("goal_set")], {}, id="an-intention-that-chases-nothing"),
])
def test_intentions_that_chase_an_obsession_are_counted_by_guest(events: list[dict[str, Any]],
                                                                 expected: dict[str, int]) -> None:
    assert chased_counts(events) == expected
