"""A rematch: a guest who lost at dice goes to the winner and asks for another game, as one plan."""

from copy import deepcopy
from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.social.thoughts import think
from social_hall import actor, advance, command, know, say, scene_of, spotted_hall
from test_dice_invitation import CHAIRS, TABLE


def lost_to_cid(age: float = 5.0) -> dict[str, Any]:
    """Ada, standing, lost at dice to Cid, who sits at the far table; Ada knows the dice table."""
    data = spotted_hall()
    data["objects"] += [deepcopy(TABLE), *deepcopy(CHAIRS)]
    data["table_manners"] = False
    world = create_world(data, 4)
    assert start_action(world, "cid", command("sit", "fw"))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
        item["needs"]["boredom"] = 80.0
    know(world, "ada", "dice-table", "far", "fw", "fe")
    know(world, "cid", "dice-table")
    advance(world, age)
    think(actor(world, "ada"), "lost_at_dice", world["time"] - age, "Cid beat me", "dice", actor(world, "cid"))
    return world


def ask(world: dict[str, Any]) -> dict[str, Any]:
    """Ada sets out to ask Cid for a rematch."""
    return start_action(world, "ada", command("rematch", "cid"))


def of(world: dict[str, Any], kind: str) -> list[str]:
    """Messages of logged events of a kind."""
    return [item["message"] for item in world["events"] if item["type"] == kind]


def test_a_rematch_is_a_project_about_the_winner() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    [project] = world["projects"]
    assert (project["kind"], project["target"], project["of"]) == ("rematch", "cid", 2)


def test_the_plan_goes_to_the_winner_with_the_aim_of_a_rematch() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    advance(world, 10)
    scene = scene_of(world, "ada")
    assert scene is not None and scene["aims"]["ada"]["aim"] == "rematch"
    assert [item["message"] for item in world["events"] if item["type"] == "answered"][0].startswith("Ada went to answer")


def test_it_is_done_when_the_two_sit_down_to_the_game() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    advance(world, 80)
    assert (of(world, "project_done"), world["projects"], of(world, "dice_started")[:1]) == (
        ["Ada got the rematch (rematch)"], [], ["Ada and Cid sat down to a game of dice"])


def test_a_refusal_ends_it_as_failed() -> None:
    world = lost_to_cid()
    actor(world, "cid")["needs"]["boredom"] = 0.0
    assert ask(world)["accepted"]
    advance(world, 80)
    failed = of(world, "project_failed")
    assert (failed, world["projects"]) == (["Ada could not ask for a rematch: they would not play (rematch)"], [])


def test_the_winner_going_home_ends_it() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    advance(world, 10)
    world["actors"].remove(actor(world, "cid"))
    advance(world, 3)
    assert (len(of(world, "project_failed")), world["projects"]) == (1, [])


def test_it_lapses_when_nothing_comes_of_it() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    world["projects"][0]["started_at"] -= 1000
    advance(world, 1)
    assert of(world, "project_expired") == ["Ada gave up asking for a rematch (rematch)"]


@pytest.mark.parametrize("prepare", [
    pytest.param(lambda world: actor(world, "ada")["thoughts"].clear(), id="no-lost-game-to-answer"),
    pytest.param(lambda world: actor(world, "ada")["thoughts"].append(
        {**actor(world, "ada")["thoughts"][-1], "answered": True}) or actor(world, "ada")["thoughts"].pop(-2),
                 id="the-thought-was-answered"),
    pytest.param(lambda world: actor(world, "ada")["knowledge"]["objects"].pop("dice-table"), id="no-dice-table-known"),
    pytest.param(lambda world: next(item for item in world["map"]["objects"] if item["id"] == "dice-table").update(
        game={"players": ["bea", "dan"], "since": 0.0, "ends_at": None}), id="a-game-under-way"),
])
def test_a_rematch_that_cannot_be_asked_for_is_refused(prepare: Any) -> None:
    world = lost_to_cid()
    prepare(world)
    assert (ask(world)["accepted"], world["projects"]) == (False, [])


def seen(world: dict[str, Any], projects: bool = True) -> dict[str, Any]:
    """Ada's observation."""
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada"),
            **({"projects": ["rematch"]} if projects else {})}


def offered(view: dict[str, Any]) -> bool:
    """Whether a rematch with Cid is among the options."""
    return any(item["verb"] == "rematch" and item["target_id"] == "cid" for option in build_candidates(view)
               for item in option.get("members", [option]))


def test_a_rematch_is_offered_while_the_loss_calls_for_an_answer() -> None:
    world = lost_to_cid()
    assert (offered(seen(world)), offered(seen(world, projects=False))) == (True, False)


def test_a_rematch_is_not_offered_after_the_window() -> None:
    world = lost_to_cid(age=100.0)
    assert offered(seen(world)) is False


def test_beginning_a_rematch_answers_the_loss_so_that_a_failure_does_not_ask_again() -> None:
    world = lost_to_cid()
    assert ask(world)["accepted"]
    world["actors"].remove(actor(world, "cid"))
    advance(world, 3)
    assert (len(of(world, "project_failed")), [item.get("answered") for item in actor(world, "ada")["thoughts"]
                                               if item["kind"] == "lost_at_dice"]) == (1, [True])


def test_a_rematch_is_not_offered_with_a_winner_one_cannot_reach() -> None:
    world = lost_to_cid()
    cid = actor(world, "cid")
    cid.update(seat_id=None, x=11, y=7)
    for item in world["map"]["objects"]:
        if item.get("reserved_by") == "cid":
            item["reserved_by"] = None
    assert offered(seen(world)) is False
