"""FastAPI transport and nonblocking orchestration of autonomous tavern agents."""

import asyncio
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
import json
import math
import os
from pathlib import Path
from random import Random
from typing import Any, AsyncIterator, Mapping

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from tavern.agents import choose_action
from tavern.database import initialize_database, load_database_world, save_database_world
from tavern.persistence import load_world, save_world
from tavern.world import create_world, object_cells, observe_actor, start_action, step_world


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


class TavernRuntime:
    """Own world state and one asynchronous decision request per visitor."""

    def __init__(self, map_data: Mapping[str, Any], save_path: Path,
                 ai_config: Mapping[str, Any], seed: int = 0,
                 database_url: str | None = None) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.world = create_world(self.map_data, seed)
        self.save_path = save_path
        self.database_url = database_url
        self.ai_config = {"model": "jev-latest", "timeout": 8.0, "temperature": 0.25, **ai_config}
        self.rng = Random(seed)
        self.pending: dict[str, tuple[asyncio.Task[Any], int]] = {}
        self.revisions: dict[str, int] = {}
        self.next_decision: dict[str, float] = {}

    def snapshot(self) -> dict[str, Any]:
        """Return a client envelope with credentials excluded.

        Returns:
            Independent world copy and public evaluator configuration.
        """
        configured = bool(self.ai_config.get("typesafe_api_key"))
        return {"type": "snapshot", "state": deepcopy(self.world), "ai": {
            "mode": "jev" if configured else "local", "configured": configured,
            "model": self.ai_config["model"],
        }}

    def _event(self, message: str) -> None:
        self.world["events"].append({"time": self.world["time"], "actor_id": None,
                                      "type": "control", "message": message})
        self.world["events"] = self.world["events"][-100:]

    def _apply_decision(self, actor: dict[str, Any], task: asyncio.Task[Any], revision: int) -> None:
        if revision != self.revisions.get(actor["id"], 0) or actor["status"] != "idle" or self._receiving_conversation(actor):
            with suppress(asyncio.CancelledError, Exception):
                task.result()
            return
        try:
            decision = task.result()
            actor["decision"] = {key: decision[key] for key in ("source", "scores", "error")}
            result = start_action(self.world, actor["id"], decision["action"])
            if not result["accepted"]:
                self._event(f"{actor['name']}: {result['reason']}")
        except Exception as error:
            actor["decision"] = {"source": "local", "scores": {}, "error": str(error)}
            self._event(f"Decision failed for {actor['name']}")
        self.next_decision[actor["id"]] = self.world["time"] + 1.0

    def _collect_decisions(self) -> None:
        for actor in self.world["actors"]:
            pending = self.pending.get(actor["id"])
            if pending is not None and pending[0].done():
                del self.pending[actor["id"]]
                self._apply_decision(actor, *pending)

    def _request_decisions(self) -> None:
        for actor in self.world["actors"]:
            actor_id = actor["id"]
            if actor["status"] != "idle" or actor_id in self.pending or self._receiving_conversation(actor):
                continue
            if self.world["time"] < self.next_decision.get(actor_id, 0):
                continue
            observation = observe_actor(self.world, actor_id)
            task = asyncio.create_task(choose_action(observation, self.ai_config, self.rng))
            self.pending[actor_id] = (task, self.revisions.get(actor_id, 0))

    def _receiving_conversation(self, actor: Mapping[str, Any]) -> bool:
        return any(item.get("action") and item["action"]["verb"] == "talk"
                   and item["action"]["target_id"] == actor["id"] for item in self.world["actors"])

    def advance(self, dt: float) -> None:
        """Advance the world without waiting for AI requests.

        Args:
            dt: Real seconds since the previous simulation tick.
        """
        step_world(self.world, dt)
        if not self.world["paused"]:
            self._collect_decisions()
            self._request_decisions()

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
        for task, _revision in self.pending.values():
            task.cancel()
        self.pending.clear()
        self.revisions.clear()
        self.next_decision.clear()

    def _save(self, command: Mapping[str, Any]) -> None:
        if self.database_url:
            save_database_world(self.world, self.database_url)
        else:
            save_world(self.world, self.save_path)

    def _load(self, command: Mapping[str, Any]) -> None:
        restored = load_database_world(self.database_url) if self.database_url else load_world(self.save_path)
        if restored is None:
            raise ValueError("No saved world exists")
        self._invalidate_requests()
        self.world = restored

    def _reset(self, command: Mapping[str, Any]) -> None:
        restored = create_world(self.map_data)
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
        tasks = [task for task, _revision in self.pending.values()]
        self._invalidate_requests()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def _run_world(runtime: TavernRuntime, tick_seconds: float) -> None:
    while True:
        runtime.advance(tick_seconds)
        await asyncio.sleep(tick_seconds)


async def _send_snapshots(socket: WebSocket, runtime: TavernRuntime, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        await socket.send_json(runtime.snapshot())


async def _serve_socket(socket: WebSocket, runtime: TavernRuntime) -> None:
    await socket.accept()
    await socket.send_json(runtime.snapshot())
    sender = asyncio.create_task(_send_snapshots(socket, runtime, 0.1))
    try:
        while True:
            try:
                runtime.command(await socket.receive_json())
                await socket.send_json(runtime.snapshot())
            except ValueError as error:
                await socket.send_json({"type": "error", "message": str(error)})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
            await sender


def create_app(map_path: Path, save_path: Path, ai_config: Mapping[str, Any],
               run_loop: bool = True, database_url: str | None = None) -> FastAPI:
    """Construct the local server with explicit paths and AI configuration.

    Args:
        map_path: JSON layout to initialize the room.
        save_path: Snapshot destination used by save/load controls.
        ai_config: Evaluator settings, including an optional server-only key.
        run_loop: Whether to start automatic ticking; false for focused API tests.
        database_url: Optional PostgreSQL URL for persistent world snapshots.
    Returns:
        Application serving JSON state and a bidirectional WebSocket.
    """
    map_data = json.loads(map_path.read_text())
    if database_url:
        initialize_database(database_url)
        restored = load_database_world(database_url)
        runtime = TavernRuntime(map_data, save_path, ai_config, database_url=database_url)
        if restored is not None:
            runtime.world = restored
    else:
        runtime = TavernRuntime(map_data, save_path, ai_config)
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ticker = asyncio.create_task(_run_world(runtime, 0.1)) if run_loop else None
        yield
        if ticker is not None:
            ticker.cancel()
            with suppress(asyncio.CancelledError):
                await ticker
        await runtime.close()
    app = FastAPI(title="The Last Inn", lifespan=lifespan)
    app.state.runtime = runtime
    _register_routes(app, runtime)
    return app


def _register_routes(app: FastAPI, runtime: TavernRuntime) -> None:
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}
    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        return runtime.snapshot()
    @app.websocket("/ws")
    async def websocket(socket: WebSocket) -> None:
        await _serve_socket(socket, runtime)


def create_default_app() -> FastAPI:
    """Read launch configuration and create the local demo application.

    Returns:
        Server initialized from the repository's map and environment variables.
    """
    root = Path(__file__).resolve().parents[2]
    config = {"typesafe_api_key": os.environ.get("TYPESAFE_API_KEY"),
              "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(os.environ.get("AI_TIMEOUT", "8")),
              "temperature": float(os.environ.get("AI_TEMPERATURE", "0.25"))}
    return create_app(root / "data" / "tavern.json", root / "saves" / "demo.json", config,
                      database_url=os.environ.get("DATABASE_URL"))
