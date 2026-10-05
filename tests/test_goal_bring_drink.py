"""The goal of bringing someone a drink: what serves it, and when the world calls it done, failed or lapsed."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.mind.goals import check_goal, goal_words, serving
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
