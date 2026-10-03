"""FastAPI transport and nonblocking orchestration of autonomous tavern agents."""

import asyncio
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
import json
import math
import os
from pathlib import Path
from random import Random
import re
from typing import Any, AsyncIterator, Mapping

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from tavern import agents
from tavern.activities import ACTIVITIES, client_activities
from tavern.cards import parse_cards
from tavern.cards_api import card_routes
from tavern.claude import ask_claude
from tavern.database import initialize_database, load_database_world, save_database_world
from tavern.decisions import apply_decision, decision_requests, free_to_decide, log_control, stale_requests
from tavern.feelings import minds
from tavern.jev import evaluate_actions, evaluate_seats
from tavern.persistence import load_world, save_world
from tavern.questions import Ask, Question
from tavern.room import object_cells
from tavern.scenario import Scenario, open_evening, parse_scenario
from tavern.scripted import write_scripted_turn
from tavern.turns import TurnWriter, claim_turns, deliver_turn
from tavern.world import create_world, start_action, step_world

# Session IDs also name save directories, so only path-safe characters are allowed.
SESSION_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


def _number(value: Any, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Value must be between {minimum} and {maximum}")
    return float(value)


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Expected an integer")
    _number(value, minimum, maximum)
    return value


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


class TavernRuntime:
    """Own world state, one asynchronous decision request per visitor and one line per scene."""

    def __init__(self, map_data: Mapping[str, Any], save_path: Path,
                 ai_config: Mapping[str, Any], seed: int = 0,
                 database_url: str | None = None, session_id: str = "local",
                 scenario: Scenario | None = None, writer: TurnWriter = write_scripted_turn) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.scenario = scenario
        self.world = self._open(seed)
        self.save_path = save_path
        self.database_url = database_url
        self.session_id = session_id
        self.ai_config = {"model": "jev-latest", "timeout": 8.0, "temperature": 0.25, **ai_config}
        self.rng = Random(seed)
        self.pending: dict[str, tuple[asyncio.Task[Any], int]] = {}
        self.revisions: dict[str, int] = {}
        self.next_decision: dict[str, float] = {}
        # Game time each pending request was made, to drop those an interrupt overtakes.
        self.asked_at: dict[str, float] = {}
        self.writer = writer
        # Lines being written, per claimed turn (scene ID, turn index).
        self.writing: dict[tuple[str, int], asyncio.Task[Any]] = {}

    def _open(self, seed: int) -> dict[str, Any]:
        # A scenario says who comes tonight; without one, the room's own visitors are already in.
        if self.scenario is None:
            return create_world(self.map_data, seed)
        return open_evening(self.map_data, self.scenario, seed)

    def snapshot(self) -> dict[str, Any]:
        """Return a client envelope with credentials excluded.

        Returns:
            Independent world copy, public evaluator configuration, how the client
            names, shows, and targets each verb, and each visitor's inner state (`feelings.minds`).
        """
        configured = bool(self.ai_config.get("typesafe_api_key"))
        return {"type": "snapshot", "state": deepcopy(self.world), "ai": {
            "mode": "jev" if configured else "local", "configured": configured,
            "model": self.ai_config["model"],
        }, "activities": client_activities(ACTIVITIES), "minds": minds(self.world)}

    def _event(self, message: str) -> None:
        log_control(self.world, message)

    def _apply_decision(self, actor: dict[str, Any], task: asyncio.Task[Any], revision: int) -> None:
        if revision != self.revisions.get(actor["id"], 0) or not free_to_decide(self.world, actor):
            with suppress(asyncio.CancelledError, Exception):
                task.result()
            return
        self.next_decision[actor["id"]] = apply_decision(self.world, actor, task.result)

    def _collect_decisions(self) -> None:
        for actor_id, pending in list(self.pending.items()):
            if not pending[0].done():
                continue
            del self.pending[actor_id]
            self.asked_at.pop(actor_id, None)
            actor = next((item for item in self.world["actors"] if item["id"] == actor_id), None)
            if actor is not None:
                self._apply_decision(actor, *pending)
            else:
                # The visitor has gone home; their late thought has nobody to act on it.
                with suppress(asyncio.CancelledError, Exception):
                    pending[0].result()

    def _request_decisions(self) -> None:
        for actor_id, observation in decision_requests(self.world, self.pending, self.next_decision):
            task = asyncio.create_task(choose_action(observation, self.ai_config, self.rng))
            self.pending[actor_id] = (task, self.revisions.get(actor_id, 0))
            self.asked_at[actor_id] = self.world["time"]

    def _collect_lines(self) -> None:
        for key, task in list(self.writing.items()):
            if task.done():
                del self.writing[key]
                deliver_turn(self.world, *key, task.result)

    def _request_lines(self) -> None:
        for scene_id, turn, view in claim_turns(self.world):
            self.writing[(scene_id, turn)] = asyncio.create_task(self.writer(view, self.ai_config))

    def _drop_stale_requests(self) -> None:
        # As in the lockstep runner, an interrupted visitor's pending thought is dropped and they ask anew.
        for actor_id in stale_requests(self.world, self.asked_at):
            self.pending.pop(actor_id)[0].cancel()
            del self.asked_at[actor_id]

    def advance(self, dt: float) -> None:
        """Advance the world without waiting for AI requests.

        Args:
            dt: Real seconds since the previous simulation tick.
        """
        step_world(self.world, dt)
        if not self.world["paused"]:
            self._drop_stale_requests()
            self._collect_decisions()
            self._request_decisions()
            self._collect_lines()
            self._request_lines()

    def _pause(self, command: Mapping[str, Any]) -> None:
        if not isinstance(command.get("paused"), bool):
            raise ValueError("paused must be a boolean")
        self.world["paused"] = command["paused"]

    def _speed(self, command: Mapping[str, Any]) -> None:
        self.world["speed"] = _number(command.get("value"), 0.25, 8)

    def _refill(self, command: Mapping[str, Any]) -> None:
        amount = _integer(command.get("amount"), 1, 1000)
        target = next((item for item in self.world["map"]["objects"]
                       if item["id"] == command.get("object_id") and item["kind"] == "tap"), None)
        if target is None:
            raise ValueError("Unknown beer tap")
        target["stock"] += amount

    def _block(self, command: Mapping[str, Any]) -> None:
        x = _integer(command.get("x"), 0, self.world["map"]["width"] - 1)
        y = _integer(command.get("y"), 0, self.world["map"]["height"] - 1)
        if not isinstance(command.get("blocked"), bool):
            raise ValueError("blocked must be a boolean")
        self._validate_block([x, y], command["blocked"])
        cells = self.world["map"]["blocked"]
        if command["blocked"] and [x, y] not in cells:
            cells.append([x, y])
        elif not command["blocked"] and [x, y] in cells:
            cells.remove([x, y])

    def _validate_block(self, cell: list[int], blocked: bool) -> None:
        if cell in self.map_data["blocked"] and not blocked:
            raise ValueError("Permanent walls cannot be removed")
        if any([actor["x"], actor["y"]] == cell for actor in self.world["actors"]):
            raise ValueError("Cannot change the cell under a visitor")
        if any(tuple(cell) in object_cells(item) for item in self.world["map"]["objects"]):
            raise ValueError("Furniture cells cannot be changed")

    def _force_action(self, command: Mapping[str, Any]) -> None:
        actor_id = command.get("actor_id")
        if not isinstance(actor_id, str) or not isinstance(command.get("action"), dict):
            raise ValueError("Expected actor_id and action")
        if not any(actor["id"] == actor_id for actor in self.world["actors"]):
            raise ValueError("Unknown visitor")
        action = command["action"]
        if not isinstance(action.get("verb"), str) or not isinstance(action.get("id"), str):
            raise ValueError("Action id and verb must be strings")
        if action.get("target_id") is not None and not isinstance(action["target_id"], str):
            raise ValueError("Action target must be an object ID or null")
        trial = deepcopy(self.world)
        result = start_action(trial, actor_id, action)
        if not result["accepted"]:
            raise ValueError(result["reason"])
        self.world = trial
        self.revisions[actor_id] = self.revisions.get(actor_id, 0) + 1

    def _invalidate_requests(self) -> None:
        for task in [*(task for task, _revision in self.pending.values()), *self.writing.values()]:
            task.cancel()
        self.pending.clear()
        self.writing.clear()
        self.asked_at.clear()
        self.revisions.clear()
        self.next_decision.clear()

    def _autosave_path(self) -> Path:
        # Without a database the autosave lives next to the manual save file.
        return self.save_path.with_name("autosave.json")

    def _write(self, slot: str, path: Path) -> None:
        if self.database_url:
            save_database_world(self.world, self.database_url, self.session_id, slot)
        else:
            save_world(self.world, path)

    def _save(self, command: Mapping[str, Any]) -> None:
        self._write("manual", self.save_path)

    def _load(self, command: Mapping[str, Any]) -> None:
        restored = (load_database_world(self.database_url, self.session_id, "manual") if self.database_url
                    else load_world(self.save_path))
        if restored is None:
            raise ValueError("No saved world exists")
        self._invalidate_requests()
        self.world = restored

    def autosave(self) -> None:
        """Store the current world in the session's autosave slot.

        Raises:
            ValueError: The world cannot be serialized or written to a file.
            psycopg.Error: The database cannot be written.
        """
        self._write("auto", self._autosave_path())

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
            restored = self._read_autosave()
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

    def _read_autosave(self) -> dict[str, Any] | None:
        if self.database_url:
            return load_database_world(self.database_url, self.session_id, "auto")
        path = self._autosave_path()
        return load_world(path) if path.is_file() else None

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
        handlers = {"pause": self._pause, "speed": self._speed, "refill": self._refill,
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
        tasks = [*(task for task, _revision in self.pending.values()), *self.writing.values()]
        self._invalidate_requests()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class TavernSessions:
    """Own one runtime per device session; only sessions with an open page advance."""

    def __init__(self, map_data: Mapping[str, Any], save_dir: Path, ai_config: Mapping[str, Any],
                 seed: int = 0, database_url: str | None = None, scenario: Scenario | None = None) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.save_dir = save_dir
        self.ai_config = dict(ai_config)
        self.database_url = database_url
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
        runtime = TavernRuntime(self.map_data, self.save_dir / session_id / "save.json", self.ai_config,
                                seed, self.database_url, session_id, self.scenario)
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
        await sessions.release(session_id)


def create_app(map_path: Path, save_dir: Path, ai_config: Mapping[str, Any],
               run_loop: bool = True, database_url: str | None = None, seed: int = 0,
               scenario_path: Path | None = None, characters_dir: Path | None = None,
               ask: Ask | None = None) -> FastAPI:
    """Construct the local server with explicit paths and AI configuration.

    Args:
        map_path: JSON layout to initialize the room.
        save_dir: Directory of per-session snapshot files, used without a database.
        ai_config: Evaluator settings, including an optional server-only key.
        run_loop: Whether to start automatic ticking; false for focused API tests.
        database_url: Optional PostgreSQL URL for persistent session snapshots.
        seed: Seed of the sessions' arrivals and decision policies.
        scenario_path: Optional JSON scenario; sessions then open its evenings instead of
            starting with the room's own visitors.
        characters_dir: Optional folder of character cards (one JSON file each) the scenario
            casts its guests from.
        ask: Optional Claude port bound to the server's key, for the card compiler; without
            it the compiler runs its labeled offline mode.
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
    if database_url:
        initialize_database(database_url)
    sessions = TavernSessions(map_data, save_dir, ai_config, seed, database_url, scenario)
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
        environment variables.
    """
    working_root = Path.cwd()
    root = (working_root if (working_root / "data" / "tavern.json").is_file()
            else Path(__file__).resolve().parents[2])
    config = {"typesafe_api_key": os.environ.get("TYPESAFE_API_KEY"),
              "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(os.environ.get("AI_TIMEOUT", "8")),
              "temperature": float(os.environ.get("AI_TEMPERATURE", "0.25"))}
    database_url = (os.environ.get("DATABASE_URL")
                     if os.environ.get("TAVERN_DATABASE_ENABLED") == "true" else None)
    return create_app(root / "data" / "tavern.json", root / "saves", config,
                      database_url=database_url, seed=Random().randrange(1 << 30),
                      scenario_path=root / "data" / "scenarios" / "first_evening.json",
                      characters_dir=root / "data" / "characters",
                      ask=_claude_port(os.environ.get("ANTHROPIC_API_KEY")))


def _claude_port(key: str | None) -> Ask | None:
    # The key stays on the server; without one the card compiler runs offline.
    if not key:
        return None
    config = {"anthropic_api_key": key, "model": "claude-haiku-4-5", "timeout": 30.0, "retries": 1}

    async def ask(question: Question) -> dict[str, Any]:
        return (await ask_claude(question, config))[0]
    return ask
