"""FastAPI transport: the app, its routes and the WebSocket of a device session."""

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
import json
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from tavern.adapters.database import DatabaseStore, initialize_database
from tavern.evening.scenario import parse_scenario
from tavern.mind.cards import parse_cards
from tavern.mind.intentions import Intender
from tavern.mind.questions import Ask
from tavern.mind.scripted import write_scripted_turn
from tavern.server.cards_api import card_routes
from tavern.server.runtime import Store, TavernRuntime
from tavern.server.sessions import TavernSessions
from tavern.social.turns import TurnWriter


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
