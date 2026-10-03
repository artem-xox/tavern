"""Character cards: who a guest is in words, and the numbers the rules read."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.mind.cards import PARAMS, parse_card, parse_card_text, parse_cards

ROOT = Path(__file__).parents[1]


def text(**fields: Any) -> dict[str, Any]:
    """Describe a guest in words, the way a player writes a card."""
    return {"name": "Ada", "occupation": "ferrywoman", "background": "Ran the ford for twenty years.",
            "temperament": "Calm until crossed.", "speech": "Short sentences.", "quirks": "Counts coins twice.",
            "secret": "Lets smugglers cross at night.", "goal": "Hear news of the toll.", **fields}


def card(card_id: str = "ada", **fields: Any) -> dict[str, Any]:
    """Build a complete card with middling params."""
    return {"id": card_id, "sprite": "visitor", **text(), "params": dict.fromkeys(PARAMS, 0.5), **fields}


def test_card_keeps_its_words_and_params() -> None:
    parsed = parse_card(card(params={**dict.fromkeys(PARAMS, 0.5), "temper": 1, "courage": 0}))
    assert (parsed["name"], parsed["goal"], parsed["params"]["temper"], parsed["params"]["courage"]) == (
        "Ada", "Hear news of the toll.", 1.0, 0.0)


@pytest.mark.parametrize("data", [
    pytest.param([], id="malformed-card"),
    pytest.param({}, id="empty-card"),
    pytest.param({key: value for key, value in card().items() if key != "goal"}, id="missing-goal"),
    pytest.param(card(mood="grim"), id="unknown-field"),
    pytest.param(card(id=""), id="empty-id"),
    pytest.param(card(temperament=""), id="empty-temperament"),
    pytest.param(card(speech=7), id="malformed-speech"),
    pytest.param(card(params={}), id="empty-params"),
    pytest.param(card(params={**dict.fromkeys(PARAMS, 0.5), "luck": 0.5}), id="unknown-param"),
    pytest.param(card(params={key: 0.5 for key in PARAMS if key != "temper"}), id="missing-param"),
    pytest.param(card(params={**dict.fromkeys(PARAMS, 0.5), "temper": 1.5}), id="param-above-one"),
    pytest.param(card(params={**dict.fromkeys(PARAMS, 0.5), "temper": -0.1}), id="param-below-zero"),
    pytest.param(card(params={**dict.fromkeys(PARAMS, 0.5), "temper": "hot"}), id="malformed-param"),
    pytest.param(card(params={**dict.fromkeys(PARAMS, 0.5), "temper": True}), id="boolean-param"),
])
def test_invalid_card_fails_loudly(data: Any) -> None:
    with pytest.raises(ValueError):
        parse_card(data)


@pytest.mark.parametrize("records, expected", [
    pytest.param([], [], id="empty-library"),
    pytest.param([card("ada")], ["ada"], id="single-card"),
    pytest.param([card("bea"), card("ada")], ["ada", "bea"], id="keyed-by-id"),
])
def test_cards_are_keyed_by_id(records: list[dict[str, Any]], expected: list[str]) -> None:
    assert sorted(parse_cards(records)) == expected


def test_duplicate_card_ids_fail_loudly() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        parse_cards([card("ada"), card("ada")])


@pytest.mark.parametrize("data", [
    pytest.param({}, id="empty-text"),
    pytest.param("Ada", id="malformed-text"),
    pytest.param({key: value for key, value in text().items() if key != "goal"}, id="missing-goal"),
    pytest.param(text(params={"temper": 0.5}), id="params-are-not-written-by-the-player"),
    pytest.param(text(goal="   "), id="blank-goal"),
    pytest.param(text(background="x" * 2001), id="too-long"),
])
def test_invalid_player_text_fails_loudly(data: Any) -> None:
    with pytest.raises(ValueError):
        parse_card_text(data)


def test_player_text_keeps_every_field() -> None:
    assert parse_card_text(text()) == text()


def presets() -> dict[str, Any]:
    """Read the repository's preset cards."""
    return parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])


def test_eight_presets_with_distinct_temperaments_and_goals() -> None:
    cards = presets()
    assert len(cards) == 8
    assert len({item["temperament"] for item in cards.values()}) == 8
    assert len({item["goal"] for item in cards.values()}) == 8
    assert len({tuple(item["params"].values()) for item in cards.values()}) == 8


def test_presets_use_shipped_sprites() -> None:
    shipped = {path.name for path in (ROOT / "frontend" / "static" / "characters").iterdir() if path.is_dir()}
    assert {item["sprite"] for item in presets().values()} <= shipped
