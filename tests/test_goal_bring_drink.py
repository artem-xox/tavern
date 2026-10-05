"""The goal of bringing someone a drink: what serves it, and when the world calls it done, failed or lapsed."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.mind.goals import check_goal, goal_pull, goal_words, serving
from tavern.mind.local_policy import GOAL_BONUS, local_scores
from tavern.social.thoughts import think
from test_goals import OTHERS, action, minded, settled, view


def give(item: str, target: str) -> dict[str, Any]:
    """The action of handing someone an item."""
    return {"id": f"give:{item}:{target}", "verb": "give", "target_id": target, "item": item}


def treated(world: dict[str, Any], at: float, by: str = "ada", kind: str = "treated") -> dict[str, Any]:
    """Bea took what Ada handed her, at a game time, and kept the thought a receiver keeps."""
    people = {item["id"]: item for item in world["actors"]}
    think(people["bea"], kind, at, "Ada handed me something", "gave", about=people[by])
    return world


def bring(**fields: Any) -> dict[str, Any]:
    """The hall where Ada, seated nowhere, set out to bring Bea a drink at a game time."""
    return minded("bring_drink", "bea", **fields)


@pytest.mark.parametrize("act, expected", [
    pytest.param(action("bring_drink", "bea"), True, id="bringing-the-drink"),
    pytest.param(action("bring_drink", "cy"), False, id="bringing-it-to-someone-else"),
    pytest.param(give("beer", "bea"), True, id="handing-over-a-mug"),
    pytest.param(give("beer", "cy"), False, id="handing-a-mug-to-someone-else"),
    pytest.param(give("remedy", "bea"), False, id="a-remedy-is-not-a-drink"),
    pytest.param(action("sit", "w2"), True, id="sitting-where-they-sit-to-be-near"),
    pytest.param(action("sit", "e1"), False, id="sitting-at-another-table"),
    pytest.param(action("seating", None), True, id="the-wish-to-sit-while-they-sit"),
    pytest.param(action("talk", "bea"), False, id="a-chat-is-not-a-drink"),
    pytest.param(action("wait", None), False, id="waiting-serves-nothing"),
])
def test_an_option_serves_the_goal_of_bringing_a_drink_or_not(act: dict[str, Any], expected: bool) -> None:
    assert serving(view(bring()), act) is expected


@pytest.mark.parametrize("sat, act, expected", [
    pytest.param(("bea:w1", "ada:w2"), action("bring_drink", "bea"), True, id="at-their-table-bringing-the-drink"),
    pytest.param(("bea:w1", "ada:w2"), give("beer", "bea"), True, id="at-their-table-handing-over-a-mug"),
    pytest.param(("bea:w1", "ada:w2"), action("sit", "w2"), False, id="staying-in-their-seat-is-no-help"),
    pytest.param(("bea:w1", "ada:w2"), action("seating", None), False, id="no-need-to-look-for-a-seat"),
    pytest.param(("bea:w1", "ada:e1"), action("sit", "w2"), True, id="at-another-table-sitting-where-they-sit"),
])
def test_getting_near_serves_the_goal_only_while_the_guest_is_not_near(sat: tuple[str, ...], act: dict[str, Any],
                                                                      expected: bool) -> None:
    world = minded("bring_drink", "bea", sat=sat)
    assert serving(view(world), act) is expected


def test_a_finished_goal_of_bringing_a_drink_serves_nothing() -> None:
    assert serving(view(bring(status="done")), action("bring_drink", "bea")) is False


@pytest.mark.parametrize("prepare, time, expected", [
    pytest.param(lambda: bring(), 10.0, ["active"], id="nothing-yet"),
    pytest.param(lambda: treated(bring(), 5.0), 10.0, ["done", "goal_done"], id="the-person-took-a-drink"),
    pytest.param(lambda: treated(bring(at=8.0), 5.0), 10.0, ["active"], id="a-drink-from-before-the-goal"),
    pytest.param(lambda: treated(bring(), 5.0, by="cy"), 10.0, ["active"], id="a-drink-from-someone-else"),
    pytest.param(lambda: treated(bring(), 5.0, kind="cared_for"), 10.0, ["active"], id="a-remedy-is-not-a-drink"),
    pytest.param(lambda: bring(), 179.0, ["active"], id="not-yet-lapsed"),
    pytest.param(lambda: bring(), 180.0, ["expired", "goal_expired"], id="lapses-after-three-minutes"),
    pytest.param(lambda: bring(status="done"), 500.0, ["done"], id="an-ended-goal-stays-ended"),
])
def test_the_goal_of_bringing_a_drink_ends_once_the_world_decides(prepare: Any, time: float, expected: list[str]) -> None:
    assert settled(prepare(), time) == expected


def test_a_goal_to_bring_a_drink_to_someone_who_left_fails() -> None:
    world = bring()
    world["departed"].append(world["actors"].pop(1))
    assert settled(world, 10.0) == ["failed", "goal_failed"]


def test_the_goal_is_told_in_words() -> None:
    assert goal_words({"kind": "bring_drink", "target": "bea", "status": "active"}, "Bea") == "bring Bea a drink"


def test_the_mind_may_set_it_about_a_guest_in_the_hall() -> None:
    assert check_goal("bring_drink", "bea", OTHERS) == {"kind": "bring_drink", "target": "bea", "status": "active"}


@pytest.mark.parametrize("target", [pytest.param("zed", id="person-not-in-the-hall"), pytest.param(None, id="no-person")])
def test_the_mind_may_not_set_it_about_nobody(target: str | None) -> None:
    with pytest.raises(ValueError):
        check_goal("bring_drink", target, OTHERS)


def test_someone_on_duty_may_not_leave_the_bar_to_bring_a_drink() -> None:
    with pytest.raises(ValueError, match="on duty"):
        check_goal("bring_drink", "bea", OTHERS, on_duty=True)


def test_a_goal_of_bringing_a_drink_survives_save_and_load(tmp_path: Path) -> None:
    world = bring()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def scores_of(world: dict[str, Any]) -> dict[str, float]:
    """Ada's local scores for bringing Bea a drink, chatting with her, and staying in her seat at Bea's table."""
    candidates = [action("bring_drink", "bea"), action("talk", "bea"), action("sit", "w2")]
    return local_scores(view(world), candidates)


def test_a_goal_to_bring_a_drink_lifts_the_trip_above_a_chat_and_a_seat_in_the_local_policy() -> None:
    sat = ("bea:w1", "ada:w2")
    aimless, aiming = scores_of(minded("bring_drink", "bea", status="done", sat=sat)), scores_of(
        minded("bring_drink", "bea", sat=sat))
    assert (aimless["bring_drink:bea"] < aimless["talk:bea"], aiming["bring_drink:bea"] > aiming["talk:bea"],
            aiming["bring_drink:bea"] > aiming["sit:w2"]) == (True, True, True)


@pytest.mark.parametrize("kind, act, pulled", [
    pytest.param("talk_to", action("talk", "bea"), GOAL_BONUS, id="an-ordinary-goal-pulls-by-the-usual-bonus"),
    pytest.param("sit_with", action("sit", "w2"), GOAL_BONUS, id="sitting-with-someone-too"),
    pytest.param("bring_drink", action("bring_drink", "bea"), 0.8, id="a-drink-pulls-harder-as-it-is-low-on-its-own"),
    pytest.param("bring_drink", action("talk", "bea"), 0.0, id="what-does-not-serve-is-not-pulled"),
])
def test_how_hard_a_goal_pulls_the_options_that_serve_it(kind: str, act: dict[str, Any], pulled: float) -> None:
    assert goal_pull(view(minded(kind, "bea")), act) == pytest.approx(pulled)
