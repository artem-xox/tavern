"""The live runtime of one session: its world, the requests in flight, the operator's commands and saves."""

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any, Mapping, Protocol, cast


from tavern.adapters.claude import ClaudeError
from tavern.adapters.jev import evaluate_actions, evaluate_aims, evaluate_answers, evaluate_seats
from tavern.adapters.persistence import FileStore
from tavern.body.activities import ACTIVITIES, client_activities
from tavern.body.items import client_items
from tavern.evening.decisions import log_control
from tavern.evening.mind_loop import MindLoop, TaskCourier
from tavern.evening.retelling import Retelling, retell
from tavern.evening.scenario import Scenario, open_evening
from tavern.evening.story_score import WEIGHTS, Moment, story_moments, story_score
from tavern.hall.staff import guests
from tavern.hall.state import World
from tavern.hall.world import create_world, step_world
from tavern.mind import agents
from tavern.mind.feelings import minds
from tavern.mind.questions import Ask
from tavern.mind.selection import read_answers
from tavern.mind.intentions import INTENTION_RULES, Intender, IntentionRules
from tavern.mind.model_health import HealthBoard
from tavern.mind.scripted import write_scripted_turn
from tavern.server.controls import forced_action, refill_tap, set_paused, set_speed, toggle_block
from tavern.social.stage_lines import StageWriter, write_scripted_stage
from tavern.social.turns import TurnWriter


def _public_world(world: World) -> dict[str, Any]:
    """Copy a world for the browser without model-only character secrets.

    Args:
        world: Authoritative state retained for saves and model prompts.
    Returns:
        A copy whose current, expected, and departed cards omit `secret`.
    """
    public = cast(dict[str, Any], deepcopy(world))
    for group in (public["actors"], public["expected"], public["departed"]):
        for actor in group:
            card = actor.get("card")
            if card is not None:
                cast(dict[str, Any], card).pop("secret", None)
    return public


async def choose_action(observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
    """Decide a visitor's next action with the Jev adapter wired in as the model.

    Args:
        observation: Private actor observation.
        config: Explicit API key, model, timeout and selection temperature.
        rng: The runtime's seeded random generator.

    Returns:
        The decision of `tavern.mind.agents.choose_action`.

    Raises:
        ValueError: Observation or configuration is malformed.
    """
    return await agents.choose_action(observation, config, rng, agents.Evaluators(evaluate_actions, evaluate_seats, aims=evaluate_aims))


async def choose_invitation_answer(observation: Mapping[str, Any], invitation: Mapping[str, Any],
                                   options: Sequence[str], config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
    """Decide an invitee's answer with the Jev adapter wired in as the model.

    Args:
        observation: The invitee's observation.
        invitation: The pending invitation.
        options: The answers open to them.
        config: Explicit API key, model, timeout and selection temperature.
        rng: The runtime's seeded random generator.

    Returns:
        The result of `tavern.mind.agents.choose_answer`.
    """
    return await agents.choose_answer(observation, invitation, options, config, rng, agents.Evaluators(
        evaluate_actions, evaluate_seats, aims=evaluate_aims, answers=evaluate_answers))


# Decides a visitor's next action from their observation, the AI config and the runtime's generator.
Chooser = Callable[[Mapping[str, Any], Mapping[str, Any], Random], Coroutine[Any, Any, dict[str, Any]]]
# Decides how an invitee answers: their observation, the invitation, the answers open, the AI config, the generator.
Answerer = Callable[[Mapping[str, Any], Mapping[str, Any], Sequence[str], Mapping[str, Any], Random],
                    Coroutine[Any, Any, dict[str, Any]]]


# Builds the evening of a cast for the guests picked on the start screen: cast, guest IDs, minutes.
Lineup = Callable[[Any, Any, Any], Scenario]


class Store(Protocol):
    """Where one session's worlds are kept, by slot: `manual` or `auto`."""

    def load(self, slot: str) -> World | None:
        """Read the world in a slot; None when nothing was saved there. Raises ValueError if invalid."""

    def save(self, world: World, slot: str) -> None:
        """Replace the world in a slot."""


def _anyone_to_come(world: Mapping[str, Any]) -> bool:
    return bool(guests(world) or world["expected"])


class TavernRuntime:
    """Own world state, one asynchronous decision request per visitor and one line per scene."""

    def __init__(self, map_data: Mapping[str, Any], save_path: Path,
                 ai_config: Mapping[str, Any], seed: int = 0, store: Store | None = None,
                 scenario: Scenario | None = None, writer: TurnWriter = write_scripted_turn,
                 writer_label: str = "scripted",
                 intender: Intender | None = None, intention_rules: IntentionRules = INTENTION_RULES,
                 choose: Chooser = choose_action, health: HealthBoard | None = None,
                 answer: Answerer = choose_invitation_answer, storyteller: Ask | None = None,
                 lineup: Lineup | None = None, stage_writer: StageWriter = write_scripted_stage) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.scenario = scenario
        # Makes the evening of a `start` command; None where the start screen is not offered.
        self.lineup = lineup
        self.world = self._open(seed)
        # Retells the evening when it is over; None offline: the score still counts, nothing is retold.
        self.storyteller = storyteller
        self._telling: asyncio.Task[None] | None = None
        self._follow_story()
        # Without a store the worlds go to JSON files: the manual save at `save_path`, the autosave beside it.
        self.store: Store = store or FileStore(save_path)
        self.ai_config = {"model": "jev-latest", "timeout": 8.0, "temperature": 0.25, **ai_config}
        self.rng = Random(seed)
        self.writer = writer
        # Which writer speaks the lines (`haiku` or `scripted`), for the client's label.
        self.writer_label = writer_label
        # The mind port (None offline: no intentions).
        self.intender, self.intention_rules = intender, intention_rules
        # How Jev and Claude are doing, for the client's badges; None where nobody watches them.
        self.health = health
        # With the answers setting on, an invitee's answer is their own choice, asked before their line.
        answers = ((lambda observation, invitation, options: answer(observation, invitation, options, self.ai_config,
                                                                    self.rng)) if read_answers(self.ai_config) else None)
        self.mind = MindLoop(TaskCourier(), lambda observation: choose(observation, self.ai_config, self.rng),
                             lambda view: self.writer(view, self.ai_config), intender, intention_rules, answers,
                             lambda view: stage_writer(view, self.ai_config))

    @property
    def pending(self) -> dict[str, tuple[Any, int]]:
        """The decisions in flight, per visitor: the task and the revision it was asked at."""
        return self.mind.pending

    def _follow_story(self) -> None:
        # A new world starts a new story: what its log already holds is the start, and nothing is retold yet.
        if self._telling is not None:
            self._telling.cancel()
        self.chronicle: list[dict[str, Any]] = list(self.world["events"])
        self.moments: list[Moment] = story_moments(self.chronicle)
        self.retelling: Retelling | None = None
        self._telling = None

    def _note_story(self) -> None:
        # The world keeps only its latest 200 events, so the story is gathered tick by tick: what follows the
        # last event seen is new (an event is told apart by identity, as equal events do repeat).
        events = self.world["events"]
        seen = next((index for index in range(len(events) - 1, -1, -1) if events[index] is self.chronicle[-1]), -1) \
            if self.chronicle else -1
        fresh = events[seen + 1:]
        self.chronicle.extend(fresh)
        self.moments.extend(story_moments(fresh))

    async def _tell(self) -> None:
        score = story_score(self.moments, WEIGHTS)
        try:
            assert self.storyteller is not None
            self.retelling = await retell(self.chronicle, score, self.storyteller)
        except (ClaudeError, ValueError) as error:
            self._event(f"The evening could not be retold: {error}")

    async def await_retelling(self) -> None:
        """Wait until the storyteller has finished retelling the evening; at once if it was never asked."""
        if self._telling is not None:
            await self._telling

    def _open(self, seed: int) -> World:
        # A scenario says who comes tonight; without one, the room's own visitors are already in.
        if self.scenario is None:
            return create_world(self.map_data, seed)
        return open_evening(self.map_data, self.scenario, seed)

    def snapshot(self) -> dict[str, Any]:
        """Return a client envelope with credentials excluded.

        Returns:
            Independent world copy, public evaluator configuration, how the client
            names, shows, and targets each verb, how it words each kind of item, and each visitor's inner state (`feelings.minds`).
            `ai.writer` names who writes conversation lines; `ai.health` says how Jev and Claude are
            doing (`model_health`), when a board is watching them.
        """
        configured = bool(self.ai_config.get("typesafe_api_key"))
        health = {} if self.health is None else {"health": self.health.snapshot()}
        return {"type": "snapshot", "state": _public_world(self.world), "ai": {
            "mode": "jev" if configured else "local", "configured": configured,
            "model": self.ai_config["model"], "writer": self.writer_label, "intentions": self.intender is not None,
            **health,
        }, "activities": client_activities(ACTIVITIES), "items": client_items(), "minds": minds(self.world),
                "story": story_score(self.moments, WEIGHTS), "retelling": self.retelling,
                "telling": self._telling is not None and not self._telling.done()}

    def _event(self, message: str) -> None:
        log_control(self.world, message)

    def advance(self, dt: float) -> None:
        """Advance the world without waiting for AI requests.

        Args:
            dt: Real seconds since the previous simulation tick.
        """
        step_world(self.world, dt)
        self._note_story()
        if not self.world["paused"] and self.world["closes_at"] is not None and not _anyone_to_come(self.world):
            # Staff stay at their bars all night, so only guests, present or expected, keep an evening going.
            self.world["paused"] = True
            self._event("The last guest has left: the evening is over")
            self._note_story()
            if self.storyteller is not None and self._telling is None:
                self._telling = asyncio.get_running_loop().create_task(self._tell())
        if not self.world["paused"]:
            self.mind.tick(self.world)

    def _block(self, command: Mapping[str, Any]) -> None:
        toggle_block(self.world, self.map_data["blocked"], command)

    def _force_action(self, command: Mapping[str, Any]) -> None:
        self.world, actor_id = forced_action(self.world, command)
        self.mind.overrule(actor_id)

    def _invalidate_requests(self) -> None:
        self.mind.invalidate()

    def _save(self, command: Mapping[str, Any]) -> None:
        self.store.save(self.world, "manual")

    def _load(self, command: Mapping[str, Any]) -> None:
        restored = self.store.load("manual")
        if restored is None:
            raise ValueError("No saved world exists")
        self._invalidate_requests()
        self.world = restored
        self._follow_story()

    def autosave(self) -> None:
        """Store the current world in the session's autosave slot.

        Raises:
            ValueError: The world cannot be serialized or written to a file.
            psycopg.Error: The database store cannot write it.
        """
        self.store.save(self.world, "auto")

    def restore(self) -> bool:
        """Replace the world with the session's autosave, paused.

        Returns:
            Whether an autosave was restored. Without one the world is unchanged; a rejected
            one (an older format or a damaged file) leaves it unchanged too and is reported in
            the event log.
        Raises:
            psycopg.Error: The database cannot be read.
        """
        try:
            restored = self.store.load("auto")
        except ValueError as error:
            # An unreadable autosave must not lock the device out of the inn: a new evening opens.
            self._event(f"The saved evening could not be restored ({error}); a new evening begins")
            return False
        if restored is None:
            return False
        self._invalidate_requests()
        # Nobody watched the inn while it was stored, so it waits for the operator to resume.
        restored["paused"] = True
        self.world = restored
        self._follow_story()
        return True

    def _reset(self, command: Mapping[str, Any]) -> None:
        # Restart opens a new, running evening: new arrival needs, visitors back at the door.
        restored = self._open(self.rng.randrange(1 << 30))
        self._invalidate_requests()
        self.world = restored
        self._follow_story()

    def _start(self, command: Mapping[str, Any]) -> None:
        # The picked lineup becomes the scenario, so a later restart replays it.
        if self.lineup is None:
            raise ValueError("No lineups are offered")
        self.scenario = self.lineup(command.get("cast"), command.get("guests"), command.get("minutes"))
        self._reset(command)

    def command(self, command: Mapping[str, Any]) -> None:
        """Validate and apply an operator command atomically.

        Args:
            command: JSON command from the browser.
        Raises:
            ValueError: A command or its arguments are invalid.
        """
        handlers = {"pause": lambda item: set_paused(self.world, item),
                    "speed": lambda item: set_speed(self.world, item),
                    "refill": lambda item: refill_tap(self.world, item),
                    "block": self._block, "force_action": self._force_action,
                    "save": self._save, "load": self._load, "reset": self._reset, "start": self._start}
        if not isinstance(command, Mapping) or not isinstance(command.get("type"), str):
            raise ValueError("Expected a command with a type")
        handler = handlers.get(command["type"])
        if handler is None:
            raise ValueError("Unknown command")
        handler(command)
        self._event(f"Operator: {command['type']}")

    async def close(self) -> None:
        """Cancel and drain model requests when the server stops."""
        if self._telling is not None:
            self._telling.cancel()
        await self.mind.close()
