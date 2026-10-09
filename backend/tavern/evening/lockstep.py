"""Headless evenings in lockstep: fixed game-time steps and a fixed virtual model latency."""

from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
import math
from random import Random
from typing import Any, NotRequired, TypedDict

from tavern.evening.decisions import free_to_decide
from tavern.evening.mind_loop import MindLoop
from tavern.hall.staff import guests
from tavern.hall.state import World
from tavern.hall.world import step_world
from tavern.mind.agents import Evaluators, choose_action
from tavern.mind.intentions import INTENTION_RULES, Intender, IntentionRules
from tavern.mind.scripted import write_scripted_turn
from tavern.social.turns import TurnWriter


@dataclass(frozen=True)
class Pace:
    """How a headless evening advances, in game seconds.

    `step` is the time per tick, like the live server's tick. `model_latency` is the time
    between asking for a decision and acting on it, whatever the model's real speed, so a
    recorded evening replays exactly. `time_limit` is the game time that cuts the evening off.
    """

    step: float
    model_latency: float
    time_limit: float

    def __post_init__(self) -> None:
        if not 0 < self.step < math.inf:
            raise ValueError(f"Step must be a positive number of seconds, not {self.step!r}")
        if not 0 <= self.model_latency < math.inf:
            raise ValueError(f"Model latency must be a nonnegative number of seconds, not {self.model_latency!r}")
        if not 0 < self.time_limit < math.inf:
            raise ValueError(f"Time limit must be a positive number of seconds, not {self.time_limit!r}")


class Choice(TypedDict):
    """One stage of a decision: `kind` is `actions`, `seats` or `family`, as in recorded calls. `scores` holds
    the score of every option asked, by ID, in request order (`evening.choice_metrics` reads it)."""

    time: float
    actor_id: str
    kind: str
    source: str
    error: str | None
    scores: NotRequired[dict[str, float]]


class Spell(TypedDict):
    """A stretch of game time a guest spent stalled (see `run_evening`)."""

    actor_id: str
    start: float
    end: float


@dataclass(frozen=True)
class Evening:
    """What a headless evening produced.

    `events` is the complete event log in order, `choices` every decision stage asked for,
    `spells` every stalled stretch, `guests` everyone who was in the hall in order of first
    sight, `end_time` the game time it ended, and `gazes` how many times a guest turned to
    look at a sound: glances, alerts and interrupts alike.
    """

    events: list[dict[str, Any]]
    choices: list[Choice]
    spells: list[Spell]
    guests: list[str]
    end_time: float
    gazes: int = 0


@dataclass
class _Run:
    events: list[dict[str, Any]] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    spells: list[Spell] = field(default_factory=list)
    stalled_since: dict[str, float] = field(default_factory=dict)
    guests: list[str] = field(default_factory=list)
    gazes: set[tuple[str, int]] = field(default_factory=set)


@dataclass
class _Flight:
    # A request waiting for its turn at `settle`, then for its due time.
    request: Coroutine[Any, Any, Any]
    due: float
    strict: bool
    answer: Any = None
    error: Exception | None = None
    settled: bool = False


class LockstepCourier:
    """The headless courier: requests are answered at once, in the order they were sent, and
    delivered one fixed virtual latency after they were asked, whatever the model's real speed.

    A replay miss (`LookupError`) always stops the evening. So does any failure of a `strict`
    request, as a malformed decision request does; the live runtime would show it as "Decision
    failed". Other failures are kept and raised on delivery, where the world logs them.
    """

    def __init__(self, latency: float) -> None:
        """Create a courier.

        Args:
            latency: Game seconds between asking and delivering an answer.
        """
        self.latency = latency
        self._sent: list[_Flight] = []

    def send(self, request: Coroutine[Any, Any, Any], now: float, strict: bool = False) -> _Flight:
        """Take a request; it runs at the next `settle`."""
        flight = _Flight(request, now + self.latency, strict)
        self._sent.append(flight)
        return flight

    async def settle(self) -> None:
        """Run the requests sent since the last settle, in order.

        Raises:
            LookupError: A replayed request was not recorded.
            Exception: A strict request failed.
        """
        sent, self._sent = self._sent, []
        for flight in sent:
            try:
                flight.answer = await flight.request
            except LookupError:
                raise
            except Exception as error:
                if flight.strict:
                    raise
                flight.error = error
            flight.settled = True

    def ready(self, ticket: _Flight, now: float) -> bool:
        """Tell whether the answer is due by `now`."""
        # Game time sums float steps; the margin absorbs rounding far below one step.
        return now + 1e-9 >= ticket.due

    def outcome(self, ticket: _Flight) -> Callable[[], Any]:
        """Return the answer, or raise the request's error."""
        def result() -> Any:
            if ticket.error is not None:
                raise ticket.error
            return ticket.answer
        return result

    def cancel(self, ticket: _Flight) -> None:
        """Abandon a request an event overtook; one not yet run never runs."""
        if not ticket.settled:
            ticket.request.close()
            if ticket in self._sent:
                self._sent.remove(ticket)

    async def drain(self, tickets: list[_Flight]) -> None:
        """Nothing is in flight between ticks."""


def evening_over(world: Mapping[str, Any], time_limit: float) -> bool:
    """Tell whether a headless evening has ended.

    Args:
        world: Current world.
        time_limit: Game time that cuts the evening off.

    Returns:
        True once every guest has left and nobody else is expected, or the time limit is
        reached. Staff stay on, so they never keep an evening going. Worlds without a scenario
        expect nobody.
    """
    return (not guests(world) and not world.get("expected")) or world["time"] >= time_limit


def evening_mode(requested: str | None, keyed: bool) -> tuple[str, str | None]:
    """Choose who decides in a headless evening.

    Args:
        requested: `local`, `live` or `replay`; None means live when a Jev key is configured.
        keyed: Whether a Jev key is configured.

    Returns:
        The mode, and a note for the output and metrics when the default fell back to the
        local policy.

    Raises:
        ValueError: The mode is unknown, or live was requested without a key.
    """
    if requested is None:
        return ("live", None) if keyed else ("local", "No TYPESAFE_API_KEY in .env, so the labeled local policy decides")
    if requested not in ("local", "live", "replay"):
        raise ValueError(f"Unknown evening mode {requested!r}; choose local, live or replay")
    if requested == "live" and not keyed:
        raise ValueError("Live mode needs TYPESAFE_API_KEY in .env")
    return requested, None


async def run_evening(world: World, config: Mapping[str, Any], rng: Random, evaluators: Evaluators,
                      pace: Pace, writer: TurnWriter = write_scripted_turn, intender: Intender | None = None,
                      intention_rules: IntentionRules = INTENTION_RULES) -> Evening:
    """Play an evening to its end in lockstep.

    Each tick advances the world by one step, applies the answers that are due, then asks
    every visitor free to decide, by the live runtime's rules (`tavern.evening.decisions`). An answer
    is computed at once and applied one model latency later, unless the visitor left or got
    busy meanwhile. Conversation turns go the same way: each tick claims the scenes' next
    turns (`tavern.social.turns`), asks the writer at once, and hands each line back one model latency
    later; the world drops a line whose scene changed meanwhile. Intentions too (`tavern.mind.intentions`):
    asked at once, kept one model latency later, and dropped when a salient event overtakes them
    or the guest left. Nothing depends on wall-clock time. Failures the live runtime would show
    as "Decision failed" (a malformed request, a replay miss) stop the evening instead.

    Args:
        world: Unpaused world to play; mutated in place.
        config: AI config for `choose_action`; with a key the evaluators are asked.
        rng: Seeded generator of the decisions' random draws.
        evaluators: Model port.
        pace: Step, virtual model latency and time limit.
        writer: Turn writer port; the scripted writer by default.
        intender: Mind port writing guests' intentions; None (offline) writes none.
        intention_rules: When guests take stock.

    Returns:
        The evening's complete log, choices, stalled spells, guests and end time. A guest is
        stalled while they stand without an action and nobody talks to them, or wait on a
        blocked route.

    Raises:
        ValueError: The world is paused, or a decision request is malformed.
        LookupError: A replayed request was not recorded.
    """
    if world["paused"]:
        raise ValueError("A paused world never reaches the end of the evening")
    run = _Run(events=list(world["events"]))
    courier = LockstepCourier(pace.model_latency)
    mind = MindLoop(courier, lambda observation: choose_action(observation, config, rng, evaluators),
                    lambda view: writer(view, config), intender, intention_rules)
    _track(world, run)
    while not evening_over(world, pace.time_limit):
        step_world(world, pace.step)
        asked = mind.tick(world)
        await courier.settle()
        _record_choices(world, run, courier, asked)
        _collect(world, run)
        _track(world, run)
    _close(run, list(run.stalled_since), world["time"])
    return Evening(run.events, run.choices, run.spells, run.guests, world["time"], len(run.gazes))


def _record_choices(world: Mapping[str, Any], run: _Run, courier: LockstepCourier,
                    asked: list[tuple[str, Any]]) -> None:
    for actor_id, ticket in asked:
        decision = courier.outcome(ticket)()
        second = [(kind, decision[key]) for kind, key in (("seats", "seat"), ("family", "family")) if key in decision]
        stages = [("actions", decision), *second]
        run.choices.extend({"time": world["time"], "actor_id": actor_id, "kind": kind,
                            "source": stage["source"], "error": stage["error"], "scores": stage["scores"]}
                           for kind, stage in stages)


def _collect(world: Mapping[str, Any], run: _Run) -> None:
    # The world keeps only its latest events, so the new ones are those after the last event
    # collected. Identity, not equality, finds it: equal events can repeat.
    events = world["events"]
    if run.events:
        last = next((index for index in range(len(events) - 1, -1, -1) if events[index] is run.events[-1]), None)
        if last is None:
            raise ValueError("Events were trimmed before they were collected; take smaller steps")
        events = events[last + 1:]
    run.events.extend(events)


def _track(world: Mapping[str, Any], run: _Run) -> None:
    present = {actor["id"]: actor for actor in guests(world)}
    for actor_id, actor in present.items():
        if actor_id not in run.guests:
            run.guests.append(actor_id)
        if actor["gaze"]:
            run.gazes.add((actor_id, actor["gaze"]["stimulus_id"]))
        stalled = free_to_decide(world, actor) or actor["status"] == "waiting"
        if stalled and actor_id not in run.stalled_since:
            run.stalled_since[actor_id] = world["time"]
        elif not stalled and actor_id in run.stalled_since:
            _close(run, [actor_id], world["time"])
    _close(run, [actor_id for actor_id in run.stalled_since if actor_id not in present], world["time"])


def _close(run: _Run, actor_ids: list[str], now: float) -> None:
    for actor_id in actor_ids:
        run.spells.append({"actor_id": actor_id, "start": run.stalled_since.pop(actor_id), "end": now})
