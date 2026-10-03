"""Saved evenings keep each guest's character card and ties, and refuse corrupt ones."""

from pathlib import Path
from typing import Any, Callable

import pytest

from tavern.mind.cards import PARAMS, parse_cards
from tavern.adapters.persistence import load_world, save_world
from tavern.evening.scenario import open_evening, parse_scenario


def card(card_id: str, name: str) -> dict[str, Any]:
    """Build a card with middling params."""
    return {"id": card_id, "name": name, "sprite": "visitor", "occupation": "drover", "background": "Drives cattle.",
            "temperament": "Easygoing.", "speech": "Slow.", "quirks": "Whistles.", "secret": "None to tell.",
            "goal": "A quiet drink.", "params": dict.fromkeys(PARAMS, 0.5)}


def evening() -> dict[str, Any]:
    """Open a small hall for Ada, inside, and Bea, still expected; they are old friends."""
    guests = [{"id": name.lower(), "name": name, "color": "#a08060", "sprite": "visitor", "card": f"{name}-card",
               "arrives_at": time} for name, time in (("Ada", 0), ("Bea", 60))]
    data = {"guests": guests, "arrival": {"needs": {"thirst": [40, 80]}}, "closes_at": 300,
            "relationships": [{"a": "ada", "b": "bea", "kind": "old friends", "note": "Grew up together."}]}
    hall = {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]}]}
    cards = parse_cards([card("Ada-card", "Ada"), card("Bea-card", "Bea")])
    return open_evening(hall, parse_scenario(data, cards), seed=3)


def test_cards_and_ties_survive_save_and_load(tmp_path: Path) -> None:
    world = evening()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=3), id="version-3-save"),
    pytest.param(lambda world: world["actors"][0]["card"]["params"].update(temper=2), id="param-out-of-range"),
    pytest.param(lambda world: world["actors"][0]["card"].pop("goal"), id="card-without-goal"),
    pytest.param(lambda world: world["actors"][0].update(card="Ada-card"), id="malformed-card"),
    pytest.param(lambda world: world["actors"][0].pop("card"), id="missing-card"),
    pytest.param(lambda world: world["actors"][0]["ties"][0].update(kind="lovers"), id="unknown-tie-kind"),
    pytest.param(lambda world: world["actors"][0].update(ties={}), id="malformed-ties"),
    pytest.param(lambda world: world["expected"][0]["card"]["params"].update(temper=-1), id="expected-card-param"),
])
def test_corrupt_cards_and_ties_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = evening()
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
