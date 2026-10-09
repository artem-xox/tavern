"""Choosing how to answer an invitation: the options, the model's or the local scores, and the Jev question."""

import asyncio
from random import Random
from typing import Any

import httpx
import pytest

from tavern.adapters.jev import JevError, evaluate_answers, evaluate_answers_metered, request_body
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.agents import Evaluators, choose_answer
from tavern.mind.local_policy import local_answer_scores
from tavern.mind.selection import read_answers
from tavern.social.invitations import answer_options
from social_hall import actor
from test_invitation_answers import inviting, pending, scene_of
from test_aim_choice import favouring, refusing


def bea_asked(kind: str = "dice_together", knows: tuple[str, ...] = ("darts",)) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Bea's observation after Ada's invitation, the invitation and her options."""
    world = inviting(kind, knows)
    scene = scene_of(world)
    assert scene is not None
    view = {**observe_actor(world, "bea"), "people": observe_people(world, "bea")}
    return view, dict(pending(world)), answer_options(world, scene, actor(world, "bea"))


def settings(key: str | None = "test", **fields: Any) -> dict[str, Any]:
    """The AI config with the answers stage on."""
    return {"typesafe_api_key": key, "model": "jev-latest", "timeout": 2.0, "temperature": 0.0, "answers": True, **fields}


def decide(evaluators: Evaluators, config: dict[str, Any] | None = None, **view_fields: Any) -> dict[str, Any]:
    """Run the choice of an answer."""
    view, invitation, options = bea_asked(**view_fields)
    return asyncio.run(choose_answer(view, invitation, options, config or settings(), Random(0), evaluators))


def test_the_answer_is_chosen_among_the_options_and_named() -> None:
    asked: list[Any] = []
    result = decide(Evaluators(favouring("x"), favouring("x"), answers=favouring("counter:darts", asked)))
    assert (result["answer"], result["source"], result["error"], asked) == (
        "counter:darts_together", "jev", None, [["accept", "decline", "counter:darts_together", "counter:move_together"]])


def test_a_failing_evaluator_falls_back_to_the_local_scores_and_says_so() -> None:
    result = decide(Evaluators(favouring("x"), favouring("x"), answers=refusing))
    assert (result["source"], result["error"], result["answer"] in result["scores"]) == (
        "local", "Jev request timed out", True)


def test_without_a_key_the_answer_is_chosen_locally_and_no_model_is_asked() -> None:
    result = decide(Evaluators(favouring("x"), favouring("x"), answers=refusing), settings(key=None))
    assert (result["source"], result["error"]) == ("local", None)


def test_a_key_with_the_setting_on_and_no_answers_evaluator_fails_loudly() -> None:
    with pytest.raises(ValueError, match="answers"):
        decide(Evaluators(favouring("x"), favouring("x")))


@pytest.mark.parametrize("config, expected", [
    pytest.param({}, False, id="absent-is-off"),
    pytest.param({"answers": True}, True, id="on"),
])
def test_the_answers_setting_is_read_from_the_config(config: dict[str, Any], expected: bool) -> None:
    assert read_answers(config) is expected


def test_an_answers_setting_that_is_not_a_bool_fails_loudly() -> None:
    with pytest.raises(ValueError, match="answers"):
        read_answers({"answers": "yes"})


def candidates(*options: str) -> list[dict[str, Any]]:
    """Answer candidates, as the choice builds them."""
    return [{"id": option, "verb": option.partition(":")[0], "target_id": "ada", "answer": option} for option in options]


@pytest.mark.parametrize("fields, answer, expected", [
    pytest.param({"boredom": 100.0}, "accept", 0.15 + 0.65 + 0.0, id="a-bored-guest-welcomes-a-game"),
    pytest.param({"boredom": 0.0}, "accept", 0.15, id="a-content-guest-hardly-does"),
    pytest.param({"boredom": 100.0, "opinion": 40.0}, "accept", 0.15 + 0.65 + 0.1, id="liking-the-inviter-adds"),
    pytest.param({"boredom": 100.0, "opinion": -40.0}, "accept", 0.15 + 0.65 - 0.1, id="disliking-the-inviter-subtracts"),
    pytest.param({"sociability": 1.0}, "decline", 0.3, id="a-sociable-guest-declines-least"),
    pytest.param({"sociability": 0.0}, "decline", 0.5, id="a-loner-declines-most"),
    pytest.param({"boredom": 100.0}, "counter:darts_together", 0.15 + 0.65 - 0.1, id="a-counter-is-worth-its-kind-less-a-little"),
])
def test_the_local_answer_scores_follow_what_the_invitation_leads_to_and_the_guest(
        fields: dict[str, float], answer: str, expected: float) -> None:
    view, invitation, options = bea_asked("dice_together", ("darts",))
    bea = view["actor"]
    bea["needs"].update({"boredom": fields.get("boredom", 50.0), "social": 50.0})
    bea["traits"].update(sociability=fields.get("sociability", 0.5))
    bea["relations"] = {"ada": {"name": "Ada", "opinion": fields.get("opinion", 0.0), "familiarity": "acquaintance"}}
    bea["thoughts"] = []
    scores = local_answer_scores(view, invitation, candidates(*options))
    assert scores[answer] == pytest.approx(expected)


def jev_view() -> dict[str, Any]:
    """What the adapter is given for an answer question."""
    return {"situation": "Bea sits at a table.", "options": {"accept": "accept Ada's invitation to play a game of dice"},
            "self": {"name": "Bea"}}


def test_the_answer_question_asks_how_natural_the_answer_is() -> None:
    body = request_body(jev_view(), candidates("accept"), "jev-latest", answers=True)
    text = body["questions"]["accept"]["instructions"]
    assert ("accept Ada's invitation to play a game of dice" in text, "has been invited" in text,
            len(body["questions"]["accept"]["criteria"])) == (True, True, 5)


def test_answers_are_scored_by_the_jev_adapter() -> None:
    payload = {"answers": {"accept": {"type": "score", "score": 3}}, "usage": {"input_tokens": 9, "output_tokens": 1}}

    async def run() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
            config = {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 2.0}
            return (await evaluate_answers(jev_view(), candidates("accept"), config, client),
                    await evaluate_answers_metered(jev_view(), candidates("accept"), config, client))
    assert asyncio.run(run()) == ({"accept": 0.75}, ({"accept": 0.75}, {"input_tokens": 9, "output_tokens": 1}))


def test_a_request_asks_one_kind_of_question_only() -> None:
    with pytest.raises(ValueError):
        request_body(jev_view(), candidates("accept"), "jev-latest", aims=True, answers=True)
