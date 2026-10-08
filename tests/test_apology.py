"""An apology that mends: it softens the grudge it answers and leaves a warm thought, and says so in the log."""

from typing import Any

import pytest

from tavern.hall.world import create_world, start_action
from tavern.social.thoughts import THOUGHTS, opinion_of
from social_hall import actor, advance, command, say, spotted_hall


def after_an_intrusion() -> dict[str, Any]:
    """Cid sits at the far table; Ada sits down there uninvited, and starts talking to him."""
    world = create_world({**spotted_hall(), "table_manners": True}, 4)
    for name, chair in (("cid", "fw"), ("ada", "fe")):
        assert start_action(world, name, command("sit", chair))["accepted"]
        advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    assert start_action(world, "ada", command("talk", "cid"))["accepted"]
    return world


def cids_opinion(world: dict[str, Any]) -> float:
    """What Cid thinks of Ada."""
    return opinion_of(actor(world, "cid"), "ada", world["time"])


def test_an_apology_turns_a_grudge_into_goodwill() -> None:
    world = after_an_intrusion()
    assert cids_opinion(world) == pytest.approx(THOUGHTS["table_intruded"].opinion)
    assert say(world, "apologize", "Sorry, I should have asked.") == "ada"
    assert cids_opinion(world) == pytest.approx(THOUGHTS["table_intruded"].opinion / 2 + THOUGHTS["apologized"].opinion)
    assert cids_opinion(world) > 0


def test_an_apology_is_remembered_by_both() -> None:
    world = after_an_intrusion()
    say(world, "apologize")
    told = [[e["message"] for e in actor(world, who)["memory"] if e["type"] == "apologized"] for who in ("ada", "cid")]
    assert told == [["Ada apologized to Cid"]] * 2


def test_a_second_apology_for_the_same_wrong_changes_nothing() -> None:
    world = after_an_intrusion()
    say(world, "apologize")
    say(world, "remark")
    mended = cids_opinion(world)
    say(world, "apologize")
    assert cids_opinion(world) == pytest.approx(mended)
    assert sum(e["type"] == "apologized" for e in actor(world, "cid")["memory"]) == 1
