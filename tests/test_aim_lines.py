"""What a guest came for reaches the line writers: the model's moment and prefix, and the scripted rule."""

from typing import Any

import pytest

from tavern.hall.world import create_world, start_action
from tavern.mind.haiku_turns import turn_content
from tavern.mind.scripted import scripted_turn
from tavern.mind.turn_prompt import shared_prefix
from tavern.social.conversation import ACTS
from tavern.social.turns import claim_turns
from social_hall import actor, advance, command, know, say, spotted_hall


def met(aim: str, facts: dict[str, str] | None = None, opinion: float | None = None) -> dict[str, Any]:
    """Ada, who came to talk to Bea with an aim, and the view for her first line after a greeting."""
    world = create_world(spotted_hall(), 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    know(world, "ada", "darts", "tap")
    know(world, "bea", "darts")
    ada = actor(world, "ada")
    for fact_id, topic in (facts or {}).items():
        ada["knowledge"]["facts"][fact_id] = {"topic": topic, "told_as": "Fever in the river villages.",
                                              "heard_from": None, "heard_at": 0.0, "confidence": 1.0, "hops": 0,
                                              "overheard": False}
    if opinion is not None:
        ada["relations"]["bea"] = {"name": "Bea", "opinion": opinion, "familiarity": "acquaintance"}
    assert start_action(world, "ada", {**command("talk", "bea"), "aim": aim})["accepted"]
    say(world, "greet")
    say(world, "greet")
    return world


def view_of(world: dict[str, Any]) -> dict[str, Any]:
    """The view for the next line."""
    [(_, _, view)] = claim_turns(world)
    return view


@pytest.mark.parametrize("aim, facts, expected", [
    pytest.param("win_over", None, ["came over to make a good impression on Bea", "Acts that fit: compliment, small_talk"],
                 id="a-plain-aim-lists-the-acts-offered-now"),
    pytest.param("tell_news:fever", {"fever": "the fever"},
                 ["came over to tell Bea the news of the fever", "share_news", "fact_id fever"], id="news-names-its-fact"),
    pytest.param("invite:darts_together", None,
                 ["came over to invite Bea to play darts together", "invite", "invitation darts_together"],
                 id="an-invitation-names-its-kind"),
])
def test_the_moment_tells_the_writer_what_the_speaker_came_for(aim: str, facts: dict[str, str] | None,
                                                               expected: list[str]) -> None:
    content = turn_content(view_of(met(aim, facts)))
    assert all(part in content for part in expected), content


def test_passing_the_time_needs_no_nudge() -> None:
    assert "came over to" not in turn_content(view_of(met("pass_time")))


def test_the_nudge_stops_once_the_aim_is_said() -> None:
    world = met("win_over")
    say(world, "compliment")
    say(world, "greet")
    assert "came over to" not in turn_content(view_of(world))


def test_the_prefix_asks_for_what_the_speaker_came_for_without_inventing_more() -> None:
    prefix = shared_prefix({name: act.meaning for name, act in ACTS.items()})
    assert "came over to" in prefix and "never offer or promise" in prefix


@pytest.mark.parametrize("aim, facts, opinion, act, extra", [
    pytest.param("win_over", None, None, "compliment", {}, id="winning-over-pays-a-compliment"),
    pytest.param("tell_news:fever", {"fever": "the fever", "robbery": "the robbery"}, None, "share_news",
                 {"fact_id": "fever"}, id="the-news-the-aim-names"),
    pytest.param("invite:darts_together", None, None, "invite", {"invitation": "darts_together"},
                 id="the-invitation-the-aim-names"),
    pytest.param("needle", None, -40.0, "insult", {}, id="a-needle-for-someone-disliked"),
    pytest.param("have_it_out", None, -40.0, "complain", {}, id="having-it-out-starts-with-a-complaint"),
    pytest.param("thank", None, None, "compliment", {}, id="a-thanks"),
])
def test_the_scripted_writer_says_what_the_speaker_came_for(aim: str, facts: dict[str, str] | None,
                                                            opinion: float | None, act: str,
                                                            extra: dict[str, str]) -> None:
    turn = scripted_turn(view_of(met(aim, facts, opinion)))
    assert (turn["act"], {key: turn[key] for key in extra}) == (act, extra)
