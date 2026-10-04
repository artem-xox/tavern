"""A small evening in the repository's hall with its barkeep, shared by the tests of staff and bartending."""

import json
from pathlib import Path
from typing import Any

from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import start_action, step_world
from tavern.mind.cards import parse_cards

ROOT = Path(__file__).parents[1]
LAYOUT = json.loads((ROOT / "data" / "tavern.json").read_text())
HOB = {"id": "hob", "name": "Hob", "color": "#c98f4a", "sprite": "bartender", "post": "bar",
       "traits": {"patience": 0.8, "courage": 0.6}}
NEEDS = {"thirst": [55, 90], "fatigue": [40, 80], "bladder": [0, 25], "social": [15, 65], "boredom": [5, 35]}
TAP_SPOT = (6, 3)
TAKE_BEER = {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}


def cards(folder: str) -> dict[str, Any]:
    """The repository's character cards of a folder, by ID."""
    return parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / folder).glob("*.json"))])


def plan(*staff: dict[str, Any], guests: int = 2, **fields: Any) -> dict[str, Any]:
    """A scenario of inline guests arriving at the start and closing at 300 s, with the given staff."""
    people = [{"id": name, "name": name.capitalize(), "color": "#ccaa88", "sprite": "visitor",
               "traits": {"patience": 0.5}, "arrives_at": 0} for name in ("ada", "bea", "cid")[:guests]]
    return {"guests": people, "arrival": {"needs": NEEDS}, "closes_at": 300, "staff": list(staff), **fields}


def opened(*staff: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """The repository's hall opened for a small evening with the given staff."""
    return open_evening(LAYOUT, parse_scenario(plan(*staff, **fields)), seed=1)


def person(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """A visitor who is in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def hob_of(world: dict[str, Any]) -> dict[str, Any]:
    """The barkeep, who is in the hall."""
    return person(world, "hob")


def place(world: dict[str, Any], actor_id: str, cell: tuple[int, int]) -> None:
    """Put a visitor on a cell, where the test wants them."""
    person(world, actor_id).update(x=cell[0], y=cell[1])


def order_beer(world: dict[str, Any], actor_id: str) -> None:
    """Send a guest standing at the tap's spot to take a beer, which starts at once where they stand."""
    place(world, actor_id, TAP_SPOT)
    assert start_action(world, actor_id, TAKE_BEER) == {"accepted": True, "reason": None}


def advance(world: dict[str, Any], seconds: float, step: float = 0.1) -> None:
    """Advance the world by whole ticks of `step` seconds."""
    for _ in range(round(seconds / step)):
        step_world(world, step)


def events(world: dict[str, Any], kind: str) -> list[str]:
    """Messages of the logged events of a type, oldest first."""
    return [item["message"] for item in world["events"] if item["type"] == kind]
