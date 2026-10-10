"""How a guest weighs and words their answers to a fight or a hurt, without a model."""

from random import Random
import asyncio
from typing import Any

import pytest

from tavern.mind.agents import choose_action
from tavern.mind.fight_policy import utilities
from tavern.mind.local_policy import local_scores
from tavern.mind.options import option_text
from test_reactions import person, view


def guest(**traits: float) -> dict[str, Any]:
    """Ada's observation, with the given traits, of a fight at her table."""
    observation = view([person("bea", fighting="cid"), person("cid", fighting="bea")])
    observation["objects"] = []
    observation["actor"].update(traits={"courage": 0.5, "strength": 0.5, "sociability": 0.5, "curiosity": 0.5,
                                        "temper": 0.5, **traits}, inventory={"beer": 0, "remedy": 0},
                                needs={"thirst": 10, "fatigue": 10, "bladder": 10, "social": 10, "boredom": 10})
    return observation


@pytest.mark.parametrize("verb, low, high", [
    pytest.param("intervene", guest(courage=0.1, strength=0.2), guest(courage=0.9, strength=0.9), id="the-brave-and-strong-step-in"),
    pytest.param("watch_fight", guest(curiosity=0.1), guest(curiosity=0.9), id="the-curious-watch"),
    pytest.param("cheer", guest(sociability=0.1), guest(sociability=0.9), id="the-sociable-cheer"),
    pytest.param("join_fight", guest(courage=0.2, temper=0.2), guest(courage=0.9, temper=0.9), id="the-hot-and-bold-join"),
    pytest.param("help_up", guest(sociability=0.1), guest(sociability=0.9), id="the-sociable-help-up"),
])
def test_traits_move_the_score_of_a_reaction(verb: str, low: dict[str, Any], high: dict[str, Any]) -> None:
    assert utilities(low)[verb] < utilities(high)[verb]


def test_drink_spoils_stepping_between_and_lifts_cheering() -> None:
    sober, drunk = guest(), guest()
    drunk["actor"]["drunkenness"] = 0.8
    assert (utilities(drunk)["intervene"] < utilities(sober)["intervene"],
            utilities(drunk)["cheer"] > utilities(sober)["cheer"]) == (True, True)


def test_a_friend_among_the_fighters_pushes_a_guest_to_step_in() -> None:
    stranger, friend = guest(), guest()
    friend["actor"]["relations"] = {"bea": {"name": "Bea", "opinion": 60.0, "familiarity": "friend"}}
    assert utilities(friend)["intervene"] > utilities(stranger)["intervene"]


def test_mending_comes_before_nearly_everything_for_the_hurt() -> None:
    observation = guest()
    scores = utilities(observation)
    assert scores["use_remedy"] > scores["seek_remedy"] >= 0.7 > scores["cheer"]


def test_the_timid_would_rather_leave_where_a_fight_is_on() -> None:
    brave, timid = guest(courage=0.9), guest(courage=0.1)
    candidates = [{"id": "leave:door", "verb": "leave", "target_id": "door"}]
    for observation in (brave, timid):
        observation["actor"].update(visit={"seconds": 100.0, "beers": 0}, drunkenness=0.0)
        observation["objects"] = [{"id": "door", "kind": "door", "x": 0, "y": 7, "interaction_spots": [[0, 6]],
                                   "reserved_by": None}]
    assert local_scores(timid, candidates)["leave:door"] > local_scores(brave, candidates)["leave:door"]


def test_a_hurt_guest_means_to_go_home_to_mend() -> None:
    whole, hurt = guest(), guest()
    for observation in (whole, hurt):
        observation["people"] = []
        observation["actor"].update(visit={"seconds": 100.0, "beers": 0}, drunkenness=0.0)
        observation["objects"] = [{"id": "door", "kind": "door", "x": 0, "y": 7, "interaction_spots": [[0, 6]],
                                   "reserved_by": None}]
    hurt["actor"]["health"] = 30.0
    candidates = [{"id": "leave:door", "verb": "leave", "target_id": "door"}]
    assert local_scores(hurt, candidates)["leave:door"] > 0.8 > local_scores(whole, candidates)["leave:door"]


@pytest.mark.parametrize("verb, target, expected", [
    pytest.param("watch_fight", None, "watch Bea and Cid fight", id="watch"),
    pytest.param("cheer", None, "cheer Bea and Cid on", id="cheer"),
    pytest.param("intervene", "bea", "step between Bea and Cid", id="intervene"),
    pytest.param("join_fight", "bea", "wait a turn to take them on", id="join"),
    pytest.param("help_up", "bea", "help Bea, who lies on the floor", id="help-up"),
    pytest.param("seek_remedy", "bea", "go to Bea, who carries remedies", id="seek"),
    pytest.param("use_remedy", None, "take one of the herbal remedies", id="use"),
])
def test_each_reaction_has_its_sentence(verb: str, target: str | None, expected: str) -> None:
    observation = guest()
    assert expected in option_text(observation, {"id": verb, "verb": verb, "target_id": target})


def test_a_hurt_guest_with_a_healer_in_sight_chooses_among_the_mending_options_only() -> None:
    observation = guest()
    observation["people"] = [person("cid", healer=True)]
    observation["actor"].update(health=30.0, id="ada", visit={"seconds": 200.0, "beers": 2}, seat_id="w",
                                favorite_seat_id="w", drunkenness=0.0, inventory={"beer": 0, "remedy": 0, "keepsake": 0, "cudgel": 0})
    observation["objects"] = [{"id": "door", "kind": "door", "x": 0, "y": 7, "interaction_spots": [[0, 6]], "reserved_by": None},
                              {"id": "w", "kind": "chair", "table_id": "near", "x": 2, "y": 2, "interaction_spots": [[2, 2]],
                               "reserved_by": "ada"}]
    chosen = asyncio.run(choose_action(observation, {"typesafe_api_key": None, "temperature": 0.0}, Random(1)))
    assert chosen["action"]["verb"] in ("seek_remedy", "leave")


@pytest.mark.parametrize("opinion, temper, at_least, below", [
    pytest.param(-75.0, 0.9, 0.67, None, id="hatred-in-a-hot-head-wants-it-badly"),
    pytest.param(-75.0, 0.0, 0.4, None, id="hatred-alone-is-worth-a-good-deal"),
    pytest.param(-40.0, 0.9, None, 0.3, id="a-grudge-alone-is-still-a-poor-choice"),
])
def test_a_fight_with_someone_they_hate_is_worth_more_to_a_guest(opinion: float, temper: float, at_least: float | None,
                                                                 below: float | None) -> None:
    observation = guest(temper=temper)
    observation["actor"]["relations"] = {"bea": {"name": "Bea", "opinion": opinion, "familiarity": "acquaintance"}}
    observation["actor"].update(visit={"seconds": 100.0, "beers": 0}, drunkenness=0.0)
    candidates = [{"id": "start_fight:bea", "verb": "start_fight", "target_id": "bea"}]
    score = local_scores(observation, candidates)["start_fight:bea"]
    assert (at_least is None or score >= at_least) and (below is None or score < below)
