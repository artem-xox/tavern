"""Onlookers at a game of dice: who may watch, how they stand, and what they take away."""

import asyncio
import json
from random import Random
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.agents import build_candidates, choose_action
from tavern.mind.local_policy import local_scores
from tavern.mind.options import option_text
from dice_hall import advance, guest, happened, start, table, table_hall, who

WATCH = "watch_dice"


def playing(*watchers: dict[str, Any], waiting: bool = False) -> dict[str, Any]:
    """Ada and Bea (or only Ada) at the dice table, with the watchers placed by hand, a few seconds in."""
    world = table_hall(guest("ada", (7, 8)), guest("bea", (11, 8)), *watchers)
    assert start(world, "ada", "play_dice", "dice-chair-1")["accepted"]
    if not waiting:
        assert start(world, "bea", "play_dice", "dice-chair-2")["accepted"]
    advance(world, 3)
    return world


def onlooker(actor_id: str = "cid", cell: tuple[int, int] = (13, 8), **fields: Any) -> dict[str, Any]:
    """A guest near the table who sees the game."""
    return guest(actor_id, cell, **fields)


def options_of(world: dict[str, Any], actor_id: str = "cid") -> list[dict[str, Any]]:
    """The concrete options a guest has, as the decision layer builds them."""
    observation = {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}
    return [item for option in build_candidates(observation) for item in option.get("members", [option])]


def watching(world: dict[str, Any]) -> list[str]:
    """The verbs of the options a guest has that watch a game."""
    return [item["target_id"] for item in options_of(world) if item["verb"] == WATCH]


@pytest.mark.parametrize("prepare, offered", [
    pytest.param(lambda world: None, True, id="a-game-under-way"),
    pytest.param(lambda world: world["map"]["objects"][-3].update(game=None), False, id="the-game-is-over"),
    pytest.param(lambda world: world.update(closes_at=0.0), False, id="the-inn-has-closed"),
])
def test_watching_is_offered_while_a_game_is_under_way(prepare: Any, offered: bool) -> None:
    world = playing(onlooker())
    assert table(world)["game"] is not None
    prepare(world)
    assert (watching(world) == ["dice-table"]) is offered


def test_a_table_with_one_player_waiting_draws_no_crowd() -> None:
    assert watching(playing(onlooker(), waiting=True)) == []


def test_no_table_in_sight_or_in_mind_means_nothing_to_watch() -> None:
    world = table_hall(onlooker("cid", (3, 3)))
    assert watching(world) == []


def test_the_option_names_the_players_as_the_watcher_calls_them() -> None:
    world = playing(onlooker())
    world["actors"][-1]["relations"]["bea"] = {"name": "the stout woman with a pipe", "opinion": 0.0,
                                                "familiarity": "stranger", "knows_name": False}
    world["actors"][1]["card"] = {"looks": "the stout woman with a pipe"}
    observation = {**observe_actor(world, "cid"), "people": observe_people(world, "cid")}
    [action] = [item for item in options_of(world) if item["verb"] == WATCH]
    assert option_text(observation, action).endswith("and watch Ada and the stout woman with a pipe play dice")


@pytest.mark.parametrize("low, high", [
    pytest.param({"boredom": 20}, {"boredom": 80}, id="boredom"),
    pytest.param({"boredom": 50, "bladder": 80}, {"boredom": 50, "bladder": 10}, id="a-pressing-need"),
])
def test_the_wish_to_watch_grows_with_boredom_and_falls_with_a_pressing_need(low: dict[str, float],
                                                                          high: dict[str, float]) -> None:
    def score(needs: dict[str, float]) -> float:
        world = playing(onlooker())
        who(world, "cid")["needs"].update(needs)
        observation = {**observe_actor(world, "cid"), "people": observe_people(world, "cid")}
        [action] = [item for item in options_of(world) if item["verb"] == WATCH]
        return local_scores(observation, [action])[action["id"]]
    assert score(low) < score(high)


def test_curious_guests_like_a_game_more() -> None:
    def score(curiosity: float) -> float:
        world = playing(onlooker(traits={"curiosity": curiosity}))
        observation = {**observe_actor(world, "cid"), "people": observe_people(world, "cid")}
        [action] = [item for item in options_of(world) if item["verb"] == WATCH]
        return local_scores(observation, [action])[action["id"]]
    assert score(0.1) < score(0.9)


def test_a_bored_guest_choosing_with_the_local_policy_may_pick_the_game() -> None:
    world = playing(onlooker(needs={"boredom": 95, "thirst": 5, "fatigue": 5, "bladder": 5, "social": 5}))
    observation = {**observe_actor(world, "cid"), "people": observe_people(world, "cid")}
    verbs = {asyncio.run(choose_action(observation, {"typesafe_api_key": None, "temperature": 0.5}, Random(seed)))
             ["action"]["verb"] for seed in range(40)}
    assert WATCH in verbs


def test_onlookers_stand_on_different_spots_and_never_reserve_the_table() -> None:
    watchers = [onlooker(name, (13, 7 + index)) for index, name in enumerate(("cid", "dan", "eve"))]
    world = playing(*watchers)
    for name in ("cid", "dan", "eve"):
        assert start(world, name, WATCH, "dice-table")["accepted"]
    advance(world, 6)
    spots = [(who(world, name)["x"], who(world, name)["y"]) for name in ("cid", "dan", "eve")]
    assert len(set(spots)) == 3 and all(list(spot) in table(world)["interaction_spots"] for spot in spots)
    assert table(world)["reserved_by"] is None
    assert [who(world, name)["status"] for name in ("cid", "dan", "eve")] == ["interacting"] * 3


def test_once_every_spot_is_taken_the_next_onlooker_is_refused() -> None:
    names = ("cid", "dan", "eve", "fay", "gus")
    world = playing(*[onlooker(name, (12, 6 + index)) for index, name in enumerate(names)])
    answers = [start(world, name, WATCH, "dice-table")["accepted"] for name in names]
    assert answers == [True, True, True, True, False]


def test_onlookers_finish_with_the_game_and_remember_its_result() -> None:
    world = playing(onlooker("cid", (13, 8)), onlooker("dan", (13, 10)))
    for name in ("cid", "dan"):
        assert start(world, name, WATCH, "dice-table")["accepted"]
    advance(world, 40)
    [result] = set(happened(world, "dice_won"))
    loser, winner = result.split(" beat ")[1].removesuffix(" at dice"), result.split(" beat ")[0]
    assert sorted(happened(world, "dice_watched")) == [f"Cid watched {winner} beat {loser} at dice",
                                                       f"Dan watched {winner} beat {loser} at dice"]
    assert [(who(world, name)["status"], who(world, name)["action"]) for name in ("cid", "dan")] == [("idle", None)] * 2
    assert all(who(world, name)["needs"]["boredom"] < who(world, "ada")["needs"]["boredom"] + 80 for name in ("cid", "dan"))
    assert who(world, "cid")["needs"]["boredom"] < 50


def test_an_onlooker_who_arrives_after_the_result_is_let_go() -> None:
    world = playing(onlooker())
    advance(world, 40)
    assert table(world)["game"] is None
    assert start(world, "cid", WATCH, "dice-table")["accepted"]
    advance(world, 8)
    assert (who(world, "cid")["status"], who(world, "cid")["action"]) == ("idle", None)
    assert happened(world, "dice_watched") == []


def test_a_game_broken_off_lets_its_onlookers_go_without_a_result() -> None:
    world = playing(onlooker())
    assert start(world, "cid", WATCH, "dice-table")["accepted"]
    advance(world, 5)
    assert start(world, "ada", "wait")["accepted"]
    advance(world, 1)
    assert (who(world, "cid")["status"], happened(world, "dice_watched"), happened(world, "dice_won")) == ("idle", [], [])


def test_a_save_made_while_guests_watch_loads_back_unchanged() -> None:
    world = playing(onlooker())
    assert start(world, "cid", WATCH, "dice-table")["accepted"]
    advance(world, 6)
    assert who(world, "cid")["status"] == "interacting"
    assert parse_world(json.dumps(world)) == world
