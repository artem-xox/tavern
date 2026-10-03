"""A new world gets its own copy of the game's rules, with one duration per timed verb."""

import pytest

from tavern.activities import ACTIVITIES
from tavern.rules import default_rules


def test_every_timed_verb_has_its_duration_and_decision_steps_have_none() -> None:
    durations = default_rules()["durations"]
    assert durations == {verb: item.duration for verb, item in ACTIVITIES.items() if item.duration is not None}
    assert all(verb not in durations for verb, item in ACTIVITIES.items() if item.duration is None)


@pytest.mark.parametrize("path", [
    pytest.param(("need_rates", "thirst"), id="needs"),
    pytest.param(("attention", "glance"), id="attention"),
    pytest.param(("conversation", "reach"), id="conversation"),
])
def test_each_call_returns_rules_nobody_else_holds(path: tuple[str, str]) -> None:
    mine, theirs = default_rules(), default_rules()
    mine[path[0]][path[1]] = -1
    assert theirs[path[0]][path[1]] != -1
