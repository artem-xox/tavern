"""Taking stock after a game of dice: the result makes a guest write a fresh intention."""

import json

import pytest

from tavern.adapters.persistence import parse_world
from tavern.mind.intentions import INTENTION_RULES, intention_due
from dice_hall import advance, guest, happened, start, table_hall, who


def intended(world: dict, actor_id: str) -> None:
    """Give a guest an intention written at the start of the evening."""
    who(world, actor_id)["intention"] = {
        "thought": "Bored.", "intention": "Find a game.", "written_at": 0.0,
        "trigger": {"kind": "arrival", "text": "Just came in", "time": 0.0}}


def played() -> dict:
    """Ada and Bea play a game to its result while Cid stands by and sees nothing of it."""
    world = table_hall(guest("ada", (8, 8)), guest("bea", (12, 8)), guest("cid", (13, 8)))
    for name in ("ada", "bea", "cid"):
        intended(world, name)
    assert start(world, "ada", "play_dice", "dice-chair-1")["accepted"]
    assert start(world, "bea", "play_dice", "dice-chair-2")["accepted"]
    advance(world, 40)
    return world


@pytest.mark.parametrize("name, kind", [
    pytest.param("ada", "dice", id="a-player"),
    pytest.param("bea", "dice", id="the-other-player"),
    pytest.param("cid", None, id="a-guest-who-saw-nothing"),
])
def test_players_take_stock_after_the_result_and_bystanders_do_not(name: str, kind: str | None) -> None:
    world = played()
    assert len(happened(world, "dice_won")) == 1
    trigger = intention_due(world, who(world, name), INTENTION_RULES)
    assert (trigger["kind"] if trigger else None) == kind


def test_a_save_holding_an_intention_written_after_a_game_loads_back() -> None:
    world = played()
    trigger = intention_due(world, who(world, "ada"), INTENTION_RULES)
    who(world, "ada")["intention"] = {"thought": "Won.", "intention": "Celebrate.", "written_at": world["time"],
                                      "trigger": trigger}
    assert parse_world(json.dumps(world)) == world
