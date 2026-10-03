"""Scenario guests cast from character cards, and the ties between them that the evening starts with."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.mind.cards import PARAMS, Card, parse_cards
from tavern.evening.scenario import open_evening, parse_scenario

ROOT = Path(__file__).parents[1]


def card(card_id: str, name: str, **params: float) -> dict[str, Any]:
    """Build a card whose words name the guest and whose params are middling unless given."""
    return {"id": card_id, "name": name, "sprite": "visitor", "occupation": "drover", "background": "Drives cattle.",
            "temperament": f"{name} is easygoing.", "speech": "Slow.", "quirks": "Whistles.", "secret": "None to tell.",
            "goal": f"{name} wants a quiet drink.", "params": {**dict.fromkeys(PARAMS, 0.5), **params}}


def library() -> dict[str, Card]:
    """Two cards, Ada's and Bea's."""
    return parse_cards([card("ada-card", "Ada", temper=0.9), card("bea-card", "Bea")])


def cast(guest_id: str, card_id: str, name: str, arrives_at: float = 0, **fields: Any) -> dict[str, Any]:
    """Describe a guest the scenario casts from a card."""
    return {"id": guest_id, "name": name, "color": "#a08060", "sprite": "visitor", "card": card_id,
            "arrives_at": arrives_at, **fields}


def scenario(guests: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    """Describe an evening with the given guests, closing at 300 s."""
    return {"guests": guests, "arrival": {"needs": {"thirst": [50, 90]}}, "closes_at": 300, **fields}


def tie(a: str, b: str, kind: str = "old friends", note: str = "Served together.") -> dict[str, str]:
    """Describe a starting relationship between two guests."""
    return {"a": a, "b": b, "kind": kind, "note": note}


TWO = [cast("ada", "ada-card", "Ada"), cast("bea", "bea-card", "Bea", 60)]


def test_card_guest_takes_the_cards_params_as_traits() -> None:
    guest = parse_scenario(scenario(TWO[:1]), library()).guests[0]
    assert (guest["traits"]["temper"], guest["traits"]["patience"], guest["card"]["goal"]) == (
        0.9, 0.5, "Ada wants a quiet drink.")


@pytest.mark.parametrize("guests, cards", [
    pytest.param([cast("ada", "zed-card", "Ada")], library(), id="unknown-card"),
    pytest.param([cast("ada", "ada-card", "Bea")], library(), id="name-differs-from-card"),
    pytest.param([cast("ada", "ada-card", "Ada", sprite="edda")], library(), id="sprite-differs-from-card"),
    pytest.param([cast("ada", "ada-card", "Ada", traits={"patience": 0.5})], library(), id="traits-and-card"),
    pytest.param([cast("ada", 7, "Ada")], library(), id="malformed-card-id"),
])
def test_miscast_guest_fails_loudly(guests: list[dict[str, Any]], cards: dict[str, Card]) -> None:
    with pytest.raises(ValueError):
        parse_scenario(scenario(guests), cards)


def test_without_a_card_library_card_guests_come_with_middling_traits() -> None:
    # Only the schedule is read: a guest's card is resolved when the shell passes the library.
    guest = parse_scenario(scenario(TWO[:1])).guests[0]
    assert (guest["traits"], "card" in guest) == ({}, False)


@pytest.mark.parametrize("ties, expected", [
    pytest.param([], ((), [], []), id="empty-ties"),
    pytest.param([tie("ada", "bea")], (("ada", "bea"), ["bea"], ["ada"]), id="single-tie"),
    pytest.param([tie("bea", "ada", "rivals")], (("bea", "ada"), ["bea"], ["ada"]), id="listed-either-way"),
])
def test_each_side_of_a_tie_knows_the_other(ties: list[dict[str, str]],
                                            expected: tuple[tuple[str, ...], list[str], list[str]]) -> None:
    parsed = parse_scenario(scenario(TWO, relationships=ties), library())
    ada, bea = parsed.guests
    pairs = tuple(name for item in parsed.ties for name in (item["a"], item["b"]))
    assert (pairs, [item["with"] for item in ada.get("ties", [])],
            [item["with"] for item in bea.get("ties", [])]) == expected


def test_a_guest_sees_the_others_name_kind_and_note() -> None:
    ada = parse_scenario(scenario(TWO, relationships=[tie("ada", "bea", "rivals", "Bea won the ox.")]),
                         library()).guests[0]
    assert ada["ties"] == [{"with": "bea", "name": "Bea", "kind": "rivals", "note": "Bea won the ox."}]


@pytest.mark.parametrize("ties", [
    pytest.param("ada and bea", id="malformed-ties"),
    pytest.param([tie("ada", "zed")], id="unknown-guest"),
    pytest.param([tie("ada", "ada")], id="tie-to-oneself"),
    pytest.param([tie("ada", "bea"), tie("bea", "ada", "rivals")], id="duplicate-pair"),
    pytest.param([tie("ada", "bea", "lovers")], id="unknown-kind"),
    pytest.param([tie("ada", "bea", note="")], id="empty-note"),
    pytest.param([{**tie("ada", "bea"), "since": 1203}], id="unknown-field"),
])
def test_malformed_ties_fail_loudly(ties: Any) -> None:
    with pytest.raises(ValueError):
        parse_scenario(scenario(TWO, relationships=ties), library())


def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a door in the bottom wall."""
    return {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]}]}


def test_guests_bring_their_card_and_ties_into_the_evening() -> None:
    world = open_evening(hall(), parse_scenario(scenario(TWO, relationships=[tie("ada", "bea")]), library()), 1)
    ada, bea = world["actors"][0], world["expected"][0]
    assert (ada["card"]["id"], [item["name"] for item in ada["ties"]], bea["card"]["id"]) == (
        "ada-card", ["Bea"], "bea-card")


def test_guest_without_a_card_has_none() -> None:
    guest = {"id": "ada", "name": "Ada", "color": "#a08060", "sprite": "visitor", "traits": {}, "arrives_at": 0}
    ada = open_evening(hall(), parse_scenario(scenario([guest])), 1)["actors"][0]
    assert (ada["card"], ada["ties"]) == (None, [])


def test_repository_scenario_casts_every_guest_from_a_preset() -> None:
    cards = parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])
    parsed = parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()), cards)
    assert all("card" in guest for guest in parsed.guests)
    assert len(parsed.ties) == 2
