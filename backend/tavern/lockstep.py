"""Headless evenings in lockstep: fixed game-time steps and a fixed virtual model latency."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from random import Random
from typing import Any, TypedDict

from tavern.agents import Evaluators, choose_action
from tavern.decisions import apply_decision, decision_requests, free_to_decide
from tavern.world import step_world


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
    """One stage of a decision: `kind` is `actions` or `seats`, as in recorded calls."""

    time: float
    actor_id: str
    kind: str
    source: str
    error: str | None


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
    sight, and `end_time` the game time it ended.
    """

    events: list[dict[str, Any]]
    choices: list[Choice]
    spells: list[Spell]
    guests: list[str]
    end_time: float


@dataclass
class _Run:
    pending: dict[str, tuple[float, Mapping[str, Any]]] = field(default_factory=dict)
    next_decision: dict[str, float] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    spells: list[Spell] = field(default_factory=list)
    stalled_since: dict[str, float] = field(default_factory=dict)
    guests: list[str] = field(default_factory=list)


def evening_over(world: Mapping[str, Any], time_limit: float) -> bool:
    """Tell whether a headless evening has ended.

    Args:
        world: Current world.
        time_limit: Game time that cuts the evening off.

    Returns:
        True once every visitor has left and nobody else is expected, or the time limit is
        reached. Worlds without a scenario expect nobody.
    """
    return (not world["actors"] and not world.get("expected")) or world["time"] >= time_limit


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


async def run_evening(world: dict[str, Any], config: Mapping[str, Any], rng: Random, evaluators: Evaluators,
                      pace: Pace) -> Evening:
    """Play an evening to its end in lockstep.

    Each tick advances the world by one step, applies the answers that are due, then asks
    every visitor free to decide, by the live runtime's rules (`tavern.decisions`). An answer
    is computed at once and applied one model latency later, unless the visitor left or got
    busy meanwhile. Nothing depends on wall-clock time. Failures the live runtime would show
    as "Decision failed" (a malformed request, a replay miss) stop the evening instead.

    Args:
        world: Unpaused world to play; mutated in place.
        config: AI config for `choose_action`; with a key the evaluators are asked.
        rng: Seeded generator of the decisions' random draws.
        evaluators: Model port.
        pace: Step, virtual model latency and time limit.

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
    _track(world, run)
    while not evening_over(world, pace.time_limit):
        step_world(world, pace.step)
        _apply_due(world, run)
        await _ask(world, run, config, rng, evaluators, pace.model_latency)
        _collect(world, run)
        _track(world, run)
    _close(run, list(run.stalled_since), world["time"])
    return Evening(run.events, run.choices, run.spells, run.guests, world["time"])


def _apply_due(world: dict[str, Any], run: _Run) -> None:
    for actor_id, (due, decision) in list(run.pending.items()):
        # Game time sums float steps; the margin absorbs rounding far below one step.
        if world["time"] + 1e-9 < due:
            continue
        del run.pending[actor_id]
        actor = next((item for item in world["actors"] if item["id"] == actor_id), None)
        # As in the live runtime, an answer for a visitor who left or got busy meanwhile is dropped.
        if actor is not None and free_to_decide(world, actor):
            run.next_decision[actor_id] = apply_decision(world, actor, lambda: decision)


async def _ask(world: dict[str, Any], run: _Run, config: Mapping[str, Any], rng: Random,
               evaluators: Evaluators, latency: float) -> None:
    for actor_id, observation in decision_requests(world, run.pending, run.next_decision):
        decision = await choose_action(observation, config, rng, evaluators)
        run.pending[actor_id] = (world["time"] + latency, decision)
        stages = [("actions", decision), *([("seats", decision["seat"])] if "seat" in decision else [])]
        run.choices.extend({"time": world["time"], "actor_id": actor_id, "kind": kind,
                            "source": stage["source"], "error": stage["error"]} for kind, stage in stages)


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
    present = {actor["id"]: actor for actor in world["actors"]}
    for actor_id, actor in present.items():
        if actor_id not in run.guests:
            run.guests.append(actor_id)
        stalled = free_to_decide(world, actor) or actor["status"] == "waiting"
        if stalled and actor_id not in run.stalled_since:
            run.stalled_since[actor_id] = world["time"]
        elif not stalled and actor_id in run.stalled_since:
            _close(run, [actor_id], world["time"])
    _close(run, [actor_id for actor_id in run.stalled_since if actor_id not in present], world["time"])


def _close(run: _Run, actor_ids: list[str], now: float) -> None:
    for actor_id in actor_ids:
        run.spells.append({"actor_id": actor_id, "start": run.stalled_since.pop(actor_id), "end": now})
