"""A shout is an insult flung across the hall: offered to a row already on or a grudge, heard and turned to by the room."""

from typing import Any

import pytest

from tavern.social.quarrels import heat
from tavern.social.thoughts import opinion_of
from tavern.social.turns import claim_turns, turn_view
from social_hall import actor, say, scene_of, seated_talk
from test_grudges import GRUDGE
from test_quarrels import foes


def grudge_held_by(world: dict[str, Any], holder: str, toward: str) -> None:
    """Give a guest a tie toward another that holds a grudge."""
    actor(world, holder)["ties"] = [{"with": toward, "name": toward.title(), "kind": "rivals", "note": "Old rivals.",
                                     "grudge": GRUDGE}]


def offered(world: dict[str, Any]) -> list[str]:
    """The acts the next speaker of Ada's scene may use."""
    return list(turn_view(world, scene_of(world))["acts"])


def heated(world: dict[str, Any]) -> None:
    """One insult has been traded, so the row is on."""
    say(world, "insult")


def disliking(world: dict[str, Any]) -> None:
    """Ada and Bea dislike each other, with no row yet."""
    foes(world)


@pytest.mark.parametrize("prepare, shout", [
    pytest.param(lambda world: None, False, id="friendly-talk"),
    pytest.param(disliking, False, id="dislike-alone-is-only-an-insult"),
    pytest.param(lambda world: (disliking(world), heated(world)), True, id="a-row-is-on"),
    pytest.param(lambda world: (disliking(world), grudge_held_by(world, "ada", "bea"),
                                grudge_held_by(world, "bea", "ada")), True, id="a-grudge-is-held"),
    pytest.param(lambda world: (grudge_held_by(world, "ada", "bea"), grudge_held_by(world, "bea", "ada")), False,
                 id="a-grudge-without-dislike-is-no-shout"),
    pytest.param(lambda world: (disliking(world), grudge_held_by(world, "ada", "cid"),
                                grudge_held_by(world, "bea", "cid")), False, id="a-grudge-against-someone-absent"),
])
def test_a_shout_is_offered_in_a_row_or_for_a_grudge_to_someone_disliked(prepare: Any, shout: bool) -> None:
    world = seated_talk()
    prepare(world)
    assert ("shout" in offered(world)) == shout


def test_a_shout_stings_like_an_insult_and_is_answered_in_kind() -> None:
    world = seated_talk()
    foes(world)
    heated(world)
    shouter = say(world, "shout")
    target = "ada" if shouter == "bea" else "bea"
    assert ("insulted" in {item["kind"] for item in actor(world, target)["thoughts"] if item["about"] == shouter},
            opinion_of(actor(world, target), shouter, world["time"]) < -40.0) == (True, True)


def test_a_shout_counts_in_the_heat_of_a_row() -> None:
    world = seated_talk()
    foes(world)
    heated(world)
    say(world, "shout")
    assert heat(scene_of(world)) == 2


def turned_heads(world: dict[str, Any]) -> list[str]:
    """Who outside Ada's scene turned toward a sound or was alerted to it."""
    return sorted({event["actor_id"] for event in world["events"] if event["type"] in ("interrupted", "alerted")}
                  - {"ada", "bea"})


@pytest.mark.parametrize("act, turned", [
    pytest.param("insult", [], id="an-insult-turns-no-heads-across-the-hall"),
    pytest.param("shout", ["cid", "dan"], id="a-shout-turns-the-whole-hall"),
])
def test_a_shout_turns_heads_across_the_hall_that_an_insult_does_not(act: str, turned: list[str]) -> None:
    # Ada alone dislikes Bea and holds the grudge, so Bea does not answer in kind: no quarrel, which is loud, is logged.
    world = seated_talk()
    actor(world, "ada")["relations"]["bea"] = {"name": "Bea", "opinion": -40.0, "familiarity": "acquaintance"}
    grudge_held_by(world, "ada", "bea")
    assert say(world, act) == "ada"
    assert turned_heads(world) == turned
