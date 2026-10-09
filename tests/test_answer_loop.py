"""The invitee's answer in the tick of model requests: asked before their line, applied to the invitation, dropped when stale."""

from typing import Any

from tavern.evening.mind_loop import MindLoop
from tavern.mind.intentions import INTENTION_RULES
from test_answer_choice import settings
from test_invitation_answers import inviting, pending, scene_of
from test_mind_loop import ManualCourier, nothing


async def answering(observation: Any, invitation: Any, options: Any) -> dict[str, Any]:
    """Stand in for the choice of an answer; the manual courier never runs it."""
    return {"answer": "accept"}


def loop(courier: ManualCourier, answer: Any = answering) -> MindLoop:
    """A mind loop that asks for answers (or not, with None)."""
    return MindLoop(courier, nothing, nothing, None, INTENTION_RULES, answer=answer)  # type: ignore[arg-type]


def waiting_for_bea() -> tuple[MindLoop, ManualCourier, dict[str, Any]]:
    """A world in which Ada has invited Bea, a loop that has taken one tick, and its courier."""
    courier, world = ManualCourier(), inviting("dice_together", ("darts",))
    mind = loop(courier)
    mind.tick(world)
    return mind, courier, world


def answer_ticket(mind: MindLoop) -> Any:
    """The ticket of the answer in flight."""
    [(ticket, _)] = mind.answering.values()
    return ticket


def test_the_invitee_is_asked_for_an_answer_before_their_line_is_written() -> None:
    mind, _, world = waiting_for_bea()
    scene = scene_of(world)
    assert scene is not None
    assert (len(mind.answering), mind.writing, scene["writing"]["speaker"], "answer" in pending(world)) == (
        1, {}, "bea", False)


def test_they_are_asked_once() -> None:
    mind, courier, world = waiting_for_bea()
    before = len(courier.tickets)
    mind.tick(world)
    assert (len(mind.answering), len(courier.tickets)) == (1, before)


def test_a_decided_answer_is_kept_on_the_invitation_and_the_line_is_written_next() -> None:
    mind, _, world = waiting_for_bea()
    ticket = answer_ticket(mind)
    ticket.answer, ticket.ready = {"answer": "decline", "source": "jev", "scores": {}, "error": None}, True
    mind.tick(world)
    scene = scene_of(world)
    assert scene is not None
    assert (pending(world)["answer"], mind.answering, list(mind.writing)) == ("decline", {}, [(scene["id"], 1)])


def test_a_failed_request_leaves_the_answer_to_the_line_writer() -> None:
    mind, _, world = waiting_for_bea()
    ticket = answer_ticket(mind)
    ticket.error, ticket.ready = ValueError("boom"), True
    mind.tick(world)
    scene = scene_of(world)
    assert scene is not None
    assert ("answer" in pending(world), mind.answering, list(mind.writing)) == (False, {}, [(scene["id"], 1)])


def test_an_answer_for_an_invitation_that_changed_meanwhile_is_dropped() -> None:
    mind, _, world = waiting_for_bea()
    ticket = answer_ticket(mind)
    ticket.answer, ticket.ready = {"answer": "decline", "source": "jev", "scores": {}, "error": None}, True
    scene = scene_of(world)
    assert scene is not None
    scene["invitation"] = {"kind": "darts_together", "from": "ada", "to": "bea"}
    scene.update(writing=None)
    mind.tick(world)
    assert "answer" not in pending(world)


def test_an_answer_that_is_not_one_of_the_options_is_ignored() -> None:
    mind, _, world = waiting_for_bea()
    ticket = answer_ticket(mind)
    ticket.answer, ticket.ready = {"answer": "counter:waltz", "source": "jev", "scores": {}, "error": None}, True
    mind.tick(world)
    assert "answer" not in pending(world)


def test_without_an_answer_port_the_line_is_claimed_at_once_as_before() -> None:
    courier, world = ManualCourier(), inviting("dice_together", ("darts",))
    mind = loop(courier, answer=None)
    mind.tick(world)
    scene = scene_of(world)
    assert scene is not None
    assert (mind.answering, list(mind.writing)) == ({}, [(scene["id"], 1)])


def test_a_reset_cancels_the_answer_in_flight() -> None:
    mind, _, world = waiting_for_bea()
    ticket = answer_ticket(mind)
    mind.invalidate()
    assert (ticket.cancelled, mind.answering) == (True, {})


def test_the_setting_is_on_in_the_helper_config() -> None:
    assert settings()["answers"] is True


def test_in_a_headless_evening_the_invitees_own_choice_is_the_answer_their_line_gives() -> None:
    import asyncio
    from random import Random
    from tavern.evening.lockstep import Pace, run_evening
    from tavern.mind.agents import Evaluators
    from test_aim_choice import favouring
    world = inviting("dice_together", ("darts",))
    # Bea is bored enough that the scripted rule alone would accept; her own choice is to decline.
    evaluators = Evaluators(favouring("x"), favouring("x"), answers=favouring("decline"))
    result = asyncio.run(run_evening(world, settings(), Random(3), evaluators, Pace(0.1, 1.0, 12.0)))
    spoken = [item["message"] for item in result.events if item["type"] == "turn" and item["actor_id"] == "bea"][:1]
    assert (spoken[0].split("(")[1].split(")")[0], [e["type"] for e in result.events].count("invitation_declined")) == (
        "decline", 1)
