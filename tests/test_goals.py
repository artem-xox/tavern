"""Goals: what a guest's mind may set out to do, the options that serve it, and how it ends."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.goals import check_goal, serving, settle_goals
from tavern.mind.intentions import INTENTION_RULES, intention_due, intention_view, parse_stance
from tavern.mind.local_policy import GOAL_BONUS, local_scores


def chair(chair_id: str, table: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at a table."""
    return {"id": chair_id, "kind": "chair", "name": f"{table} · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": table, "interaction_spots": [[x, y]]}


def hall() -> dict[str, Any]:
    """Two tables: Bea sits at the first, with a chair free; Cy at the second; Ada stands apart."""
    return {"width": 14, "height": 6, "blocked": [], "objects": [
        {"id": "t1", "kind": "table", "name": "West table", "x": 2, "y": 2, "width": 2, "height": 1},
        {"id": "t2", "kind": "table", "name": "East table", "x": 9, "y": 2, "width": 2, "height": 1},
        chair("w1", "t1", 1, 2), chair("w2", "t1", 4, 2), chair("e1", "t2", 8, 2), chair("e2", "t2", 11, 2)],
        "actors": [{"id": "ada", "name": "Ada", "x": 6, "y": 4}, {"id": "bea", "name": "Bea", "x": 1, "y": 2},
                   {"id": "cy", "name": "Cy", "x": 8, "y": 2}]}


def goal(kind: str = "talk_to", target: str | None = "bea", status: str = "active") -> dict[str, Any]:
    """A goal."""
    return {"kind": kind, "target": target, "status": status}


def minded(kind: str = "talk_to", target: str | None = "bea", status: str = "active", at: float = 0.0,
           sat: tuple[str, ...] = ("bea:w1", "cy:e2")) -> dict[str, Any]:
    """The hall where Ada, seated nowhere, holds a goal written at a game time; others sit as told."""
    world = create_world(hall())
    for seating in sat:
        who, seat = seating.split(":")
        assert start_action(world, who, {"id": f"sit:{seat}", "verb": "sit", "target_id": seat})["accepted"]
    for _ in range(300):
        step_world(world, 0.1)
    next(item for item in world["actors"] if item["id"] == "ada")["intention"] = {
        "thought": "Hm.", "intention": "Talk to someone.", "goal": goal(kind, target, status), "written_at": at,
        "trigger": {"kind": "arrival", "text": "Ada came in", "time": at}}
    return world


def action(verb: str, target: str | None) -> dict[str, Any]:
    """A concrete action."""
    return {"id": f"{verb}:{target}", "verb": verb, "target_id": target}


def view(world: dict[str, Any]) -> dict[str, Any]:
    """Ada's observation, with the people she sees."""
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}


@pytest.mark.parametrize("kind, target, status, act, expected", [
    pytest.param("talk_to", "bea", "active", action("talk", "bea"), True, id="talk-to-the-person"),
    pytest.param("talk_to", "bea", "active", action("join_conversation", "bea"), True, id="join-the-person"),
    pytest.param("talk_to", "bea", "active", action("talk", "cy"), False, id="talk-to-someone-else"),
    pytest.param("talk_to", "bea", "active", action("approach", "bea"), True, id="walk-over-to-the-person"),
    pytest.param("talk_to", "bea", "active", action("approach", "cy"), False, id="walk-over-to-someone-else"),
    pytest.param("talk_to", "bea", "active", action("sit", "w2"), False, id="sit-at-their-table-uninvited"),
    pytest.param("talk_to", "bea", "active", action("sit", "e1"), False, id="sit-at-another-table"),
    pytest.param("talk_to", "bea", "done", action("talk", "bea"), False, id="a-done-goal-serves-nothing"),
    pytest.param("sit_with", "cy", "active", action("sit", "e1"), True, id="sit-with-at-their-table"),
    pytest.param("sit_with", "cy", "active", action("talk", "cy"), False, id="chat-is-not-sitting-with"),
    pytest.param("sit_with", "bea", "active", action("wait", None), False, id="waiting-serves-nothing"),
])
def test_an_option_serves_a_goal_or_not(kind: str, target: str, status: str, act: dict[str, Any],
                                        expected: bool) -> None:
    assert serving(view(minded(kind, target, status)), act) is expected


def test_a_family_serves_a_goal_when_a_member_does() -> None:
    family = {"id": "company", "verb": "company", "target_id": None,
              "members": [action("talk", "cy"), action("talk", "bea")]}
    assert serving(view(minded()), family) is True


def test_a_guest_without_a_goal_is_served_by_nothing() -> None:
    world = minded()
    next(item for item in world["actors"] if item["id"] == "ada")["intention"]["goal"] = None
    assert serving(view(world), action("talk", "bea")) is False


def test_the_briefing_marks_the_options_that_serve_the_goal() -> None:
    observation = view(minded("sit_with"))
    options = brief(observation, build_candidates(observation))["options"]
    assert [key for key, text in options.items() if "serves the goal" in text] == ["seating"]


def test_the_local_policy_adds_a_bonus_to_options_that_serve_the_goal() -> None:
    world = minded("sit_with")
    observation = view(world)
    sat = action("sit", "w2")
    without = {**observation, "actor": {**observation["actor"], "intention": None}}
    assert local_scores(observation, [sat])[sat["id"]] == pytest.approx(
        min(1.0, local_scores(without, [sat])[sat["id"]] + GOAL_BONUS))


def settled(world: dict[str, Any], time: float) -> list[str]:
    """Settle the goals at a game time and list the events remembered about them."""
    world["time"] = time
    settle_goals(world)
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    return [ada["intention"]["goal"]["status"], *(e["type"] for e in ada["memory"] if e["type"].startswith("goal_"))]


def spoke(world: dict[str, Any], speaker: str, at: float) -> dict[str, Any]:
    """Ada heard a line from a guest at a game time."""
    next(item for item in world["actors"] if item["id"] == "ada")["heard"].append(
        {"time": at, "scene_id": "c1", "speaker_id": speaker, "speaker": speaker, "line": "Evening.", "act": "greet"})
    return world


@pytest.mark.parametrize("prepare, time, expected", [
    pytest.param(lambda: minded(), 10.0, ["active"], id="nothing-yet"),
    pytest.param(lambda: spoke(minded(), "bea", 5.0), 10.0, ["done", "goal_done"], id="a-line-from-the-person"),
    pytest.param(lambda: spoke(minded(), "cy", 5.0), 10.0, ["active"], id="a-line-from-someone-else"),
    pytest.param(lambda: spoke(minded(at=8.0), "bea", 5.0), 10.0, ["active"], id="a-line-from-before-the-goal"),
    pytest.param(lambda: minded(), 241.0, ["expired", "goal_expired"], id="the-time-passed"),
    pytest.param(lambda: minded("sit_with", "cy", at=0.0), 130.0, ["expired", "goal_expired"], id="sitting-lapses"),
    pytest.param(lambda: minded(status="done"), 500.0, ["done"], id="an-ended-goal-stays-ended"),
])
def test_goals_end_once_the_world_decides(prepare: Any, time: float, expected: list[str]) -> None:
    assert settled(prepare(), time) == expected


def test_a_goal_about_someone_who_left_fails() -> None:
    world = minded()
    world["departed"].append(world["actors"].pop(1))
    assert settled(world, 10.0) == ["failed", "goal_failed"]


def test_a_goal_is_done_once_both_sit_at_one_table() -> None:
    world = minded("sit_with", "bea")
    assert start_action(world, "ada", action("sit", "w2") | {"id": "sit:w2"})["accepted"]
    for _ in range(300):
        step_world(world, 0.1)
    assert settled(world, world["time"])[0] == "done"


def test_a_goal_gives_an_event_the_guest_takes_stock_after() -> None:
    world = spoke(minded(), "bea", 5.0)
    world["time"] = 10.0
    settle_goals(world)
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    ada["intention"]["written_at"] = 1.0
    assert intention_due(world, ada, INTENTION_RULES)["kind"] == "goal"


OTHERS = {"bea": "Bea", "cy": "Cy"}
THOUGHT = {"thought": "Hm.", "intention": "Talk to Bea."}


@pytest.mark.parametrize("answer, expected", [
    pytest.param({**THOUGHT, "goal": "none", "target": None}, None, id="no-goal"),
    pytest.param({**THOUGHT, "goal": "talk_to", "target": "bea"}, goal(), id="talk-to"),
    pytest.param({**THOUGHT, "goal": "sit_with", "target": "cy"}, goal("sit_with", "cy"), id="sit-with"),
])
def test_a_stance_names_a_goal_the_world_can_carry_out(answer: dict[str, Any], expected: Any) -> None:
    assert parse_stance(answer, OTHERS).get("goal") == expected


@pytest.mark.parametrize("answer", [
    pytest.param({**THOUGHT, "goal": "fetch_ale", "target": "bea"}, id="unknown-kind"),
    pytest.param({**THOUGHT, "goal": "talk_to", "target": "zed"}, id="person-not-in-the-hall"),
    pytest.param({**THOUGHT, "goal": "talk_to", "target": None}, id="kind-without-a-person"),
    pytest.param({**THOUGHT, "goal": "none", "target": "bea"}, id="person-without-a-kind"),
    pytest.param({**THOUGHT, "goal": "talk_to"}, id="target-missing"),
    pytest.param({**THOUGHT, "goal": 3, "target": None}, id="kind-not-text"),
    pytest.param({"thought": "", "intention": "Go.", "goal": "none", "target": None}, id="blank-thought"),
    pytest.param(None, id="not-an-object"),
])
def test_a_stance_the_world_cannot_carry_out_is_refused(answer: Any) -> None:
    with pytest.raises(ValueError):
        parse_stance(answer, OTHERS)


def test_check_goal_refuses_a_target_without_a_kind_in_the_table() -> None:
    with pytest.raises(ValueError):
        check_goal("avoid", "bea", OTHERS)


def test_the_mind_is_shown_who_it_may_set_a_goal_about() -> None:
    world = minded()
    ada = next(item for item in world["actors"] if item["id"] == "ada")
    shown = intention_view(world, ada, {"kind": "interval", "text": "A while passed", "time": 0.0})["others"]
    assert sorted(shown) == ["bea", "cy"]


def test_a_goal_survives_save_and_load(tmp_path: Path) -> None:
    world = minded()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


@pytest.mark.parametrize("corrupt", [
    pytest.param({"kind": "fetch_ale", "target": "bea", "status": "active"}, id="unknown-kind"),
    pytest.param({"kind": "talk_to", "target": "bea", "status": "pending"}, id="unknown-status"),
    pytest.param({"kind": "talk_to", "target": None, "status": "active"}, id="no-person"),
    pytest.param({"kind": "talk_to", "target": "bea"}, id="no-status"),
    pytest.param("talk_to", id="not-an-object"),
])
def test_a_corrupt_saved_goal_is_refused(corrupt: Any, tmp_path: Path) -> None:
    world = minded()
    next(item for item in world["actors"] if item["id"] == "ada")["intention"]["goal"] = corrupt
    save_world(world, tmp_path / "evening.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "evening.json")
