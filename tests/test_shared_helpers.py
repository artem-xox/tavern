"""Spec of the small helpers shared across modules: integer checks, finding visitors, logging events."""

import pytest

from tavern.hall.memory import fresh_events, log_event, record_event
from tavern.hall.state import find_actor
from tavern.hall.validation import integer
from tavern.hall.world import create_world


@pytest.mark.parametrize("value, expected", [
    pytest.param(5, 5, id="inside"),
    pytest.param(1, 1, id="lower-bound"),
    pytest.param(10, 10, id="upper-bound"),
])
def test_integer_accepts_whole_numbers_in_range(value: int, expected: int) -> None:
    assert integer(value, "Amount", 1, 10) == expected


@pytest.mark.parametrize("value, message", [
    pytest.param(0, "Amount must be between", id="below"),
    pytest.param(11, "Amount must be between", id="above"),
    pytest.param(2.5, "Amount must be an integer", id="fraction"),
    pytest.param(True, "Amount must be an integer", id="bool"),
    pytest.param("3", "Amount must be an integer", id="text"),
    pytest.param(None, "Amount must be an integer", id="missing"),
])
def test_integer_rejects_everything_else(value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        integer(value, "Amount", 1, 10)


@pytest.mark.parametrize("actor_id, found", [
    pytest.param("bea", "bea", id="present"),
    pytest.param("zed", None, id="absent"),
    pytest.param(None, None, id="no-id"),
])
def test_find_actor_by_id(actor_id: object, found: str | None) -> None:
    world = {"actors": [{"id": "ann"}, {"id": "bea"}]}
    actor = find_actor(world, actor_id)
    assert (actor["id"] if actor else None) == found


def test_find_actor_in_an_empty_hall() -> None:
    assert find_actor({"actors": []}, "ann") is None


def test_log_event_keeps_the_latest_200() -> None:
    world = {"time": 3.0, "events": [{"n": index} for index in range(200)]}
    log_event(world, "ann", "turn", "Ann spoke")
    assert len(world["events"]) == 200
    assert world["events"][-1] == {"time": 3.0, "actor_id": "ann", "type": "turn", "message": "Ann spoke"}


def _hall() -> dict:
    return create_world({"width": 4, "height": 3, "blocked": [], "objects": [],
                         "actors": [{"id": "ann", "name": "Ann", "x": 1, "y": 1}]})


@pytest.mark.parametrize("log", [
    pytest.param(lambda world: record_event(world, world["actors"][0], "turn", "Ann spoke"), id="record-event"),
    pytest.param(lambda world: log_event(world, "ann", "turn", "Ann spoke"), id="log-event"),
])
def test_logging_returns_the_event_it_appended(log) -> None:
    world = _hall()
    assert log(world) is world["events"][-1]


def test_record_event_fields_reach_the_logged_event_and_the_memory() -> None:
    world = _hall()
    ann = world["actors"][0]
    event = record_event(world, ann, "action_started", "Ann chose talk", fields={"verb": "talk"})
    assert event["verb"] == "talk"
    assert world["events"][-1]["verb"] == "talk"
    assert ann["memory"][-1]["verb"] == "talk"


def _log() -> list[dict]:
    return [{"n": 1}, {"n": 2}, {"n": 3}]


@pytest.mark.parametrize("last, expected", [
    pytest.param(None, [{"n": 1}, {"n": 2}, {"n": 3}], id="no-last-takes-all"),
    pytest.param(0, [{"n": 2}, {"n": 3}], id="last-in-the-middle-of-the-log"),
    pytest.param(2, [], id="last-at-the-end"),
])
def test_fresh_events_follow_the_last_one_seen(last: int | None, expected: list[dict]) -> None:
    events = _log()
    assert fresh_events(events, None if last is None else events[last]) == expected


@pytest.mark.parametrize("last", [
    pytest.param({"n": 0}, id="trimmed-away"),
    pytest.param({"n": 2}, id="equal-but-not-identical"),
])
def test_fresh_events_say_none_when_the_last_one_is_not_in_the_log(last: dict) -> None:
    assert fresh_events(_log(), last) is None


def test_fresh_events_of_an_empty_log() -> None:
    assert fresh_events([], None) == []
