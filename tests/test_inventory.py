"""What a visitor carries as the world builds, saves and shows it: one count per item kind."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.arrival import create_actor
from tavern.hall.room import create_map
from tavern.hall.world import create_world
from tavern.server.runtime import TavernRuntime


def room() -> dict[str, Any]:
    return create_map({"width": 4, "height": 4, "blocked": [], "objects": []})


def guest(**fields: Any) -> dict[str, Any]:
    return {"id": "ada", "name": "Ada", "x": 1, "y": 1, **fields}


@pytest.mark.parametrize(("fields", "expected"), [
    pytest.param({}, {"beer": 0}, id="nothing-said"),
    pytest.param({"inventory": {}}, {"beer": 0}, id="empty-inventory"),
    pytest.param({"inventory": {"beer": 1}}, {"beer": 1}, id="one-mug"),
])
def test_a_guest_arrives_with_what_the_scenario_gives_them(fields: dict[str, Any], expected: dict[str, int]) -> None:
    assert create_actor(guest(**fields), room())["inventory"] == expected


@pytest.mark.parametrize("inventory", [
    pytest.param({"beer": -1}, id="negative"),
    pytest.param({"beer": True}, id="boolean"),
    pytest.param({"beer": 1.5}, id="fraction"),
    pytest.param({"wine": 1}, id="unknown-kind"),
])
def test_a_guest_with_a_malformed_inventory_is_refused(inventory: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="nventory"):
        create_actor(guest(inventory=inventory), room())


def saved(damage: Callable[[dict[str, Any]], Any]) -> str:
    world = create_world({"width": 6, "height": 4, "blocked": [], "objects": [], "actors": [guest()]})
    damage(world["actors"][0]["inventory"])
    return json.dumps(world)


def test_a_saved_inventory_loads_whole() -> None:
    world = parse_world(saved(lambda inventory: inventory.update(beer=1)))
    assert world["actors"][0]["inventory"] == {"beer": 1}


@pytest.mark.parametrize("damage", [
    pytest.param(lambda inventory: inventory.pop("beer"), id="missing-kind"),
    pytest.param(lambda inventory: inventory.update(beer=-1), id="negative"),
    pytest.param(lambda inventory: inventory.update(beer=True), id="boolean"),
    pytest.param(lambda inventory: inventory.update(beer="1"), id="text"),
    pytest.param(lambda inventory: inventory.update(wine=1), id="unknown-kind"),
])
def test_a_damaged_saved_inventory_is_rejected(damage: Callable[[dict[str, Any]], Any]) -> None:
    with pytest.raises(ValueError, match="Could not load the world"):
        parse_world(saved(damage))


def test_the_snapshot_names_every_kind_of_item(tmp_path: Path) -> None:
    runtime = TavernRuntime(guest_room(), tmp_path / "save.json", {"typesafe_api_key": None})
    assert runtime.snapshot()["items"] == {"beer": {"one": "a mug of ale", "many": "mugs of ale"}}


def guest_room() -> dict[str, Any]:
    return {"width": 6, "height": 4, "tile_size": 32, "blocked": [], "objects": [], "actors": [guest()]}
