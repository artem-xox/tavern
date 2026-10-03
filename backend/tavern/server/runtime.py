"""The live runtime of one session: its world, the requests in flight, the operator's commands and saves."""

from collections.abc import Callable, Coroutine
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any, Mapping, Protocol


from tavern.adapters.jev import evaluate_actions, evaluate_seats
from tavern.adapters.persistence import FileStore
from tavern.body.activities import ACTIVITIES, client_activities
from tavern.evening.decisions import log_control
from tavern.evening.mind_loop import MindLoop, TaskCourier
from tavern.evening.scenario import Scenario, open_evening
from tavern.hall.state import World
from tavern.hall.world import create_world, step_world
from tavern.mind import agents
from tavern.mind.feelings import minds
from tavern.mind.intentions import INTENTION_RULES, Intender, IntentionRules
from tavern.mind.scripted import write_scripted_turn
from tavern.server.controls import forced_action, refill_tap, set_paused, set_speed, toggle_block
from tavern.social.turns import TurnWriter


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
    return await agents.choose_action(observation, config, rng, agents.Evaluators(evaluate_actions, evaluate_seats))


# Decides a visitor's next action from their observation, the AI config and the runtime's generator.
Chooser = Callable[[Mapping[str, Any], Mapping[str, Any], Random], Coroutine[Any, Any, dict[str, Any]]]


class Store(Protocol):
    """Where one session's worlds are kept, by slot: `manual` or `auto`."""

    def load(self, slot: str) -> World | None:
        """Read the world in a slot; None when nothing was saved there. Raises ValueError if invalid."""

    def save(self, world: World, slot: str) -> None:
        """Replace the world in a slot."""


class TavernRuntime:
    """Own world state, one asynchronous decision request per visitor and one line per scene."""

    def __init__(self, map_data: Mapping[str, Any], save_path: Path,
                 ai_config: Mapping[str, Any], seed: int = 0, store: Store | None = None,
                 scenario: Scenario | None = None, writer: TurnWriter = write_scripted_turn,
                 writer_label: str = "scripted",
                 intender: Intender | None = None, intention_rules: IntentionRules = INTENTION_RULES,
                 choose: Chooser = choose_action) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.scenario = scenario
        self.world = self._open(seed)
        # Without a store the worlds go to JSON files: the manual save at `save_path`, the autosave beside it.
        self.store: Store = store or FileStore(save_path)
        self.ai_config = {"model": "jev-latest", "timeout": 8.0, "temperature": 0.25, **ai_config}
        self.rng = Random(seed)
        self.writer = writer
        # Which writer speaks the lines (`haiku` or `scripted`), for the client's label.
        self.writer_label = writer_label
        # The mind port (None offline: no intentions).
        self.intender, self.intention_rules = intender, intention_rules
        self.mind = MindLoop(TaskCourier(), lambda observation: choose(observation, self.ai_config, self.rng),
                             lambda view: self.writer(view, self.ai_config), intender, intention_rules)

    @property
    def pending(self) -> dict[str, tuple[Any, int]]:
        """The decisions in flight, per visitor: the task and the revision it was asked at."""
        return self.mind.pending

    def _open(self, seed: int) -> World:
        # A scenario says who comes tonight; without one, the room's own visitors are already in.
        if self.scenario is None:
            return create_world(self.map_data, seed)
        return open_evening(self.map_data, self.scenario, seed)

    def snapshot(self) -> dict[str, Any]:
        """Return a client envelope with credentials excluded.

        Returns:
            Independent world copy, public evaluator configuration, how the client
            names, shows, and targets each verb, and each visitor's inner state (`feelings.minds`).
            `ai.writer` names who writes conversation lines.
        """
        configured = bool(self.ai_config.get("typesafe_api_key"))
        return {"type": "snapshot", "state": deepcopy(self.world), "ai": {
            "mode": "jev" if configured else "local", "configured": configured,
            "model": self.ai_config["model"], "writer": self.writer_label, "intentions": self.intender is not None,
        }, "activities": client_activities(ACTIVITIES), "minds": minds(self.world)}

    def _event(self, message: str) -> None:
        log_control(self.world, message)

    def advance(self, dt: float) -> None:
        """Advance the world without waiting for AI requests.

        Args:
            dt: Real seconds since the previous simulation tick.
        """
        step_world(self.world, dt)
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
        return True

    def _reset(self, command: Mapping[str, Any]) -> None:
        # Restart opens a new, running evening: new arrival needs, visitors back at the door.
        restored = self._open(self.rng.randrange(1 << 30))
        self._invalidate_requests()
        self.world = restored

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
                    "save": self._save, "load": self._load, "reset": self._reset}
        if not isinstance(command, Mapping) or not isinstance(command.get("type"), str):
            raise ValueError("Expected a command with a type")
        handler = handlers.get(command["type"])
        if handler is None:
            raise ValueError("Unknown command")
        handler(command)
        self._event(f"Operator: {command['type']}")

    async def close(self) -> None:
        """Cancel and drain model requests when the server stops."""
        await self.mind.close()
