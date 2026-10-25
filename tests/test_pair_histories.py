"""Every pair of famous guests shares a short, true history, which each holder reads from their own side."""

import json
import re
from itertools import permutations
from pathlib import Path

import pytest

from tavern.adapters.characters import load_catalog
from tavern.evening.lineup import lineup_scenario
from tavern.mind.characters import parse_catalog
from tavern.mind.portrait import portrait
from tavern.social.ties import parse_own_ties

from test_character_catalog import profile
from test_recent_news import DEAD, DEATH_WORDS

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "characters")
TEMPLATES = {"guests": json.loads((ROOT / "data" / "scenarios" / "guests.json").read_text())}
GUESTS = sorted(item["id"] for item in CATALOG.characters.values() if item["cast"] == "guests")
HISTORIES = {(item["holder"], item["toward"]): item.get("history", "") for item in CATALOG.regard}
for _tie in CATALOG.ties:  # a pair with a catalog tie keeps its history there, shared by both
    HISTORIES[(_tie["a"], _tie["b"])] = HISTORIES[(_tie["b"], _tie["a"])] = _tie.get("history", "")
PAIRS = list(permutations(GUESTS, 2))


def sentences(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text))


def test_a_regard_cell_keeps_its_history_beside_the_note() -> None:
    cell = {"kind": "disliked", "note": "He talks over her.", "history": "They met once. It went badly."}
    catalog = parse_catalog([profile("ada"), profile("bea")], {"ada": {"bea": cell}})
    assert catalog.regard[0]["history"] == "They met once. It went badly."


def test_a_catalog_tie_keeps_its_history_for_both_guests() -> None:
    ada = profile("ada", relationships=[{"with": "bea", "kind": "rivals", "note": "n", "history": "They met. It ended."}])
    catalog = parse_catalog([ada, profile("bea")])
    assert catalog.ties[0]["history"] == "They met. It ended."


def test_a_blank_history_is_rejected_loudly() -> None:
    cell = {"kind": "disliked", "note": "He talks over her.", "history": " "}
    with pytest.raises(ValueError, match="(?i)regard.*history"):
        parse_catalog([profile("ada"), profile("bea")], {"ada": {"bea": cell}})


def test_a_guest_carries_the_history_of_each_pair_in_a_lineup() -> None:
    guests = lineup_scenario(TEMPLATES, CATALOG, "guests", ["trump", "zelensky"], 5).guests
    ties = {tie["with"]: tie for tie in guests[0]["ties"]}
    assert ties["zelensky"]["history"] == HISTORIES[("trump", "zelensky")]


def test_a_saved_tie_with_a_history_still_parses() -> None:
    tie = {"with": "bea", "name": "Bea", "kind": "disliked", "note": "n", "history": "They met."}
    assert parse_own_ties([tie]) == [tie]


def test_the_portrait_tells_the_history() -> None:
    actor = {"card": None, "ties": [{"name": "Greta", "kind": "disliked", "note": "A note.", "history": "They met in Davos."}]}
    assert "They met in Davos." in portrait(actor)


@pytest.mark.parametrize("holder, toward", [pytest.param(a, b, id=f"{a}-{b}") for a, b in PAIRS])
def test_every_pair_has_a_history_of_three_or_four_sentences(holder: str, toward: str) -> None:
    assert 3 <= sentences(HISTORIES[(holder, toward)]) <= 4


def test_an_evening_seats_eight_guests() -> None:
    ids = ["greta", "kardashian", "musk", "putin", "sobchak", "trump", "tyson", "vucic"]
    assert len(lineup_scenario(TEMPLATES, CATALOG, "guests", ids, 5).guests) == 8


@pytest.mark.parametrize("holder, toward", [pytest.param(a, b, id=f"{a}-{b}") for a, b in PAIRS
                                            if "monroe" in (a, b) or "queen" in (a, b) or "thatcher" in (a, b)])
def test_a_pair_with_a_dead_guest_never_mentions_death(holder: str, toward: str) -> None:
    text = HISTORIES[(holder, toward)].lower()
    assert [word for word in (*DEATH_WORDS, "died", "death", "dead", "funeral") if word in text] == []
