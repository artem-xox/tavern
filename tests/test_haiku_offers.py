"""Haiku asks with the same cached prefix and schema whatever acts the moment allows."""

from typing import Any

import pytest

from tavern.social.conversation import ACTS
from tavern.mind.haiku_turns import RejectedTurn, parse_turn, turn_question
from tavern.social.invitations import KINDS


def view(acts: list[str], invitations: list[str]) -> dict[str, Any]:
    speaker = {"id": "ada", "name": "Ada", "needs": {"thirst": 10.0, "fatigue": 10.0, "bladder": 10.0, "social": 50.0, "boredom": 10.0}, "traits": {}, "visit": {"beers": 0},
               "places": [], "card": None, "portrait": "", "feelings": "", "drunkenness": 0.0, "company": [],
               "opinions": {"bea": 0.0}}
    return {"conversation": {"id": 1, "topic": "the road", "turn": 1, "invitation": None, "turns": [],
                             "participants": [{"id": "ada", "name": "Ada", "known": True},
                                              {"id": "bea", "name": "Bea", "known": True}]},
            "speaker": speaker, "acts": {name: ACTS[name].meaning for name in acts},
            "invitations": invitations, "seed": 1}


def answer(act: str, invitation: str | None = None) -> dict[str, Any]:
    return {"line": "Come, a round of darts?", "act": act, "addressee": "bea", "topic": "darts",
            "invitation": invitation}


def test_prefix_and_schema_do_not_change_with_what_is_offered() -> None:
    narrow = turn_question(view(["greet", "small_talk"], []))
    wide = turn_question(view(["greet", "small_talk", "invite", "insult"], ["darts_together"]))
    assert (narrow["system"][0], narrow["schema"]) == (wide["system"][0], wide["schema"])
    assert set(narrow["schema"]["properties"]["act"]["enum"]) == set(ACTS)
    assert set(narrow["schema"]["properties"]["invitation"]["anyOf"][0]["enum"]) == set(KINDS)


def test_the_moment_lists_only_what_is_offered_now() -> None:
    content = turn_question(view(["greet", "invite"], ["darts_together"]))["content"]
    assert ("invite" in content, "darts_together" in content, "insult" in content) == (True, True, False)


@pytest.mark.parametrize(("acts", "invitations", "given", "expected"), [
    pytest.param(["small_talk"], [], answer("small_talk"), None, id="no-invitation"),
    pytest.param(["invite"], ["darts_together"], answer("invite", "darts_together"), "darts_together", id="invite"),
])
def test_an_answer_with_a_null_or_offered_invitation_is_accepted(acts: list[str], invitations: list[str],
                                                                given: dict[str, Any], expected: str | None) -> None:
    assert parse_turn(view(acts, invitations), given).get("invitation") == expected


@pytest.mark.parametrize(("acts", "invitations", "given"), [
    pytest.param(["small_talk"], [], answer("insult"), id="act-not-offered"),
    pytest.param(["invite"], ["join_table"], answer("invite", "darts_together"), id="kind-not-offered"),
    pytest.param(["small_talk"], [], answer("small_talk", "darts_together"), id="invitation-without-invite"),
])
def test_an_answer_outside_the_offer_is_rejected(acts: list[str], invitations: list[str],
                                                 given: dict[str, Any]) -> None:
    with pytest.raises(RejectedTurn):
        parse_turn(view(acts, invitations), given)


def test_the_moment_names_the_people_an_answer_may_address() -> None:
    content = turn_question(view(["small_talk"], []))["content"]
    assert 'addressee must be null or one of these, written exactly as here: "Bea".' in content
