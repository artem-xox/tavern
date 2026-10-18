"""Goals: what a guest's mind may set out to do, the options that serve it, and how it ends."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.goals import check_goal, open_kinds, serving, serving_aim, settle_goals
from tavern.mind.intentions import INTENTION_RULES, intention_due, intention_view, parse_stance
from tavern.mind.local_policy import GOAL_BONUS, local_aim_scores, local_scores
from tavern.social.thoughts import think


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


def ada_of(world: dict[str, Any]) -> dict[str, Any]:
    """Ada, the guest who holds the goal."""
    return next(item for item in world["actors"] if item["id"] == "ada")


def thinking(world: dict[str, Any], kind: str, about: str, at: float) -> dict[str, Any]:
    """Ada comes to hold a thought of a kind about a guest, formed at a game time."""
    other = next(item for item in world["actors"] if item["id"] == about)
    think(ada_of(world), kind, at, f"{kind} with {about}", f"{kind} event", about=other)
    return world


@pytest.mark.parametrize("kind, target, act, expected", [
    pytest.param("treat", "bea", action("talk", "bea"), True, id="treat-by-talking-to-them"),
    pytest.param("treat", "bea", action("approach", "bea"), True, id="treat-by-walking-over"),
    pytest.param("treat", "bea", action("bring_drink", "bea"), True, id="treat-by-bringing-an-ale"),
    pytest.param("treat", "bea", action("talk", "cy"), False, id="treat-by-talking-to-someone-else"),
    pytest.param("play_with", "bea", action("approach", "bea"), True, id="play-by-walking-over"),
    pytest.param("play_with", "bea", action("sit", "w2"), False, id="play-by-sitting-uninvited"),
    pytest.param("have_it_out", "bea", action("talk", "bea"), True, id="have-it-out-by-talking"),
    pytest.param("have_it_out", "bea", action("join_conversation", "cy"), False, id="have-it-out-with-someone-else"),
])
def test_an_option_serves_the_new_kinds_of_goal(kind: str, target: str, act: dict[str, Any], expected: bool) -> None:
    assert serving(view(minded(kind, target)), act) is expected


def aimed(aim: str, target: str) -> dict[str, Any]:
    """A social option with an aim, as the aim candidates carry it."""
    return {"id": f"talk:{target}:{aim}", "verb": "talk", "target_id": target, "aim": aim}


@pytest.mark.parametrize("kind, target, candidate, expected", [
    pytest.param("treat", "bea", aimed("invite:buy_drink", "bea"), True, id="invite-them-to-an-ale"),
    pytest.param("treat", "bea", aimed("invite:buy_drink", "cy"), False, id="invite-someone-else-to-an-ale"),
    pytest.param("treat", "bea", aimed("pass_time", "bea"), False, id="small-talk-is-not-a-round"),
    pytest.param("play_with", "bea", aimed("invite:dice_together", "bea"), True, id="invite-them-to-dice"),
    pytest.param("play_with", "bea", aimed("rematch", "bea"), True, id="ask-for-a-rematch"),
    pytest.param("play_with", "bea", aimed("invite:darts_together", "bea"), False, id="darts-is-not-dice"),
    pytest.param("have_it_out", "bea", aimed("have_it_out", "bea"), True, id="have-it-out-aim"),
    pytest.param("have_it_out", "bea", aimed("needle", "bea"), True, id="needle-aim"),
    pytest.param("have_it_out", "bea", aimed("win_over", "bea"), False, id="winning-over-is-not-having-it-out"),
    pytest.param("talk_to", "bea", aimed("needle", "bea"), False, id="talking-is-not-a-needle"),
])
def test_an_aim_serves_a_goal_aimed_at_its_person(kind: str, target: str, candidate: dict[str, Any],
                                                  expected: bool) -> None:
    assert serving_aim(view(minded(kind, target)), candidate) is expected


def test_the_local_policy_prefers_the_aim_that_serves_the_goal() -> None:
    observation = view(minded("play_with", "bea"))
    served, other = aimed("invite:dice_together", "bea"), aimed("pass_time", "bea")
    scores = local_aim_scores(observation, [served, other])
    unserved = local_aim_scores({**observation, "actor": {**observation["actor"], "intention": None}}, [served, other])
    assert scores[served["id"]] == pytest.approx(min(1.0, unserved[served["id"]] + GOAL_BONUS))
    assert scores[other["id"]] == unserved[other["id"]]


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda: minded("treat", "bea"), ["active"], id="treat-nothing-yet"),
    pytest.param(lambda: thinking(minded("treat", "bea"), "generous", "bea", 5.0), ["done", "goal_done"],
                 id="treat-after-giving-them-an-ale"),
    pytest.param(lambda: thinking(minded("treat", "bea"), "generous", "cy", 5.0), ["active"],
                 id="treat-someone-else-is-not-it"),
    pytest.param(lambda: thinking(minded("treat", "bea", at=8.0), "generous", "bea", 5.0), ["active"],
                 id="treat-before-the-goal-is-not-it"),
    pytest.param(lambda: thinking(minded("play_with", "bea"), "lost_at_dice", "bea", 5.0), ["done", "goal_done"],
                 id="play-after-a-loss"),
    pytest.param(lambda: thinking(minded("play_with", "bea"), "won_at_dice", "bea", 5.0), ["done", "goal_done"],
                 id="play-after-a-win"),
    pytest.param(lambda: thinking(minded("play_with", "bea"), "chat", "bea", 5.0), ["active"],
                 id="play-a-chat-is-not-a-game"),
    pytest.param(lambda: thinking(minded("have_it_out", "bea"), "quarrel", "bea", 5.0), ["done", "goal_done"],
                 id="have-it-out-after-a-quarrel"),
    pytest.param(lambda: thinking(minded("have_it_out", "bea"), "insulted", "bea", 5.0), ["active"],
                 id="have-it-out-an-insult-is-not-a-quarrel"),
])
def test_the_new_goals_end_when_the_world_shows_them_reached(prepare: Any, expected: list[str]) -> None:
    assert settled(prepare(), 10.0) == expected


@pytest.mark.parametrize("kind, time", [
    pytest.param("treat", 241.0, id="treat-lapses"),
    pytest.param("play_with", 301.0, id="play-lapses"),
    pytest.param("have_it_out", 181.0, id="have-it-out-lapses"),
])
def test_the_new_goals_lapse_unreached(kind: str, time: float) -> None:
    assert settled(minded(kind, "bea"), time) == ["expired", "goal_expired"]


def furnished(*objects: dict[str, Any]) -> dict[str, Any]:
    """The hall with extra objects: Ada, Bea and Cy stand about."""
    return create_world({**hall(), "objects": [*hall()["objects"], *objects]})


DICE = {"id": "dice", "kind": "dice_table", "name": "Dice table", "x": 5, "y": 4, "interaction_spots": [[5, 3]]}
TAP = {"id": "tap", "kind": "tap", "name": "Tap", "x": 6, "y": 0, "interaction_spots": [[6, 1]]}


@pytest.mark.parametrize("world, expected", [
    pytest.param(furnished(), ["talk_to", "sit_with", "have_it_out"], id="bare-hall"),
    pytest.param(furnished(DICE), ["talk_to", "sit_with", "play_with", "have_it_out"], id="dice-table"),
    pytest.param(furnished(TAP), ["talk_to", "sit_with", "treat", "have_it_out"], id="tap"),
    pytest.param(furnished(DICE, TAP), ["talk_to", "sit_with", "treat", "play_with", "have_it_out"], id="both"),
])
def test_only_the_goals_the_hall_can_carry_out_are_open(world: dict[str, Any], expected: list[str]) -> None:
    assert open_kinds(world, ada_of(world), next(item for item in world["actors"] if item["id"] == "bea")) == expected


def test_nobody_wants_to_have_it_out_with_a_friend() -> None:
    world = furnished()
    ada, bea = ada_of(world), next(item for item in world["actors"] if item["id"] == "bea")
    ada["relations"]["bea"] = {"name": "Bea", "opinion": 50.0, "familiarity": "friend"}
    assert "have_it_out" not in open_kinds(world, ada, bea)


def test_nobody_sets_a_game_a_round_or_a_quarrel_with_someone_asleep() -> None:
    world = furnished(DICE, TAP)
    bea = next(item for item in world["actors"] if item["id"] == "bea")
    bea["action"] = {"id": "doze:w1", "verb": "doze", "target_id": "w1", "progress": 0.0, "duration": 60.0}
    bea["status"] = "interacting"
    assert open_kinds(world, ada_of(world), bea) == ["talk_to", "sit_with"]


@pytest.mark.parametrize("answer, possible, ok", [
    pytest.param({**THOUGHT, "goal": "play_with", "target": "bea"}, {"bea": ["talk_to", "play_with"]}, True,
                 id="an-open-goal"),
    pytest.param({**THOUGHT, "goal": "play_with", "target": "bea"}, {"bea": ["talk_to"]}, False,
                 id="a-goal-the-hall-cannot-carry-out"),
    pytest.param({**THOUGHT, "goal": "play_with", "target": "cy"}, {"bea": ["play_with"]}, False,
                 id="a-goal-open-for-someone-else"),
    pytest.param({**THOUGHT, "goal": "none", "target": None}, {}, True, id="no-goal-needs-nothing-open"),
])
def test_a_stance_is_refused_for_a_goal_the_hall_cannot_carry_out_now(answer: dict[str, Any],
                                                                      possible: dict[str, list[str]], ok: bool) -> None:
    if ok:
        parse_stance(answer, OTHERS, possible=possible)
    else:
        with pytest.raises(ValueError):
            parse_stance(answer, OTHERS, possible=possible)


def test_the_mind_is_shown_which_goals_are_open_for_each_guest() -> None:
    world = furnished(DICE)
    shown = intention_view(world, ada_of(world), {"kind": "interval", "text": "A while passed", "time": 0.0})
    assert shown["possible"]["bea"] == ["talk_to", "sit_with", "play_with", "have_it_out"]


@pytest.mark.parametrize("time, bonus", [
    pytest.param(30.0, GOAL_BONUS, id="early-the-bonus-only-tips-a-tie"),
    pytest.param(60.0, GOAL_BONUS, id="half-way-the-bonus-is-still-the-base"),
    pytest.param(90.0, GOAL_BONUS + 0.1, id="three-quarters-through-it-is-halfway-grown"),
    pytest.param(120.0, GOAL_BONUS + 0.2, id="at-the-end-it-is-fully-grown"),
])
def test_the_pull_of_a_goal_grows_over_its_second_half_so_a_steady_need_cannot_starve_it(time: float, bonus: float) -> None:
    world = minded("sit_with")
    world["time"] = time
    observation = view(world)
    sat = action("sit", "w2")
    without = {**observation, "actor": {**observation["actor"], "intention": None}}
    assert local_scores(observation, [sat])[sat["id"]] == pytest.approx(
        min(1.0, local_scores(without, [sat])[sat["id"]] + bonus))
