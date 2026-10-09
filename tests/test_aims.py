"""Aims: what a guest means by a social option, which aims are offered, and when one is carried out."""

from typing import Any

import pytest

from tavern.body.activities import ACTIVITIES
from tavern.social.aims import AIM_VERBS, AIMS, aim_candidates, aim_words, carried_out, check_aim, offered_aims
from tavern.social.conversation import ACTS
from tavern.social.invitations import KINDS
from tavern.social.responses import RESPONSES
from tavern.social.thoughts import THOUGHTS

NOW = 100.0


def fact(topic: str, confidence: float = 1.0) -> dict[str, Any]:
    """A news item Ada holds."""
    return {"topic": topic, "told_as": "x", "heard_from": None, "heard_at": 0.0, "confidence": confidence,
            "hops": 0, "overheard": False}


def thought(kind: str, about: str = "bea", age: float = 10.0) -> dict[str, Any]:
    """A thought of Ada's about Bea that began `age` seconds ago."""
    rule = THOUGHTS[kind]
    return {"kind": kind, "about": about, "text": "x", "mood": rule.mood, "opinion": rule.opinion,
            "expires_at": NOW - age + rule.seconds, "source_event": "x"}


def sight(opinion: float = 0.0, familiarity: str = "acquaintance", facts: dict[str, Any] | None = None,
          thoughts: list[dict[str, Any]] | None = None, objects: list[dict[str, Any]] | None = None,
          holding: dict[str, int] | None = None, beer: int = 0, seat_id: str | None = None) -> dict[str, Any]:
    """Ada's observation, with Bea beside her."""
    return {"actor": {"id": "ada", "name": "Ada", "inventory": {"beer": beer}, "seat_id": seat_id,
                      "relations": {"bea": {"name": "Bea", "opinion": opinion, "familiarity": familiarity}},
                      "thoughts": thoughts or [], "knowledge": {"objects": {}, "cells": [], "facts": facts or {}}},
            "objects": objects or [], "visitors": [], "time": NOW, "on_errands": [],
            "people": [{"id": "bea", "name": "Bea", "beside": True, "holding": holding or {}}]}


def place(kind: str, object_id: str, **fields: Any) -> dict[str, Any]:
    """A known place."""
    return {"id": object_id, "kind": kind, "x": 3, "y": 2, "reserved_by": None, **fields}


TALK = {"id": "talk:bea", "verb": "talk", "target_id": "bea"}
DARTS = place("darts", "darts")
DICE = place("dice_table", "dice", game=None)
TAP = place("tap", "tap", stock=5)


@pytest.mark.parametrize("view, expected", [
    pytest.param(sight(familiarity="friend"), ["pass_time"], id="a-friend-needs-no-winning-over"),
    pytest.param(sight(), ["pass_time", "win_over"], id="an-acquaintance"),
    pytest.param(sight(familiarity="stranger"), ["pass_time", "win_over"], id="a-stranger"),
    pytest.param(sight(opinion=-5.0), ["pass_time"], id="a-slight-dislike-is-neither"),
    pytest.param(sight(opinion=-10.0), ["pass_time", "needle"], id="a-disliked-person"),
    pytest.param(sight(familiarity="friend", facts={"fever": fact("the fever")}), ["pass_time", "tell_news:fever"],
                 id="one-fact"),
    pytest.param(sight(familiarity="friend", facts={"a": fact("x", 0.5), "b": fact("y", 0.9), "c": fact("z", 0.7)}),
                 ["pass_time", "tell_news:b", "tell_news:c"], id="three-facts-the-top-two-by-confidence"),
    pytest.param(sight(familiarity="friend", facts={"b": fact("y"), "a": fact("x")}),
                 ["pass_time", "tell_news:a", "tell_news:b"], id="equal-confidence-goes-by-id"),
    pytest.param(sight(familiarity="friend", objects=[DARTS]), ["pass_time", "invite:darts_together"],
                 id="darts-known"),
    pytest.param(sight(familiarity="friend", objects=[DICE]), ["pass_time", "invite:dice_together"],
                 id="a-free-dice-table"),
    pytest.param(sight(familiarity="friend", objects=[{**DICE, "game": {"players": ["cid", "dan"]}}]), ["pass_time"],
                 id="a-dice-table-in-use"),
    pytest.param(sight(familiarity="friend", objects=[TAP]), ["pass_time", "invite:buy_drink"],
                 id="an-ale-for-someone-with-empty-hands"),
    pytest.param(sight(familiarity="friend", objects=[TAP], holding={"beer": 1}), ["pass_time"],
                 id="no-ale-for-someone-who-has-one"),
    pytest.param(sight(familiarity="friend", objects=[TAP], beer=1), ["pass_time", "invite:buy_drink"],
                 id="a-mug-in-one-hand-leaves-the-other-free"),
    pytest.param(sight(familiarity="friend", objects=[TAP], beer=2), ["pass_time"], id="no-free-hand-to-fetch-with"),
    pytest.param(sight(familiarity="friend", objects=[place("tap", "tap", stock=0)]), ["pass_time"],
                 id="a-dry-tap"),
    pytest.param(sight(familiarity="friend", thoughts=[thought("lost_at_dice")], objects=[DICE]),
                 ["pass_time", "invite:dice_together", "rematch"], id="a-lost-game-and-a-free-dice-table"),
    pytest.param(sight(familiarity="friend", thoughts=[thought("lost_at_dice")]), ["pass_time"],
                 id="a-lost-game-and-no-dice-table-known"),
    pytest.param(sight(familiarity="friend", thoughts=[thought("insulted")]), ["pass_time", "needle", "have_it_out"],
                 id="a-fresh-wrong-which-also-sours-the-opinion"),
    pytest.param(sight(familiarity="friend", thoughts=[thought("treated")]), ["pass_time", "thank"],
                 id="a-fresh-kindness"),
    pytest.param(sight(familiarity="friend", thoughts=[{**thought("insulted"), "answered": True}]),
                 ["pass_time", "needle"], id="an-answered-wrong-calls-for-nothing"),
    pytest.param(sight(familiarity="friend", thoughts=[thought("insulted", age=500.0)]), ["pass_time"],
                 id="an-old-wrong"),
])
def test_the_aims_a_guest_may_take_to_a_person(view: dict[str, Any], expected: list[str]) -> None:
    assert offered_aims(view, TALK) == expected


def test_every_kind_of_thought_that_calls_for_an_answer_has_an_aim() -> None:
    from tavern.social.aims import ANSWER_AIMS
    assert set(ANSWER_AIMS) == set(RESPONSES)


def test_the_table_names_only_known_acts_and_invitations() -> None:
    from tavern.social.aims import NEEDLED
    from tavern.social.conversation import DISLIKED
    assert NEEDLED == DISLIKED
    assert (all(set(kind.acts) <= set(ACTS) for kind in AIMS.values()),
            {kind.invitation for kind in AIMS.values() if kind.invitation} <= set(KINDS),
            set(AIM_VERBS) <= set(ACTIVITIES)) == (True, True, True)


@pytest.mark.parametrize("aim, name, expected", [
    pytest.param("pass_time", "Bea", "pass the time with Bea", id="plain"),
    pytest.param("tell_news:fever", "Bea", "tell Bea the news of the fever", id="news-by-topic"),
    pytest.param("invite:dice_together", "Bea", "invite Bea to play a game of dice", id="an-invitation"),
    pytest.param("rematch", "Bea", "ask Bea for a rematch at dice", id="a-rematch"),
])
def test_an_aim_is_told_in_words(aim: str, name: str, expected: str) -> None:
    assert aim_words(aim, name, {"fever": "the fever"}) == expected


def test_aim_candidates_name_their_action() -> None:
    assert aim_candidates(TALK, ["pass_time", "win_over"]) == [
        {"id": "pass_time@talk:bea", "verb": "talk", "target_id": "bea", "aim": "pass_time"},
        {"id": "win_over@talk:bea", "verb": "talk", "target_id": "bea", "aim": "win_over"}]


def turn(speaker: str, act: str, **fields: Any) -> dict[str, Any]:
    """A spoken line."""
    return {"speaker": speaker, "addressee": None, "line": "x", "act": act, "time": 1.0, **fields}


@pytest.mark.parametrize("aim, turns, expected", [
    pytest.param("pass_time", [], False, id="nothing-said-yet"),
    pytest.param("pass_time", [turn("ada", "small_talk")], True, id="small-talk"),
    pytest.param("pass_time", [turn("bea", "small_talk")], False, id="said-by-someone-else"),
    pytest.param("tell_news:fever", [turn("ada", "share_news", fact_id="fever")], True, id="the-news-told"),
    pytest.param("tell_news:fever", [turn("ada", "share_news", fact_id="robbery")], False, id="other-news-told"),
    pytest.param("invite:darts_together", [turn("ada", "invite", invitation="darts_together")], True,
                 id="the-invitation-made"),
    pytest.param("invite:darts_together", [turn("ada", "invite", invitation="buy_drink")], False,
                 id="another-invitation-made"),
    pytest.param("rematch", [turn("ada", "invite", invitation="dice_together")], True, id="a-dice-invitation"),
    pytest.param("rematch", [turn("ada", "invite", invitation="darts_together")], False, id="a-darts-invitation"),
    pytest.param("needle", [turn("ada", "greet"), turn("ada", "insult")], True, id="an-insult-after-a-greeting"),
])
def test_an_aim_is_carried_out_by_the_speaker_saying_one_of_its_acts(
        aim: str, turns: list[dict[str, Any]], expected: bool) -> None:
    assert carried_out(aim, "ada", turns) is expected


@pytest.mark.parametrize("aim", [
    pytest.param("nothing", id="unknown-kind"),
    pytest.param("tell_news", id="news-without-a-fact"),
    pytest.param("invite:waltz", id="unknown-invitation"),
    pytest.param("pass_time:extra", id="detail-on-a-kind-without-one"),
    pytest.param("", id="empty"),
])
def test_an_aim_that_is_not_one_fails_loudly(aim: str) -> None:
    with pytest.raises(ValueError):
        check_aim(aim)


@pytest.mark.parametrize("aim", [
    pytest.param("pass_time", id="plain"),
    pytest.param("tell_news:fever", id="news"),
    pytest.param("invite:dice_together", id="invitation"),
    pytest.param("rematch", id="rematch"),
])
def test_a_proper_aim_passes_the_check(aim: str) -> None:
    check_aim(aim)
