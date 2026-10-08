"""Manners in the evening metrics: seats taken, tables sat down at uninvited, and apologies."""

from typing import Any

import pytest

from tavern.evening.manner_metrics import manner_counts


def event(kind: str, message: str = "x", actor_id: str = "ada", time: float = 1.0) -> dict[str, Any]:
    """A logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


def counts(**fields: int) -> dict[str, int]:
    """The counts of an evening without any manners to speak of, with some fields changed."""
    return {"seats_taken": 0, "table_intrusions": 0, "apologies": 0, **fields}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], counts(), id="empty"),
    pytest.param([event("seat_taken")], counts(seats_taken=1), id="a-seat-taken"),
    pytest.param([event("table_intruded")], counts(table_intrusions=1), id="an-intrusion"),
    pytest.param([event("table_intruded", "Ada sat down at Cid's table uninvited (Far table)", "cid"),
                  event("table_intruded", "Ada sat down at Dan's table uninvited (Far table)", "dan")],
                 counts(table_intrusions=2), id="an-intrusion-upsets-each-host"),
    pytest.param([event("sat_uninvited"), event("table_intruded")], counts(table_intrusions=1),
                 id="the-newcomers-own-memory-is-not-a-second-intrusion"),
    pytest.param([event("apologized", "Ada apologized to Bea", "ada"), event("apologized", "Ada apologized to Bea", "bea")],
                 counts(apologies=1), id="an-apology-is-logged-twice-and-counted-once"),
    pytest.param([event("apologized", "Ada apologized to Bea", time=1.0), event("apologized", "Ada apologized to Bea", time=50.0)],
                 counts(apologies=2), id="the-same-apology-at-two-times"),
    pytest.param([event("quarrel"), event("seat_taken"), event("table_intruded"), event("apologized")],
                 counts(seats_taken=1, table_intrusions=1, apologies=1), id="mixed-with-other-events"),
])
def test_manners_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert manner_counts(events) == expected
