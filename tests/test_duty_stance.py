"""A barkeep on duty takes stock like a guest, within his duties: no goal that takes him from the bar."""

from typing import Any

import pytest
from staff_hall import HOB, hob_of, opened

from tavern.mind.goals import GOALS
from tavern.mind.intentions import INTENTION_RULES, intention_due, intention_question, intention_requests, \
    intention_view, parse_stance

OTHERS = {"ada": "Ada", "bea": "Bea"}
THOUGHT = {"thought": "A quiet bar.", "intention": "Keep the mugs full."}


def barkeeps_view() -> dict[str, Any]:
    """What Hob's mind is shown on arrival."""
    world = opened(HOB)
    hob = hob_of(world)
    return intention_view(world, hob, intention_due(world, hob, INTENTION_RULES))  # type: ignore[arg-type]


def test_the_barkeeps_mind_is_asked_like_a_guests() -> None:
    world = opened(HOB)
    assert "hob" in [actor_id for actor_id, _ in intention_requests(world, set(), {}, INTENTION_RULES)]


def test_the_barkeeps_view_names_his_post() -> None:
    assert barkeeps_view()["duty"] == "Oak bar"


def test_a_guests_view_has_no_duty() -> None:
    world = opened(HOB)
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    assert intention_view(world, ada, intention_due(world, ada, INTENTION_RULES))["duty"] is None  # type: ignore[arg-type]


def test_the_question_to_a_barkeep_says_he_is_at_work() -> None:
    content = intention_question("PREFIX", barkeeps_view())["content"]
    assert "on duty behind the Oak bar" in content


@pytest.mark.parametrize("goal, on_duty, expected", [
    pytest.param("talk_to", True, "talk_to", id="a-barkeep-talks-with-those-at-his-bar"),
    pytest.param("sit_with", False, "sit_with", id="a-guest-sits-with-someone"),
    pytest.param("none", True, None, id="no-goal-on-duty"),
])
def test_a_stance_within_the_duties_is_kept(goal: str, on_duty: bool, expected: str | None) -> None:
    answer = {**THOUGHT, "goal": goal, "target": None if goal == "none" else "ada"}
    written = parse_stance(answer, OTHERS, on_duty=on_duty)
    assert (written.get("goal") or {}).get("kind") == expected


def test_a_barkeep_cannot_set_out_to_sit_at_a_table() -> None:
    with pytest.raises(ValueError, match="on duty"):
        parse_stance({**THOUGHT, "goal": "sit_with", "target": "ada"}, OTHERS, on_duty=True)


def test_only_goals_that_keep_a_man_at_his_bar_are_open_to_him() -> None:
    assert [kind for kind, goal in GOALS.items() if goal.on_duty] == ["talk_to"]
