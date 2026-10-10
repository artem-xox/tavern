"""What a turn writer is told of a guest who has just fought, or who is hurt: the speaker's side of `turn_view`."""

from typing import Any

import pytest

from tavern.mind.haiku_turns import turn_content
from tavern.social.scenes import conversation_of
from tavern.social.turns import turn_view
from test_turn_mind import people, scene_world


def after_fight(ended_ago: float, outcome: str = "shouting") -> dict[str, Any]:
    """Ada, Bea and Cid at one table in a conversation, and a fight between Ada and Bea that ended `ended_ago` ago."""
    world = scene_world(None)
    world["time"] = 500.0
    world["fights"].append({"id": "fight-1", "a": "ada", "b": "bea", "weapons": {"ada": "fists", "bea": "fists"},
                            "started_at": 480.0, "next_exchange_at": 481.0, "exchanges": [], "waiting": [],
                            "witnessed": True, "cause": "drink", "outcome": outcome, "loser": None,
                            "ended_at": 500.0 - ended_ago})
    return world


@pytest.mark.parametrize("ended_ago, outcome, expected", [
    pytest.param(5.0, "shouting", ["bea"], id="just-now"),
    pytest.param(119.0, "parted", ["bea"], id="nearly-two-minutes-ago"),
    pytest.param(121.0, "shouting", [], id="long-ago"),
])
def test_the_speaker_is_told_whom_they_fought_just_now(ended_ago: float, outcome: str, expected: list[str]) -> None:
    world = after_fight(ended_ago, outcome)
    assert turn_view(world, conversation_of(world, "ada"))["speaker"]["just_fought"] == expected


def test_a_speaker_who_did_not_fight_is_told_of_nobody() -> None:
    world = after_fight(5.0)
    world["fights"][0].update(a="bea", b="cid", weapons={"bea": "fists", "cid": "fists"})
    assert turn_view(world, conversation_of(world, "ada"))["speaker"]["just_fought"] == []


def test_a_model_writer_is_told_the_talk_is_sharp() -> None:
    world = after_fight(5.0)
    assert "just come to blows with Bea" in turn_content(turn_view(world, conversation_of(world, "ada")))


def test_a_model_writer_is_told_of_hurts_in_the_company_and_in_the_speaker() -> None:
    world = after_fight(300.0)
    people(world)["ada"]["health"] = 40.0
    people(world)["bea"]["health"] = 30.0
    view = turn_view(world, conversation_of(world, "ada"))
    content = turn_content(view)
    assert [item["hurt"] for item in view["speaker"]["company"]] == [True, False]
    assert "You are battered and hurt after a fight and want to mend." in content
    assert "looks battered and hurt" in content
