"""News and the copies of it that guests carry: the scenario's items, who starts holding them, and saves."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import step_world


ROOT = Path(__file__).parents[1]


def item(item_id: str, known_by: list[str], **fields: Any) -> dict[str, Any]:
    """Describe a news item the way a scenario file does."""
    return {"id": item_id, "topic": f"the {item_id}", "text": f"Word is that the {item_id} has changed.",
            "known_by": known_by, **fields}


NEWS = [item("toll", ["ada"]), item("wolves", ["ada", "bea"]), item("salt", ["cid"])]


def guest(guest_id: str, arrives_at: float = 0) -> dict[str, Any]:
    """Describe a guest the way a scenario file does."""
    return {"id": guest_id, "name": guest_id.title(), "color": "#c09060", "sprite": "visitor",
            "traits": {"patience": 0.5}, "arrives_at": arrives_at}


def scenario(news: Any = None, guests: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Describe an evening: Ada and Bea at opening, Cid half a minute later, with the given news."""
    data = {"guests": guests or [guest("ada"), guest("bea"), guest("cid", 30)],
            "arrival": {"needs": {"thirst": [50, 90]}}, "closes_at": 300}
    return data if news is None else {**data, "news": news}


def hall() -> dict[str, Any]:
    """Build a 10×7 hall with a door with room for three guests at once, and a tap."""
    return {"width": 10, "height": 7, "blocked": [[x, 6] for x in range(10) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 6, "interaction_spots": [[5, 5], [4, 5], [6, 5]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5}]}


def evening(news: Any = None, seconds: float = 40.0) -> dict[str, Any]:
    """Open the evening and let time pass without decisions, so that every guest has come in."""
    world = open_evening(hall(), parse_scenario(scenario(news)), 3)
    for _ in range(round(seconds / 0.5)):
        step_world(world, 0.5)
    return world


def guest_of(world: dict[str, Any], guest_id: str) -> dict[str, Any]:
    """Find a guest in the hall."""
    return next(actor for actor in world["actors"] if actor["id"] == guest_id)


@pytest.mark.parametrize("news, expected", [
    pytest.param([], [], id="no-news"),
    pytest.param([item("toll", ["ada"])], ["toll"], id="single-item"),
    pytest.param(NEWS, ["toll", "wolves", "salt"], id="items-in-listed-order"),
    pytest.param([item("toll", ["ada"]), item("wolves", ["ada"])], ["toll", "wolves"], id="one-holder-of-two"),
])
def test_scenario_keeps_the_news_in_listed_order(news: list[dict[str, Any]], expected: list[str]) -> None:
    assert [entry["id"] for entry in parse_scenario(scenario(news)).news] == expected


def test_scenario_without_news_has_none() -> None:
    assert parse_scenario(scenario()).news == ()


@pytest.mark.parametrize("news", [
    pytest.param("tolls", id="news-is-not-a-list"),
    pytest.param(["tolls"], id="item-is-not-a-record"),
    pytest.param([{key: value for key, value in item("toll", ["ada"]).items() if key != "topic"}], id="missing-topic"),
    pytest.param([item("toll", ["ada"], mood="grim")], id="unknown-field"),
    pytest.param([item("toll", ["ada"]), item("toll", ["bea"])], id="duplicate-ids"),
    pytest.param([item("", ["ada"])], id="empty-id"),
    pytest.param([item("toll", ["ada"], topic="")], id="empty-topic"),
    pytest.param([item("toll", ["ada"], text="  ")], id="blank-text"),
    pytest.param([item("toll", ["ada"], text="x" * 201)], id="text-over-200-characters"),
    pytest.param([item("toll", [])], id="nobody-holds-it"),
    pytest.param([item("toll", "ada")], id="holders-are-not-a-list"),
    pytest.param([item("toll", ["zed"])], id="holder-is-not-a-guest"),
    pytest.param([item("toll", ["ada", "ada"])], id="holder-listed-twice"),
])
def test_malformed_news_fails_loudly(news: Any) -> None:
    with pytest.raises(ValueError):
        parse_scenario(scenario(news))


def test_text_of_exactly_200_characters_is_allowed() -> None:
    assert parse_scenario(scenario([item("toll", ["ada"], text="x" * 200)])).news[0]["text"] == "x" * 200


def test_the_world_keeps_the_original_news() -> None:
    assert evening(NEWS)["news"] == NEWS


@pytest.mark.parametrize("guest_id, expected", [
    pytest.param("ada", ["toll", "wolves"], id="holder-of-two"),
    pytest.param("bea", ["wolves"], id="holder-of-one"),
    pytest.param("cid", ["salt"], id="guest-who-came-in-later"),
])
def test_guests_start_with_the_news_they_are_listed_for(guest_id: str, expected: list[str]) -> None:
    assert sorted(guest_of(evening(NEWS), guest_id)["knowledge"]["facts"]) == expected


def test_a_guest_listed_for_nothing_starts_with_no_news() -> None:
    world = evening([item("toll", ["ada"])])
    assert guest_of(world, "bea")["knowledge"]["facts"] == {}


def test_a_first_holders_copy_is_the_original_text() -> None:
    copy = guest_of(evening(NEWS), "ada")["knowledge"]["facts"]["toll"]
    assert copy == {"topic": "the toll", "told_as": "Word is that the toll has changed.", "heard_from": None,
                    "heard_at": 0.0, "confidence": 1.0, "hops": 0, "overheard": False}


def test_a_guest_who_comes_in_later_has_their_copy_dated_to_their_arrival() -> None:
    copy = guest_of(evening(NEWS), "cid")["knowledge"]["facts"]["salt"]
    assert copy["heard_at"] >= 30.0


def test_news_survives_save_and_load(tmp_path: Path) -> None:
    world = evening(NEWS)
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def break_copy(**fields: Any) -> Callable[[dict[str, Any]], None]:
    """Overwrite fields of Ada's copy of the toll news."""
    return lambda world: guest_of(world, "ada")["knowledge"]["facts"]["toll"].update(fields)


def drop_copy_field(name: str) -> Callable[[dict[str, Any]], None]:
    """Remove a field from Ada's copy of the toll news."""
    return lambda world: guest_of(world, "ada")["knowledge"]["facts"]["toll"].pop(name)


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=6), id="version-6-save-without-news"),
    pytest.param(lambda world: world.pop("news"), id="missing-news"),
    pytest.param(lambda world: world.update(news="tolls"), id="news-is-not-a-list"),
    pytest.param(lambda world: world["news"][0].update(known_by=["zed"]), id="news-held-by-a-stranger"),
    pytest.param(lambda world: world["news"].append(world["news"][0]), id="news-id-repeated"),
    pytest.param(lambda world: world["news"][0].update(text="x" * 201), id="news-text-too-long"),
    pytest.param(lambda world: guest_of(world, "ada")["knowledge"].pop("facts"), id="missing-facts"),
    pytest.param(lambda world: guest_of(world, "ada")["knowledge"].update(facts=["toll"]), id="facts-is-not-a-record"),
    pytest.param(lambda world: guest_of(world, "ada")["knowledge"]["facts"].update(
        rumour=guest_of(world, "ada")["knowledge"]["facts"]["toll"]), id="copy-of-an-unknown-news-item"),
    pytest.param(lambda world: guest_of(world, "ada")["knowledge"]["facts"].update(toll="word"),
                 id="copy-is-not-a-record"),
    pytest.param(drop_copy_field("told_as"), id="copy-without-words"),
    pytest.param(break_copy(extra=1), id="copy-with-an-unknown-field"),
    pytest.param(break_copy(topic="the salt"), id="copy-with-another-topic"),
    pytest.param(break_copy(told_as=""), id="copy-with-no-words"),
    pytest.param(break_copy(confidence=1.5), id="confidence-above-one"),
    pytest.param(break_copy(confidence=0.0), id="no-confidence-at-all"),
    pytest.param(break_copy(hops=-1), id="negative-hops"),
    pytest.param(break_copy(hops=1.5), id="fractional-hops"),
    pytest.param(break_copy(hops=1), id="hops-without-a-teller"),
    pytest.param(break_copy(heard_from="bea"), id="a-teller-at-zero-hops"),
    pytest.param(break_copy(heard_from="zed", hops=1), id="teller-is-not-a-guest"),
    pytest.param(break_copy(heard_at=-1), id="heard-before-the-evening"),
    pytest.param(break_copy(heard_at=1e6), id="heard-in-the-future"),
    pytest.param(break_copy(overheard="yes"), id="overheard-is-not-a-flag"),
])
def test_corrupt_news_is_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = evening(NEWS)
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


def test_the_first_evening_has_four_to_six_news_items_each_held_by_a_guest() -> None:
    parsed = parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()))
    assert 4 <= len(parsed.news) <= 6
    assert {holder for entry in parsed.news for holder in entry["known_by"]} <= {guest["id"] for guest in parsed.guests}
