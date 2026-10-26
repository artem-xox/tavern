"""A grudge is a reason in words that one guest holds against another: it travels with the tie and gives a cause to lash out."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import load_catalog
from tavern.adapters.persistence import load_world, save_world
from tavern.evening.lineup import lineup_scenario
from tavern.hall.world import create_world
from tavern.mind.portrait import portrait
from tavern.social.hostility import hostile_targets
from tavern.social.ties import own_regard, own_ties, parse_own_ties, parse_regard, parse_ties
from hostile_view import person, thought, view
from social_hall import hall

GRUDGE = "He still owes her money."
IDS = ["ada", "bea"]
NAMES = {"ada": "Ada", "bea": "Bea"}
DRUNK = 0.5


def cell(grudge: Any = None) -> dict[str, Any]:
    """A regard cell, with a grudge unless it is None."""
    return {"kind": "disliked", "note": "A bore.", **({} if grudge is None else {"grudge": grudge})}


def pair(grudge: Any = None) -> list[dict[str, Any]]:
    """A shared starting relationship of Ada and Bea, with a grudge unless it is None."""
    return [{"a": "ada", "b": "bea", "kind": "rivals", "note": "Old rivals.", **({} if grudge is None else {"grudge": grudge})}]


def held(grudge: Any = None) -> list[dict[str, Any]]:
    """The tie Ada holds toward Bea, as a saved guest keeps it."""
    return [{"with": "bea", "name": "Bea", "kind": "rivals", "note": "Old rivals.",
             **({} if grudge is None else {"grudge": grudge})}]


# Every way a tie is read or handed on, as a function of its grudge.
WAYS: list[Any] = [
    pytest.param(lambda grudge: parse_regard({"ada": {"bea": cell(grudge)}}, IDS)[0], id="regard-matrix"),
    pytest.param(lambda grudge: parse_ties(pair(grudge), IDS)[0], id="shared-tie"),
    pytest.param(lambda grudge: own_ties("ada", parse_ties(pair(grudge), IDS), NAMES)[0], id="tie-held-by-a-guest"),
    pytest.param(lambda grudge: own_regard("ada", parse_regard({"ada": {"bea": cell(grudge)}}, IDS), NAMES)[0],
                 id="regard-held-by-a-guest"),
    pytest.param(lambda grudge: parse_own_ties(held(grudge))[0], id="saved-guest-ties"),
]


@pytest.mark.parametrize("grudge, expected", [
    pytest.param(GRUDGE, GRUDGE, id="a-reason"),
    pytest.param(None, None, id="none-given"),
])
@pytest.mark.parametrize("way", WAYS)
def test_a_grudge_travels_with_the_tie_when_there_is_one(way: Callable[[Any], dict[str, Any]], grudge: Any,
                                                         expected: str | None) -> None:
    assert way(grudge).get("grudge") == expected


@pytest.mark.parametrize("grudge", [
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
    pytest.param(5, id="not-text"),
])
@pytest.mark.parametrize("way", WAYS)
def test_a_grudge_without_words_fails_loudly(way: Callable[[Any], dict[str, Any]], grudge: Any) -> None:
    with pytest.raises(ValueError, match="grudge"):
        way(grudge)


def grudging(observation: dict[str, Any], about: str = "bea", reason: Any = GRUDGE) -> dict[str, Any]:
    """Give Ada a tie toward someone, with a grudge unless `reason` is None."""
    observation["actor"]["ties"] = [{"with": about, "name": about.title(), "kind": "disliked", "note": "A bore.",
                                     **({} if reason is None else {"grudge": reason})}]
    return observation


@pytest.mark.parametrize("observation, expected", [
    pytest.param(grudging(view(opinion=-40.0, drunkenness=DRUNK)), ["bea"], id="a-grudge-needs-no-fresh-cause"),
    pytest.param(grudging(view(opinion=-40.0, drunkenness=DRUNK), reason=None), [], id="a-tie-without-a-grudge-is-no-cause"),
    pytest.param(grudging(view(opinion=-40.0, drunkenness=DRUNK), about="cid"), [], id="a-grudge-against-someone-else"),
    pytest.param(grudging(view(opinion=-9.0, drunkenness=DRUNK)), [], id="a-grudge-does-not-make-an-ill-opinion"),
    pytest.param(grudging(view(opinion=-40.0)), [], id="a-grudge-does-not-make-a-sober-guest-fight"),
    pytest.param(grudging(view(opinion=-40.0, drunkenness=DRUNK, people=[person("bea", table_id="far", seat_id="fw")])), [],
                 id="a-grudge-does-not-reach-another-table"),
    pytest.param(grudging(view([thought("quarrel", "bea", 30.0)], opinion=-40.0, drunkenness=DRUNK)), ["bea"],
                 id="a-fresh-cause-still-counts-beside-a-grudge"),
])
def test_a_grudge_is_a_cause_for_a_drunk_hothead_to_fight(observation: dict[str, Any], expected: list[str]) -> None:
    assert hostile_targets(observation, "start_fight") == expected


def test_a_grudge_is_a_cause_to_shove_too() -> None:
    assert hostile_targets(grudging(view(opinion=-40.0)), "shove") == ["bea"]


def test_a_grudge_survives_a_save(tmp_path: Path) -> None:
    data = hall()
    data["actors"][0]["ties"] = held(GRUDGE)
    world = create_world(data)
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json")["actors"][0]["ties"] == held(GRUDGE)


ROOT = Path(__file__).resolve().parents[1]

# The grudges the famous guests bring, as (holder, toward): each has a reason in the guest's own relationship.
FAMOUS = [
    pytest.param("putin", "zelensky", id="putin-zelensky"),
    pytest.param("zelensky", "putin", id="zelensky-putin"),
    pytest.param("zelensky", "trump", id="zelensky-trump"),
    pytest.param("trump", "zuckerberg", id="trump-zuckerberg"),
    pytest.param("musk", "zuckerberg", id="musk-zuckerberg"),
    pytest.param("zuckerberg", "musk", id="zuckerberg-musk"),
]


@pytest.mark.parametrize("holder, toward", FAMOUS)
def test_famous_guests_bring_their_grudges_into_the_evening(holder: str, toward: str) -> None:
    catalog = load_catalog(ROOT / "characters")
    templates = {"guests": json.loads((ROOT / "data" / "scenarios" / "guests.json").read_text())}
    guests = lineup_scenario(templates, catalog, "guests", [holder, toward], 5).guests
    tie = next(item for guest in guests if guest["id"] == holder for item in guest["ties"] if item["with"] == toward)
    assert tie.get("grudge")


def test_a_portrait_tells_the_grudge_a_guest_holds() -> None:
    actor = {"card": None, "ties": [{"name": "Bea", "kind": "rivals", "note": "Old rivals.", "grudge": GRUDGE}]}
    assert portrait(actor) == f"Bea is a rival of theirs (Old rivals.). They hold a grudge against them: {GRUDGE}"
