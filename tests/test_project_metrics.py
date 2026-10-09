"""Projects in the evening metrics: how many ended how."""

from typing import Any

import pytest

from tavern.evening.project_metrics import project_counts


def ended(outcome: str, kind: str = "settle_in") -> dict[str, Any]:
    """A logged project end."""
    return {"time": 1.0, "actor_id": "ada", "type": f"project_{outcome}", "message": f"Ada did it ({kind})"}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"started": 0, "by_kind": {}}, id="empty"),
    pytest.param([ended("done")], {"started": 1, "by_kind": {"settle_in": {"done": 1, "failed": 0, "dropped": 0, "expired": 0}}},
                 id="one-done"),
    pytest.param([ended("done"), ended("failed"), ended("failed"), ended("dropped"), ended("expired")],
                 {"started": 5, "by_kind": {"settle_in": {"done": 1, "failed": 2, "dropped": 1, "expired": 1}}},
                 id="every-outcome-and-duplicates"),
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "talk", "message": "x"}], {"started": 0, "by_kind": {}},
                 id="other-events-ignored"),
])
def test_projects_are_counted(events: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert project_counts(events) == expected


@pytest.mark.parametrize("message", [
    pytest.param("Ada did it", id="no-kind"),
    pytest.param("Ada did it (dance)", id="unknown-kind"),
])
def test_a_project_event_that_cannot_be_read_fails_loudly(message: str) -> None:
    with pytest.raises(ValueError):
        project_counts([{"time": 1.0, "actor_id": "ada", "type": "project_done", "message": message}])
