"""FastAPI transport and nonblocking orchestration of autonomous tavern agents."""

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
import json
import os
from pathlib import Path
from random import Random
import re
from typing import Any, AsyncIterator, Mapping, Protocol

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from tavern import agents
from tavern.activities import ACTIVITIES, client_activities
from tavern.cards import parse_cards
from tavern.cards_api import card_routes
from tavern.claude import ask_claude
from tavern.controls import forced_action, refill_tap, set_paused, set_speed, toggle_block
from tavern.database import DatabaseStore, initialize_database
from tavern.decisions import log_control
from tavern.feelings import minds
from tavern.haiku_turns import claude_writer
from tavern.intentions import INTENTION_RULES, Intender, IntentionRules, intention_writer
from tavern.jev import evaluate_actions, evaluate_seats
from tavern.mind_loop import MindLoop, TaskCourier
from tavern.persistence import FileStore
from tavern.questions import Ask, Question
from tavern.scenario import Scenario, open_evening, parse_scenario
from tavern.scripted import write_scripted_turn
from tavern.state import World
from tavern.turns import TurnWriter
from tavern.world import create_world, step_world

# Session IDs also name save directories, so only path-safe characters are allowed.
SESSION_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


async def choose_action(observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
    """Decide a visitor's next action with the Jev adapter wired in as the model.

    Args:
        observation: Private actor observation.
        config: Explicit API key, model, timeout and selection temperature.
        rng: The runtime's seeded random generator.

    Returns:
        The decision of `tavern.agents.choose_action`.

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


class TavernSessions:
    """Own one runtime per device session; only sessions with an open page advance."""

    def __init__(self, map_data: Mapping[str, Any], save_dir: Path, ai_config: Mapping[str, Any],
                 seed: int = 0, database_url: str | None = None, scenario: Scenario | None = None,
                 writer: TurnWriter = write_scripted_turn, writer_label: str = "scripted",
                 intender: Intender | None = None, store_for: Callable[[str], Store] | None = None) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.writer, self.writer_label = writer, writer_label
        self.save_dir = save_dir
        self.intender = intender
        self.ai_config = dict(ai_config)
        # Which database backs the sessions, if any; `store_for` makes each session's store (default:
        # JSON files under `save_dir`).
        self.database_url = database_url
        self.store_for = store_for
        self.scenario = scenario
        self.rng = Random(seed)
        self.runtimes: dict[str, TavernRuntime] = {}
        self.pages: dict[str, int] = {}

    def open(self, session_id: Any) -> TavernRuntime:
        """Attach a page to its session, restoring or creating the session's world.

        Args:
            session_id: Device session ID of 8-64 letters, digits, '-' or '_'.
        Returns:
            The session's runtime, shared by every page of that session.
        Raises:
            ValueError: The ID is malformed.
        """
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ValueError("Invalid session")
        if session_id not in self.runtimes:
            self.runtimes[session_id] = self._start(session_id)
        self.pages[session_id] = self.pages.get(session_id, 0) + 1
        return self.runtimes[session_id]

    def _start(self, session_id: str) -> TavernRuntime:
        # A scenario's own seed replays the same evening in every session; otherwise each draws one.
        seed = self.rng.randrange(1 << 30)
        if self.scenario is not None and self.scenario.seed is not None:
            seed = self.scenario.seed
        runtime = TavernRuntime(self.map_data, self.save_dir / session_id / "save.json", self.ai_config, seed,
                                self.store_for(session_id) if self.store_for else None, self.scenario,
                                self.writer, self.writer_label, intender=self.intender)
        if not runtime.restore():
            # A new evening waits at the door until someone presses Start.
            runtime.world["paused"] = True
        return runtime

    async def release(self, session_id: str) -> None:
        """Detach a page; the last page to leave autosaves and unloads the session.

        Args:
            session_id: Session previously returned by open.
        Raises:
            ValueError: The world cannot be written.
            psycopg.Error: The database cannot be written.
        """
        self.pages[session_id] -= 1
        if self.pages[session_id] > 0:
            return
        runtime = self.runtimes[session_id]
        # Save before forgetting: if storage fails, the session stays in memory, unticked.
        runtime.autosave()
        del self.runtimes[session_id], self.pages[session_id]
        await runtime.close()

    def advance(self, dt: float) -> None:
        """Advance sessions that someone is watching; closed sessions keep their clock.

        Args:
            dt: Real seconds since the previous simulation tick.
        """
        for session_id, runtime in self.runtimes.items():
            if self.pages[session_id] > 0:
                runtime.advance(dt)

    async def close(self) -> None:
        """Autosave and unload every session when the server stops."""
        runtimes = list(self.runtimes.values())
        for runtime in runtimes:
            runtime.autosave()
        self.runtimes.clear()
        self.pages.clear()
        await asyncio.gather(*(runtime.close() for runtime in runtimes))


async def _run_world(sessions: TavernSessions, tick_seconds: float) -> None:
    while True:
        sessions.advance(tick_seconds)
        await asyncio.sleep(tick_seconds)


async def _send_snapshots(socket: WebSocket, runtime: TavernRuntime, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        await socket.send_json(runtime.snapshot())


async def _serve_socket(socket: WebSocket, sessions: TavernSessions) -> None:
    session_id = socket.query_params.get("session")
    try:
        runtime = sessions.open(session_id)
    except ValueError as error:
        # Policy violation: retrying with the same session cannot succeed. Accepting first
        # lets the browser see the code and reason instead of a bare handshake failure.
        await socket.accept()
        await socket.close(code=1008, reason=str(error))
        return
    sender = None
    try:
        await socket.accept()
        await socket.send_json(runtime.snapshot())
        sender = asyncio.create_task(_send_snapshots(socket, runtime, 0.1))
        while True:
            try:
                runtime.command(await socket.receive_json())
                await socket.send_json(runtime.snapshot())
            except ValueError as error:
                await socket.send_json({"type": "error", "message": str(error)})
    except WebSocketDisconnect:
        pass
    finally:
        if sender is not None:
            sender.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await sender
        await sessions.release(str(session_id))  # `open` accepted it, so it is a valid ID.


def create_app(map_path: Path, save_dir: Path, ai_config: Mapping[str, Any],
               run_loop: bool = True, database_url: str | None = None, seed: int = 0,
               scenario_path: Path | None = None, characters_dir: Path | None = None,
               ask: Ask | None = None, writer: TurnWriter = write_scripted_turn,
               writer_label: str = "scripted", intender: Intender | None = None,
               store_for: Callable[[str], Store] | None = None) -> FastAPI:
    """Construct the local server with explicit paths and AI configuration.

    Args:
        map_path: JSON layout to initialize the room.
        save_dir: Directory of per-session snapshot files, used without a database.
        ai_config: Evaluator settings, including an optional server-only key.
        run_loop: Whether to start automatic ticking; false for focused API tests.
        database_url: Optional PostgreSQL URL for persistent session snapshots; unless `store_for`
            is given, each session then keeps its worlds there.
        seed: Seed of the sessions' arrivals and decision policies.
        scenario_path: Optional JSON scenario; sessions then open its evenings instead of
            starting with the room's own visitors.
        characters_dir: Optional folder of character cards (one JSON file each) the scenario
            casts its guests from.
        ask: Optional Claude port bound to the server's key, for the card compiler; without
            it the compiler runs its labeled offline mode.
        writer: Turn writer of every session's conversation lines; scripted by default.
        writer_label: Name of that writer shown to the client (`haiku` or `scripted`).
        intender: Optional mind port writing guests' intentions; without it guests have none
            and the snapshot says so.
        store_for: Optional maker of a session's store from its ID, in place of the database or
            the JSON files.
    Returns:
        Application serving JSON state and a bidirectional WebSocket per device session.
        Sessions advance only while a page is open and always reopen paused.
    Raises:
        ValueError: The scenario file or a character card is malformed.
    """
    map_data = json.loads(map_path.read_text())
    cards = (parse_cards([json.loads(path.read_text()) for path in sorted(characters_dir.glob("*.json"))])
             if characters_dir else None)
    scenario = parse_scenario(json.loads(scenario_path.read_text()), cards) if scenario_path else None
    if database_url and store_for is None:
        initialize_database(database_url)
        store_for = lambda session_id: DatabaseStore(database_url, session_id)
    sessions = TavernSessions(map_data, save_dir, ai_config, seed, database_url, scenario, writer, writer_label,
                              intender, store_for)
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ticker = asyncio.create_task(_run_world(sessions, 0.1)) if run_loop else None
        yield
        if ticker is not None:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
        await sessions.close()
    app = FastAPI(title="The Last Inn", lifespan=lifespan)
    app.state.sessions = sessions
    _register_routes(app, sessions)
    app.include_router(card_routes(ask))
    return app


def _register_routes(app: FastAPI, sessions: TavernSessions) -> None:
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}
    @app.get("/api/state")
    async def state(session: str) -> dict[str, Any]:
        runtime = sessions.runtimes.get(session)
        if runtime is None:
            raise HTTPException(status_code=404, detail="Session is not open")
        return runtime.snapshot()
    @app.websocket("/ws")
    async def websocket(socket: WebSocket) -> None:
        await _serve_socket(socket, sessions)


def create_default_app() -> FastAPI:
    """Read launch configuration and create the local demo application.

    Returns:
        Server initialized from the repository's map, first-evening scenario, and
        environment variables; `ANTHROPIC_API_KEY` enables the card compiler and Haiku lines.
    """
    working_root = Path.cwd()
    root = (working_root if (working_root / "data" / "tavern.json").is_file()
            else Path(__file__).resolve().parents[2])
    config = {"typesafe_api_key": os.environ.get("TYPESAFE_API_KEY"),
              "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(os.environ.get("AI_TIMEOUT", "8")),
              "temperature": float(os.environ.get("AI_TEMPERATURE", "0.25"))}
    ask = _claude_port(os.environ.get("ANTHROPIC_API_KEY"))
    database_url = (os.environ.get("DATABASE_URL")
                     if os.environ.get("TAVERN_DATABASE_ENABLED") == "true" else None)
    ask = _claude_port(os.environ.get("ANTHROPIC_API_KEY"))
    # With a Claude key Haiku writes conversation lines; without one the labeled scripted writer does.
    lines: dict[str, Any] = {} if ask is None else {"writer": claude_writer(ask), "writer_label": "haiku"}
    return create_app(root / "data" / "tavern.json", root / "saves", config,
                      database_url=database_url, seed=Random().randrange(1 << 30),
                      scenario_path=root / "data" / "scenarios" / "first_evening.json",
                      characters_dir=root / "data" / "characters",
                      ask=ask, intender=None if ask is None else intention_writer(
                          (root / "data" / "minds" / "intention_prefix.md").read_text(), ask), **lines)


def _claude_port(key: str | None) -> Ask | None:
    # The key stays on the server; without one the card compiler runs offline.
    if not key:
        return None
    config = {"anthropic_api_key": key, "model": "claude-haiku-4-5", "timeout": 30.0, "retries": 1}

    async def ask(question: Question) -> dict[str, Any]:
        return (await ask_claude(question, config))[0]
    return ask
