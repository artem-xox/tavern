"""The decided answer reaches the line writers: the scripted rule follows it, and the model is told."""

from typing import Any

import pytest

from tavern.mind.haiku_turns import turn_content
from tavern.mind.scripted import scripted_turn
from tavern.social.turns import check_turn
from social_hall import actor
from test_invitation_answers import inviting, pending, scene_of
from tavern.social.turns import turn_view


def bea_to_speak(answer: str | None, bored: float = 80.0) -> dict[str, Any]:
    """The view for Bea's line after Ada's dice invitation, with her answer decided (or not)."""
    world = inviting("dice_together", ("darts",))
    actor(world, "bea")["needs"]["boredom"] = bored
    if answer:
        pending(world)["answer"] = answer
    scene = scene_of(world)
    assert scene is not None
    return turn_view(world, scene)


@pytest.mark.parametrize("answer, bored, act, invitation", [
    pytest.param("accept", 0.0, "accept", None, id="accepts-though-the-scripted-rule-would-decline"),
    pytest.param("decline", 80.0, "decline", None, id="declines-though-the-scripted-rule-would-accept"),
    pytest.param("counter:darts_together", 80.0, "invite", "darts_together", id="counters-with-an-invitation-of-its-own"),
])
def test_the_scripted_writer_says_the_decided_answer(answer: str, bored: float, act: str, invitation: str | None) -> None:
    turn = scripted_turn(bea_to_speak(answer, bored))
    assert (turn["act"], turn.get("invitation"), turn["addressee"]) == (act, invitation, "ada")


@pytest.mark.parametrize("bored, act", [
    pytest.param(80.0, "accept", id="a-bored-guest-accepts"),
    pytest.param(0.0, "decline", id="a-content-guest-declines"),
])
def test_without_a_decided_answer_the_scripted_rule_answers_as_before(bored: float, act: str) -> None:
    assert scripted_turn(bea_to_speak(None, bored))["act"] == act


@pytest.mark.parametrize("answer, expected", [
    pytest.param("accept", ["decided to accept", "say yes"], id="accept"),
    pytest.param("decline", ["decided to turn it down"], id="decline"),
    pytest.param("counter:darts_together", ["turn it down and offer", "play darts together", "invitation darts_together"],
                 id="counter"),
])
def test_the_model_is_told_the_answer_the_speaker_has_decided_on(answer: str, expected: list[str]) -> None:
    content = turn_content(bea_to_speak(answer))
    assert all(part in content for part in expected), content


def test_no_answer_decided_adds_no_such_nudge() -> None:
    assert "has decided to" not in turn_content(bea_to_speak(None))


def test_a_counter_passes_the_check_of_a_written_line() -> None:
    view = bea_to_speak("counter:darts_together")
    turn = check_turn(view, {"line": "Darts instead?", "act": "invite", "addressee": "ada", "topic": "darts",
                             "invitation": "darts_together"})
    assert turn["invitation"] == "darts_together"


def test_any_other_act_than_the_decided_one_is_refused() -> None:
    view = bea_to_speak("decline")
    with pytest.raises(ValueError):
        check_turn(view, {"line": "Gladly.", "act": "accept", "addressee": "ada", "topic": "dice"})
