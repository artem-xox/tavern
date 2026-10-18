"""Famous guests start the evening with their own, uneven opinion of each other, read from a matrix."""

import json
from itertools import permutations
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import load_catalog
from tavern.evening.lineup import lineup_scenario
from tavern.mind.characters import parse_catalog
from tavern.social.thoughts import seed_relations

from tests.test_character_catalog import profile

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "characters")
TEMPLATES = {"guests": json.loads((ROOT / "data" / "scenarios" / "guests.json").read_text())}
GUESTS = sorted(item["id"] for item in CATALOG.characters.values() if item["cast"] == "guests")


def cell(kind: str = "disliked", note: str = "He talks over her.") -> dict[str, str]:
    return {"kind": kind, "note": note}


def holds(ids: list[str]) -> dict[str, dict[str, str]]:
    """Each picked guest's tie kinds by the other's ID, as the lineup's scenario gives them."""
    guests = lineup_scenario(TEMPLATES, CATALOG, "guests", ids, 5).guests
    return {guest["id"]: {tie["with"]: tie["kind"] for tie in guest.get("ties", [])} for guest in guests}


@pytest.mark.parametrize("kind, opinion, familiarity", [
    pytest.param("adored", 50.0, "acquaintance", id="adored"),
    pytest.param("admired", 30.0, "acquaintance", id="admired"),
    pytest.param("well known", 0.0, "acquaintance", id="well-known"),
    pytest.param("looked down on", -20.0, "acquaintance", id="looked-down-on"),
    pytest.param("disliked", -35.0, "acquaintance", id="disliked"),
    pytest.param("loathed", -60.0, "acquaintance", id="loathed"),
])
def test_each_regard_kind_starts_at_its_opinion(kind: str, opinion: float, familiarity: str) -> None:
    relations = seed_relations([{"a": "ada", "b": "bea", "kind": kind}], {"ada": "Ada", "bea": "Bea"})
    assert (relations["ada"]["bea"]["opinion"], relations["ada"]["bea"]["familiarity"]) == (opinion, familiarity)


def test_a_catalog_keeps_each_guests_regard_for_each_other() -> None:
    catalog = parse_catalog([profile("ada"), profile("bea")], {"ada": {"bea": cell("adored", "A fan since girlhood.")},
                                                              "bea": {"ada": cell("looked down on", "A fan, no more.")}})
    assert [(item["holder"], item["toward"], item["kind"]) for item in catalog.regard] == [
        ("ada", "bea", "adored"), ("bea", "ada", "looked down on")]


@pytest.mark.parametrize("matrix", [
    pytest.param({"ada": {"zed": cell()}}, id="unknown-target"),
    pytest.param({"zed": {"ada": cell()}}, id="unknown-holder"),
    pytest.param({"ada": {"ada": cell()}}, id="regard-for-oneself"),
    pytest.param({"ada": {"bea": cell("adoring")}}, id="unknown-kind"),
    pytest.param({"ada": {"bea": cell(note=" ")}}, id="empty-note"),
    pytest.param({"ada": {"bea": {"kind": "disliked"}}}, id="missing-note"),
    pytest.param({"ada": []}, id="a-row-that-is-no-mapping"),
])
def test_a_malformed_regard_matrix_is_rejected_loudly(matrix: Any) -> None:
    with pytest.raises(ValueError, match="(?i)regard"):
        parse_catalog([profile("ada"), profile("bea")], matrix)


def test_a_pair_with_a_catalog_tie_is_not_in_the_matrix_as_well() -> None:
    ada = profile("ada", relationships=[{"with": "bea", "kind": "old friends", "note": "A winter camp."}])
    with pytest.raises(ValueError, match="(?i)regard.*bea.*ada"):
        parse_catalog([ada, profile("bea")], {"bea": {"ada": cell()}})


@pytest.mark.parametrize("ids, expected", [
    pytest.param(["zelensky", "putin"], {"zelensky": {"putin": "loathed"}, "putin": {"zelensky": "loathed"}},
                 id="the-two-at-war-loathe-each-other"),
    pytest.param(["trump", "zelensky"], {"trump": {"zelensky": "looked down on"},
                                         "zelensky": {"trump": "disliked"}}, id="trump-looks-down-on-a-politician"),
    pytest.param(["monroe", "putin"], {"monroe": {"putin": "disliked"}, "putin": {"monroe": "admired"}},
                 id="uneven-regard-is-kept-per-side"),
])
def test_a_lineup_seats_guests_with_their_own_regard_for_each_other(ids: list[str],
                                                                    expected: dict[str, dict[str, str]]) -> None:
    assert holds(ids) == expected


@pytest.mark.parametrize("ids", [
    pytest.param(["greta", "monroe"], id="monroe-and-greta"),
    pytest.param(["monroe", "musk", "tyson", "queen", "zelensky"], id="monroe-and-four-more"),
])
def test_everyone_adores_marilyn_monroe(ids: list[str]) -> None:
    others = [guest for guest in ids if guest != "monroe"]
    assert [holds(ids)[guest]["monroe"] for guest in others] == ["adored"] * len(others)


def test_the_catalog_ties_still_win_for_their_pair() -> None:
    assert holds(["trump", "greta"]) == {"trump": {"greta": "bad blood"}, "greta": {"trump": "bad blood"}}


def test_every_ordered_pair_of_famous_guests_has_a_regard_or_a_catalog_tie() -> None:
    covered = {(item["holder"], item["toward"]) for item in CATALOG.regard}
    covered |= {pair for tie in CATALOG.ties for pair in ((tie["a"], tie["b"]), (tie["b"], tie["a"]))}
    assert [pair for pair in permutations(GUESTS, 2) if pair not in covered] == []
