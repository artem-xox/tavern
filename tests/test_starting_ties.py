"""Starting relationships from the scenario become guests' opinions on arrival."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.hall.arrival import create_actor
from tavern.hall.room import create_map
from tavern.social.thoughts import familiarity_of, opinion_of

ROOT = Path(__file__).resolve().parents[1]


def guest(ties: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": "ada", "name": "Ada", "x": 1, "y": 1, "ties": ties}


def tie(kind: str, other: str = "bea") -> dict[str, Any]:
    return {"with": other, "name": other.title(), "kind": kind, "note": "Known each other for years."}


def room() -> dict[str, Any]:
    return create_map({"width": 4, "height": 4, "blocked": [], "objects": []})


@pytest.mark.parametrize(("ties", "other", "opinion", "familiarity"), [
    pytest.param([], "bea", 0.0, "stranger", id="no-ties"),
    pytest.param([tie("old friends")], "bea", 50.0, "friend", id="old-friends"),
    pytest.param([tie("rivals")], "bea", -40.0, "acquaintance", id="rivals"),
    pytest.param([tie("old friends"), tie("rivals", "cid")], "cid", -40.0, "acquaintance", id="several-ties"),
])
def test_a_guest_arrives_with_opinions_of_old_ties(ties: list[dict[str, Any]], other: str,
                                                    opinion: float, familiarity: str) -> None:
    actor = create_actor(guest(ties), room())
    assert (opinion_of(actor, other, now=0.0), familiarity_of(actor, other)) == (opinion, familiarity)


def test_unknown_tie_kind_fails_loudly() -> None:
    with pytest.raises(ValueError, match="starting relationship"):
        create_actor(guest([tie("cousins")]), room())


def test_first_evening_opens_with_its_old_friends_and_rivals() -> None:
    from tavern.mind.cards import parse_cards
    from tavern.evening.scenario import open_evening, parse_scenario
    cards = parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])
    scenario = parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()), cards)
    world = open_evening(json.loads((ROOT / "data" / "tavern.json").read_text()), scenario, seed=1)
    guests = {item["id"]: item for item in [*world["actors"], *world["expected"]]}
    assert familiarity_of(guests["ivo"], "nell") == "acquaintance"
    assert opinion_of(guests["ivo"], "nell", now=0.0) < 0
