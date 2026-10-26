"""Stage lines in the tick of model requests: each claim asked of the stage writer once, spoken when it comes back."""

from typing import Any

from tavern.evening.mind_loop import MindLoop
from tavern.mind.intentions import INTENTION_RULES
from test_mind_loop import ManualCourier, nothing
from test_stage_lines import NUMBER, on_stage


async def staging(view: Any) -> list[str]:
    """Stand in for the stage writer; the manual courier never runs it."""
    return NUMBER


def asked() -> tuple[MindLoop, ManualCourier, dict[str, Any]]:
    """Ada up on the stage, and a loop that has taken a tick and asked the stage writer for her number."""
    courier, world = ManualCourier(), on_stage()
    mind = MindLoop(courier, nothing, nothing, None, INTENTION_RULES, stage=staging)  # type: ignore[arg-type]
    mind.tick(world)
    return mind, courier, world


def given(world: dict[str, Any]) -> list[str]:
    """The lines of the numbers given."""
    return [item["line"] for item in world["events"] if item["type"] == "gave_speech"]


def test_a_performer_on_the_stage_is_asked_for_once() -> None:
    mind, courier, world = asked()
    before = len(courier.tickets)
    mind.tick(world)
    assert (len(mind.staging), len(courier.tickets) - before) == (1, 0)


def test_the_number_is_spoken_when_its_words_come_back_and_the_heckler_is_asked_next() -> None:
    mind, _, world = asked()
    [(ticket, _claim)] = mind.staging.values()
    ticket.answer, ticket.ready = NUMBER, True
    mind.tick(world)
    assert (given(world), [key[:2] for key in mind.staging]) == ([" ".join(NUMBER)], [("heckle", "cid")])


def test_everything_in_flight_is_forgotten_on_invalidate() -> None:
    mind, _, world = asked()
    mind.invalidate()
    assert (mind.staging, mind.staged) == ({}, set())
