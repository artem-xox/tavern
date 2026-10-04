"""The repository's hall with guests placed by hand round the dice table (helpers, not tests)."""

import json
from pathlib import Path
from typing import Any

from tavern.hall.world import create_world, start_action, step_world

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
MIDDLING = {"patience": 0.5, "curiosity": 0.5, "courage": 0.5}


def guest(actor_id: str, cell: tuple[int, int], traits: dict[str, float] | None = None, **fields: Any) -> dict[str, Any]:
    """Describe a visitor standing on a cell, bored enough to want a game."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": cell[0], "y": cell[1], "traits": traits or MIDDLING,
            "needs": {"boredom": 80, "social": 60}, **fields}


def table_hall(*actors: dict[str, Any], seed: int = 3) -> dict[str, Any]:
    """The real hall with the visitors placed by hand and no arrival draws."""
    room = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    return create_world({**room, "actors": list(actors)}, seed=seed)


def start(world: dict[str, Any], actor_id: str, verb: str, target: str | None = None) -> dict[str, Any]:
    """Start a visitor's action and return the world's answer."""
    return start_action(world, actor_id, {"id": f"{verb}:{target}", "verb": verb, "target_id": target})


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world without requesting decisions."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def who(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a visitor in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def table(world: dict[str, Any]) -> dict[str, Any]:
    """The dice table."""
    return next(item for item in world["map"]["objects"] if item["id"] == "dice-table")


def happened(world: dict[str, Any], kind: str) -> list[str]:
    """The messages of logged events of a kind."""
    return [event["message"] for event in world["events"] if event["type"] == kind]
