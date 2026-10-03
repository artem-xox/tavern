"""The tick of model requests: who is asked, whose late answer is dropped, and what a reset cancels."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import pytest

from tavern.intentions import INTENTION_RULES
from tavern.lockstep import LockstepCourier
from tavern.mind_loop import MindLoop
from tavern.world import create_world, step_world


@dataclass
class Ticket:
    answer: Any = None
    error: Exception | None = None
    ready: bool = False
    cancelled: bool = False
    strict: bool = False


@dataclass
class ManualCourier:
    """A fake courier that answers only when the test says so."""

    tickets: list[Ticket] = field(default_factory=list)
    drained: list[Ticket] = field(default_factory=list)

    def send(self, request: Coroutine[Any, Any, Any], now: float, strict: bool = False) -> Ticket:
        request.close()  # Nothing runs: the test hands over the answer.
        self.tickets.append(Ticket(strict=strict))
        return self.tickets[-1]

    def ready(self, ticket: Ticket, now: float) -> bool:
        return ticket.ready

    def outcome(self, ticket: Ticket) -> Callable[[], Any]:
        def result() -> Any:
            if ticket.error is not None:
                raise ticket.error
            return ticket.answer
        return result

    def cancel(self, ticket: Ticket) -> None:
        ticket.cancelled = True

    async def drain(self, tickets: list[Ticket]) -> None:
        self.drained.extend(tickets)


async def nothing(_: Any) -> dict[str, Any]:
    return {}


def hall(*names: str) -> dict[str, Any]:
    return create_world({"width": 8, "height": 6, "tile_size": 32, "blocked": [], "objects": [],
                         "actors": [{"id": name, "name": name.title(), "x": index + 1, "y": 1}
                                    for index, name in enumerate(names)]})  # type: ignore[return-value]


def loop(courier: ManualCourier) -> MindLoop:
    return MindLoop(courier, nothing, nothing, None, INTENTION_RULES)  # type: ignore[arg-type]


def decision(verb: str = "wait") -> dict[str, Any]:
    return {"action": {"id": verb, "verb": verb, "target_id": None}, "source": "local", "scores": {}, "error": None}


def test_each_free_visitor_is_asked_once_until_they_answer() -> None:
    courier, world = ManualCourier(), hall("ada", "bea")
    mind = loop(courier)
    mind.tick(world)
    mind.tick(world)
    assert (len(courier.tickets), sorted(mind.pending)) == (2, ["ada", "bea"])
    assert all(ticket.strict for ticket in courier.tickets)


def test_a_returned_answer_acts_and_the_visitor_is_asked_again_later() -> None:
    courier, world = ManualCourier(), hall("ada")
    mind = loop(courier)
    mind.tick(world)
    courier.tickets[0].answer, courier.tickets[0].ready = decision("wait"), True
    mind.tick(world)
    assert world["actors"][0]["action"]["verb"] == "wait"
    assert "ada" not in mind.pending


def test_a_failed_answer_is_logged_and_does_not_stop_the_tick() -> None:
    courier, world = ManualCourier(), hall("ada")
    mind = loop(courier)
    mind.tick(world)
    courier.tickets[0].error, courier.tickets[0].ready = RuntimeError("model down"), True
    mind.tick(world)
    assert any("Decision failed" in event["message"] for event in world["events"])


def test_an_answer_for_a_visitor_who_left_is_dropped() -> None:
    courier, world = ManualCourier(), hall("ada")
    mind = loop(courier)
    mind.tick(world)
    courier.tickets[0].answer, courier.tickets[0].ready = decision(), True
    world["departed"].append(world["actors"].pop())
    mind.tick(world)
    assert (mind.pending, world["departed"][0]["action"]) == ({}, None)


def test_an_overruled_answer_is_dropped() -> None:
    courier, world = ManualCourier(), hall("ada")
    mind = loop(courier)
    mind.tick(world)
    mind.overrule("ada")
    courier.tickets[0].answer, courier.tickets[0].ready = decision(), True
    mind.tick(world)
    assert world["actors"][0]["action"] is None


def test_a_closing_call_cancels_the_pending_decision_and_asks_anew() -> None:
    courier, world = ManualCourier(), hall("ada")
    world["closes_at"] = 0.15
    mind = loop(courier)
    step_world(world, 0.1)
    mind.tick(world)
    step_world(world, 0.1)
    mind.tick(world)
    assert [ticket.cancelled for ticket in courier.tickets] == [True, False]


def test_invalidate_cancels_everything_and_forgets_it() -> None:
    courier, world = ManualCourier(), hall("ada", "bea")
    mind = loop(courier)
    mind.tick(world)
    mind.overrule("ada")
    mind.invalidate()
    assert all(ticket.cancelled for ticket in courier.tickets)
    assert (mind.pending, mind.revisions, mind.asked_at, mind.next_decision) == ({}, {}, {}, {})


def test_close_cancels_and_drains_what_was_in_flight() -> None:
    courier, world = ManualCourier(), hall("ada")
    mind = loop(courier)
    mind.tick(world)
    asyncio.run(mind.close())
    assert courier.drained == courier.tickets and courier.tickets[0].cancelled


async def answer(value: Any) -> Any:
    return value


async def failing(error: Exception) -> Any:
    raise error


@pytest.mark.parametrize("asked, now, due", [
    pytest.param(0.0, 0.9, False, id="before-the-latency"),
    pytest.param(0.0, 1.0, True, id="at-the-latency"),
    pytest.param(2.5, 3.5, True, id="later-ask"),
])
def test_a_lockstep_answer_is_due_one_virtual_latency_after_it_was_asked(asked: float, now: float, due: bool) -> None:
    courier = LockstepCourier(1.0)
    ticket = courier.send(answer("yes"), asked)
    asyncio.run(courier.settle())
    assert (courier.ready(ticket, now), courier.outcome(ticket)()) == (due, "yes")


def test_lockstep_requests_run_in_the_order_they_were_sent() -> None:
    order: list[str] = []

    async def mark(name: str) -> str:
        order.append(name)
        return name

    courier = LockstepCourier(0.0)
    tickets = [courier.send(mark(name), 0.0) for name in ("first", "second", "third")]
    asyncio.run(courier.settle())
    assert (order, [courier.outcome(ticket)() for ticket in tickets]) == (
        ["first", "second", "third"], ["first", "second", "third"])


@pytest.mark.parametrize("strict, error, stops", [
    pytest.param(False, RuntimeError("model down"), False, id="failure-kept-for-delivery"),
    pytest.param(True, RuntimeError("bad request"), True, id="strict-failure-stops"),
    pytest.param(False, LookupError("no such record"), True, id="replay-miss-stops"),
    pytest.param(True, LookupError("no such record"), True, id="strict-replay-miss-stops"),
])
def test_lockstep_failures_stop_the_run_or_wait_for_delivery(strict: bool, error: Exception, stops: bool) -> None:
    courier = LockstepCourier(0.0)
    ticket = courier.send(failing(error), 0.0, strict=strict)
    if stops:
        with pytest.raises(type(error)):
            asyncio.run(courier.settle())
        return
    asyncio.run(courier.settle())
    with pytest.raises(RuntimeError, match="model down"):
        courier.outcome(ticket)()


def test_a_lockstep_request_cancelled_before_it_ran_never_runs() -> None:
    ran: list[bool] = []

    async def mark() -> None:
        ran.append(True)

    courier = LockstepCourier(0.0)
    ticket = courier.send(mark(), 0.0)
    courier.cancel(ticket)
    asyncio.run(courier.settle())
    assert (ran, ticket.error) == ([], None)
