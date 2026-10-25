"""A famous guest's card lists the news of their last two years, which every guest around them has heard too."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import load_catalog
from tavern.mind.cards import parse_card, persona_words

from test_cards import card

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "characters")
GUESTS = sorted(item["id"] for item in CATALOG.characters.values() if item["cast"] == "guests")
# Guests who are dead: their news stops before their death, and they must not learn of it.
DEAD = ("monroe", "queen", "thatcher")
# Words that would tell them it is over; another person's death (Prince Philip's, Clark Gable's) is ordinary news.
DEATH_WORDS = ("her death", "late queen", "late lady", "late marilyn", "mourn", "posthum", "passed away",
               "after she died", "since she died", "king charles", "queen consort")


def items(count: int) -> list[str]:
    return [f"Item {number} happened." for number in range(count)]


@pytest.mark.parametrize("count", [pytest.param(10, id="ten"), pytest.param(15, id="fifteen")])
def test_ten_to_fifteen_news_items_are_kept_as_written(count: int) -> None:
    assert parse_card(card(news=items(count)))["news"] == items(count)


@pytest.mark.parametrize("news", [
    pytest.param([], id="none"),
    pytest.param(items(1), id="single"),
    pytest.param(items(9), id="nine"),
    pytest.param(items(16), id="sixteen"),
    pytest.param(["a"] * 16, id="duplicates-over-the-limit"),
    pytest.param(items(9) + [""], id="blank-item"),
    pytest.param("Item 0 happened.", id="not-a-list"),
])
def test_news_outside_ten_to_fifteen_texts_fails_loudly(news: Any) -> None:
    with pytest.raises(ValueError, match="news"):
        parse_card(card(news=news))


def test_a_writer_is_told_the_news_in_order() -> None:
    words = persona_words(parse_card(card(news=items(10))))
    assert words["News of the last two years, known to everyone"] == " | ".join(items(10))


def test_a_card_without_news_adds_nothing_for_the_writer() -> None:
    assert persona_words(card()) == {}


@pytest.mark.parametrize("guest", [pytest.param(guest, id=guest) for guest in GUESTS])
def test_a_famous_guest_has_ten_to_fifteen_news_items(guest: str) -> None:
    assert 10 <= len(CATALOG.characters[guest]["card"]["news"]) <= 15


@pytest.mark.parametrize("guest", [pytest.param(guest, id=guest) for guest in DEAD])
def test_a_dead_guest_never_hears_of_their_own_death(guest: str) -> None:
    text = " ".join(CATALOG.characters[guest]["card"]["news"]).lower()
    assert [word for word in DEATH_WORDS if word in text] == []
