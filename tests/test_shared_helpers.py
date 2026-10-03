"""Spec of the small helpers shared across modules: integer checks, finding visitors, logging events."""

import pytest

from tavern.hall.memory import log_event
from tavern.hall.state import find_actor
from tavern.hall.validation import integer


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
