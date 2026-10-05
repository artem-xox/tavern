"""A guest whose best option is a poor one stops, and their mind is asked what they want."""

from typing import Any

import pytest

from tavern.evening.decisions import UNSURE_BELOW, apply_decision
from tavern.evening.goal_metrics import unsure_count
from tavern.hall.world import create_world
from tavern.mind.intentions import INTENTION_RULES, intention_due

HALL = {"width": 10, "height": 6, "blocked": [], "objects": [
    {"id": "darts", "kind": "darts", "name": "Darts", "x": 5, "y": 2, "interaction_spots": [[5, 3]]},
    {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 5, "interaction_spots": [[0, 4]]}],
    "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}]}
DARTS = {"id": "play_darts:darts", "verb": "play_darts", "target_id": "darts"}
WAIT = {"id": "wait", "verb": "wait", "target_id": None}


def decided(scores: dict[str, float], source: str = "jev", action: dict[str, Any] = DARTS,
            error: str | None = None, closed: bool = False, stages: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ada applies a decision; return the world."""
    world = create_world(HALL)
    if closed:
        world["closes_at"] = 0.0
    ada = world["actors"][0]
    apply_decision(world, ada, lambda: {"action": action, "source": source, "scores": scores, "error": error,
                                        **(stages or {})})
    return world


def verb_of(world: dict[str, Any]) -> str | None:
    """What Ada is doing."""
    action = world["actors"][0]["action"]
    return action["verb"] if action else None


def doubts(world: dict[str, Any]) -> list[str]:
    """Ada's remembered doubts."""
    return [event["type"] for event in world["actors"][0]["memory"] if event["type"] == "unsure"]


@pytest.mark.parametrize("scores, expected_verb, unsure", [
    pytest.param({"play_darts:darts": 0.9, "wait": 0.1}, "play_darts", False, id="a-clear-favourite"),
    pytest.param({"play_darts:darts": UNSURE_BELOW, "wait": 0.1}, "play_darts", False, id="exactly-at-the-line"),
    pytest.param({"play_darts:darts": UNSURE_BELOW - 0.01, "wait": 0.1}, "wait", True, id="just-under-the-line"),
    pytest.param({"play_darts:darts": 0.0}, "wait", True, id="nothing-scores"),
    pytest.param({}, "play_darts", False, id="no-scores-at-all"),
])
def test_a_jev_decision_with_no_good_option_becomes_a_pause_and_a_doubt(scores: dict[str, float],
                                                                         expected_verb: str, unsure: bool) -> None:
    world = decided(scores)
    assert (verb_of(world), doubts(world) == ["unsure"]) == (expected_verb, unsure)


@pytest.mark.parametrize("kwargs", [
    pytest.param({"source": "local"}, id="a-local-score-is-not-calibrated"),
    pytest.param({"error": "Jev HTTP 500"}, id="a-failed-model-call"),
    pytest.param({"action": WAIT}, id="already-waiting"),
    pytest.param({"closed": True}, id="closing-time-goes-home"),
])
def test_only_a_real_doubt_pauses_a_guest(kwargs: dict[str, Any]) -> None:
    assert doubts(decided({"play_darts:darts": 0.1}, **kwargs)) == []


def test_a_poor_second_stage_is_a_doubt_too() -> None:
    stages = {"family": {"name": "pastime", "source": "jev", "scores": {"play_darts:darts": 0.2}, "error": None}}
    assert doubts(decided({"pastime": 0.9}, stages=stages)) == ["unsure"]


def test_a_poor_seat_choice_is_no_doubt() -> None:
    stages = {"seat": {"source": "jev", "scores": {"sit:w1": 0.1}, "error": None}}
    assert doubts(decided({"pastime": 0.9}, stages=stages)) == []


def test_a_doubt_makes_the_guest_take_stock() -> None:
    world = decided({"play_darts:darts": 0.2})
    ada = world["actors"][0]
    ada["intention"] = {"thought": "Hm.", "intention": "Stay.", "goal": None, "written_at": -1.0,
                        "trigger": {"kind": "arrival", "text": "Came in", "time": -1.0}}
    world["time"] = 5.0
    trigger = intention_due(world, ada, INTENTION_RULES)
    assert trigger is not None and trigger["kind"] == "unsure"


def test_doubts_are_counted() -> None:
    events = [{"type": "unsure", "time": 1.0, "actor_id": "ada", "message": "x"}, {"type": "turn"}] * 2
    assert unsure_count(events) == 2
    assert unsure_count([]) == 0


@pytest.mark.parametrize("later, expected", [
    pytest.param(5.0, ["play_darts"], id="still-thinking-so-no-second-pause"),
    pytest.param(29.0, ["play_darts"], id="just-inside-the-cooldown"),
    pytest.param(31.0, ["wait"], id="cooled-down-so-doubt-again"),
])
def test_a_guest_who_just_doubted_is_not_paused_again_while_their_mind_works(later: float, expected: list[str]) -> None:
    world = decided({"play_darts:darts": 0.2})
    ada = world["actors"][0]
    ada.update(action=None, status="idle")
    world["time"] = later
    apply_decision(world, ada, lambda: {"action": DARTS, "source": "jev", "scores": {"play_darts:darts": 0.2},
                                        "error": None})
    assert [ada["action"]["verb"]] == expected
