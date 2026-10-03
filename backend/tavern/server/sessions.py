"""The sessions of a server: one runtime per device, attached to pages and saved when the last page leaves."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from random import Random
import re
from typing import Any, Mapping

from tavern.evening.scenario import Scenario
from tavern.mind.intentions import Intender
from tavern.mind.model_health import HealthBoard
from tavern.mind.scripted import write_scripted_turn
from tavern.server.runtime import Chooser, Store, TavernRuntime, choose_action
from tavern.social.turns import TurnWriter


# Session IDs also name save directories, so only path-safe characters are allowed.
SESSION_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


class TavernSessions:
    """Own one runtime per device session; only sessions with an open page advance."""

    def __init__(self, map_data: Mapping[str, Any], save_dir: Path, ai_config: Mapping[str, Any],
                 seed: int = 0, database_url: str | None = None, scenario: Scenario | None = None,
                 writer: TurnWriter = write_scripted_turn, writer_label: str = "scripted",
                 intender: Intender | None = None, store_for: Callable[[str], Store] | None = None,
                 choose: Chooser | None = None, health: HealthBoard | None = None) -> None:
        self.map_data = deepcopy(dict(map_data))
        self.writer, self.writer_label = writer, writer_label
        self.save_dir = save_dir
        self.intender = intender
        self.ai_config = dict(ai_config)
        # Which database backs the sessions, if any; `store_for` makes each session's store (default:
        # JSON files under `save_dir`).
        self.database_url = database_url
        self.store_for = store_for
        self.choose, self.health = choose, health
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
                                self.writer, self.writer_label, intender=self.intender,
                                choose=self.choose or choose_action, health=self.health)
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
