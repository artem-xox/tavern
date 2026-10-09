"""The requests in flight to the models, and the tick that asks, drops, delivers and applies them.

Both runners of an evening (the live server and the headless lockstep) play the same tick, in
this order: drop decisions an interrupt overtook, apply those that came back, ask the visitors
free to decide, deliver written lines, claim and ask the next lines, then take intentions the same
way. They differ only in when an answer arrives, which a `Courier` decides.
"""

from collections.abc import Callable, Coroutine, Mapping, Sequence
from contextlib import suppress
import asyncio
from typing import Any, Protocol

from tavern.evening.decisions import apply_decision, decision_requests, free_to_decide, stale_requests
from tavern.hall.state import World, find_actor
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.goals import settle_goals
from tavern.mind.intentions import (UNMETERED, IntentionRules, Intender, deliver_intention, intention_requests,
                                    stale_intentions)
from tavern.social.invitations import answer_options
from tavern.social.turns import TurnResult, claim_turns, deliver_turn, next_speaker

# One answer in flight. What it is belongs to the courier: a task live, a stored coroutine in lockstep.
Ticket = Any

# Asks for a visitor's next decision from their observation; for a turn from the speaker's view.
Decide = Callable[[Mapping[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
Write = Callable[[Mapping[str, Any]], Coroutine[Any, Any, TurnResult]]
# Asks how an invitee answers: their observation, the pending invitation and the answers open to them.
Answer = Callable[[Mapping[str, Any], Mapping[str, Any], Sequence[str]], Coroutine[Any, Any, dict[str, Any]]]


class Courier(Protocol):
    """Carries a request to a model and says when its answer is back.

    `send` starts a request (a coroutine) at game time `now`; with `strict`, a failure of the
    request is not kept for delivery but stops the run, as for a malformed decision request in
    a headless evening. `ready` tells whether the answer has arrived by `now`. `outcome` hands
    the answer over as a callable that returns it or raises the request's error, as
    `decisions.apply_decision`, `turns.deliver_turn` and `intentions.deliver_intention` expect.
    `cancel` abandons a request an event overtook. `drain` waits for requests still in flight.
    """

    def send(self, request: Coroutine[Any, Any, Any], now: float, strict: bool = False) -> Ticket: ...

    def ready(self, ticket: Ticket, now: float) -> bool: ...

    def outcome(self, ticket: Ticket) -> Callable[[], Any]: ...

    def cancel(self, ticket: Ticket) -> None: ...

    async def drain(self, tickets: list[Ticket]) -> None: ...


class TaskCourier:
    """The live courier: each request runs as an asyncio task and is back when the task is done."""

    def send(self, request: Coroutine[Any, Any, Any], now: float, strict: bool = False) -> asyncio.Task[Any]:
        """Start the request on the running loop."""
        return asyncio.create_task(request)

    def ready(self, ticket: asyncio.Task[Any], now: float) -> bool:
        """Tell whether the task is done."""
        return ticket.done()

    def outcome(self, ticket: asyncio.Task[Any]) -> Callable[[], Any]:
        """Return the task's `result`, which raises its error."""
        return ticket.result

    def cancel(self, ticket: asyncio.Task[Any]) -> None:
        """Cancel the task."""
        ticket.cancel()

    async def drain(self, tickets: list[asyncio.Task[Any]]) -> None:
        """Wait for the tasks to settle, whatever became of them."""
        if tickets:
            await asyncio.gather(*tickets, return_exceptions=True)


class MindLoop:
    """The model requests of one evening in flight: decisions, conversation lines and intentions.

    The dictionaries are public because the runtimes and their tests read them: `pending` holds
    per visitor a decision's (ticket, revision); `asked_at` the game time it was asked;
    `writing` per claimed turn (scene ID, turn index) its ticket; `intending` per guest an
    intention's (ticket, asked at, view).
    """

    def __init__(self, courier: Courier, decide: Decide, write: Write, intender: Intender | None,
                 rules: IntentionRules, answer: Answer | None = None) -> None:
        """Create a loop with nothing in flight.

        Args:
            courier: Carries requests and says when answers are back.
            decide: Asks for a decision from an observation.
            write: Asks for a line from a speaker's view.
            intender: Writes intentions; None offline, which asks for none.
            rules: When guests take stock.
            answer: Asks how an invitee answers; None leaves the answer to the line writer, as before.
        """
        self.courier, self.decide, self.write, self.answer = courier, decide, write, answer
        self.intender, self.rules = intender, rules
        self.pending: dict[str, tuple[Ticket, int]] = {}
        self.revisions: dict[str, int] = {}
        self.next_decision: dict[str, float] = {}
        self.asked_at: dict[str, float] = {}
        self.writing: dict[tuple[str, int], Ticket] = {}
        self.answering: dict[tuple[str, int], tuple[Ticket, dict[str, str]]] = {}
        self.answered: set[tuple[str, int]] = set()  # Answers asked once, whatever came of it: never asked twice.
        self.intending: dict[str, tuple[Ticket, float, dict[str, Any]]] = {}
        self.next_intention: dict[str, float] = {}
        self.made: dict[str, int] = {}

    def tick(self, world: World) -> list[tuple[str, Ticket]]:
        """Play one tick of requests against a world that has just stepped.

        Args:
            world: World updated in place by the answers that are delivered.

        Returns:
            The decision requests asked this tick, as (visitor ID, ticket), for a runner that
            measures them.
        """
        self._drop_stale_decisions(world)
        self._apply_decisions(world)
        asked = self._ask_decisions(world)
        self._deliver_answers(world)
        self._ask_answers(world)
        self._deliver_lines(world)
        self._ask_lines(world)
        if self.intender is not None:
            self._take_stock(world, self.intender)
        return asked

    def overrule(self, actor_id: str) -> None:
        """Make a visitor's pending decision stale, because the operator acted for them.

        Args:
            actor_id: Visitor whose answer, when it arrives, is no longer wanted.
        """
        self.revisions[actor_id] = self.revisions.get(actor_id, 0) + 1

    def invalidate(self) -> None:
        """Cancel everything in flight and forget every revision, wait and pause."""
        for ticket in self._tickets():
            self.courier.cancel(ticket)
        for requests in (self.pending, self.writing, self.answering, self.answered, self.intending, self.next_intention, self.asked_at,
                         self.revisions, self.next_decision, self.made):
            requests.clear()

    async def close(self) -> None:
        """Cancel everything in flight and wait for it to settle."""
        tickets = self._tickets()
        self.invalidate()
        await self.courier.drain(tickets)

    def _tickets(self) -> list[Ticket]:
        return [*(ticket for ticket, _revision in self.pending.values()), *self.writing.values(),
                *(ticket for ticket, _ in self.answering.values()),
                *(ticket for ticket, _, _ in self.intending.values())]

    def _drop_stale_decisions(self, world: World) -> None:
        # An interrupted visitor's pending thought is dropped and they ask anew.
        for actor_id in stale_requests(world, self.asked_at):
            self.courier.cancel(self.pending.pop(actor_id)[0])
            del self.asked_at[actor_id]

    def _apply_decisions(self, world: World) -> None:
        for actor_id, (ticket, revision) in list(self.pending.items()):
            if not self.courier.ready(ticket, world["time"]):
                continue
            del self.pending[actor_id]
            self.asked_at.pop(actor_id, None)
            outcome, actor = self.courier.outcome(ticket), find_actor(world, actor_id)
            # An answer for a visitor who left, got busy, or was overruled meanwhile is dropped.
            if actor is None or revision != self.revisions.get(actor_id, 0) or not free_to_decide(world, actor):
                with suppress(asyncio.CancelledError, Exception):
                    outcome()
                continue
            self.next_decision[actor_id] = apply_decision(world, actor, outcome)

    def _ask_decisions(self, world: World) -> list[tuple[str, Ticket]]:
        asked = []
        for actor_id, observation in decision_requests(world, self.pending, self.next_decision):
            ticket = self.courier.send(self.decide(observation), world["time"], strict=True)
            self.pending[actor_id] = (ticket, self.revisions.get(actor_id, 0))
            self.asked_at[actor_id] = world["time"]
            asked.append((actor_id, ticket))
        return asked

    def _ask_answers(self, world: World) -> None:
        # An invitee whose line comes next first decides how they answer: the scene's claim holds their line back
        # until the answer is in (or the line's own timeout speaks a scripted one).
        if self.answer is None:
            return
        for scene in world["conversations"]:
            invitation = scene["invitation"]
            key = (scene["id"], len(scene["turns"]))
            invitee = find_actor(world, invitation["to"]) if invitation else None
            if (invitation is None or invitee is None or "answer" in invitation or key in self.answering or key in self.answered
                    or scene["writing"] is not None or scene["written"] is not None
                    or next_speaker(scene) != invitation["to"]):
                continue
            options = answer_options(world, scene, invitee)
            seen = {**observe_actor(world, invitee["id"]), "people": observe_people(world, invitee["id"])}
            scene["writing"] = {"turn": key[1], "speaker": invitee["id"], "since": world["time"]}
            self.answered.add(key)
            self.answering[key] = (self.courier.send(self.answer(seen, dict(invitation), options), world["time"]),
                                   dict(invitation))

    def _deliver_answers(self, world: World) -> None:
        for key, (ticket, asked) in list(self.answering.items()):
            if not self.courier.ready(ticket, world["time"]):
                continue
            del self.answering[key]
            outcome = self.courier.outcome(ticket)
            scene = next((item for item in world["conversations"] if item["id"] == key[0]), None)
            claim = scene["writing"] if scene is not None else None
            if scene is not None and claim is not None and (claim["turn"], claim["speaker"]) == (key[1], asked["to"]):
                scene["writing"] = None  # The line can be claimed now, with the answer if one came.
            current = scene["invitation"] if scene is not None else None
            try:
                answer = outcome()["answer"]
            except Exception:  # A failed request leaves the answer to the line writer, as without this stage.
                continue
            if scene is not None and current == asked and answer in answer_options(
                    world, scene, find_actor(world, asked["to"]) or {}):
                current["answer"] = answer

    def _deliver_lines(self, world: World) -> None:
        for key, ticket in list(self.writing.items()):
            if self.courier.ready(ticket, world["time"]):
                del self.writing[key]
                deliver_turn(world, *key, self.courier.outcome(ticket))

    def _ask_lines(self, world: World) -> None:
        for scene_id, turn, view in claim_turns(world):
            self.writing[(scene_id, turn)] = self.courier.send(self.write(view), world["time"])

    def _take_stock(self, world: World, intender: Intender) -> None:
        # Goals the world has decided end first, so a goal's end is what the next request is about.
        settle_goals(world)
        # Overtaken requests are dropped, finished ones kept, then new ones asked.
        for actor_id in stale_intentions(world, {key: asked for key, (_, asked, _) in self.intending.items()}):
            self.courier.cancel(self.intending.pop(actor_id)[0])
        for actor_id, (ticket, _, view) in list(self.intending.items()):
            if self.courier.ready(ticket, world["time"]):
                del self.intending[actor_id]
                self.next_intention[actor_id] = deliver_intention(
                    world, actor_id, view, self.courier.outcome(ticket), self.rules)
                if view["trigger"]["kind"] not in UNMETERED:
                    self.made[actor_id] = self.made.get(actor_id, 0) + 1
        for actor_id, view in intention_requests(world, self.intending, self.next_intention, self.rules, self.made):
            self.intending[actor_id] = (self.courier.send(intender(view), world["time"]), world["time"], view)
