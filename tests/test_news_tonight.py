"""Only some of a scenario's news is told tonight: drawn by the evening's seed, each item with a single holder."""

import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.staff import guests
from tavern.hall.world import step_world
from tavern.social.facts import News, draw_news

ROOT = Path(__file__).parents[1]


def item(item_id: str, known_by: list[str]) -> News:
    """Describe a news item the way a scenario file does."""
    return News(id=item_id, topic=f"the {item_id}", text=f"Word is that the {item_id} has changed.", known_by=known_by)


FIVE = [item("toll", ["ada", "bea"]), item("wolves", ["ada"]), item("salt", ["cid", "bea"]),
        item("pass", ["bea"]), item("fort", ["cid", "ada", "bea"])]


@pytest.mark.parametrize("news, count, expected_ids", [
    pytest.param(FIVE, 5, ["toll", "wolves", "salt", "pass", "fort"], id="every-item-in-listed-order"),
    pytest.param(FIVE[:1], 1, ["toll"], id="single-item"),
])
def test_telling_every_item_keeps_them_in_listed_order(news: list[News], count: int, expected_ids: list[str]) -> None:
    assert [entry["id"] for entry in draw_news(news, count, Random(3))] == expected_ids


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in range(10)])
def test_each_drawn_item_has_one_holder_from_its_own_list(seed: int) -> None:
    drawn = draw_news(FIVE, 3, Random(seed))
    originals = {entry["id"]: entry for entry in FIVE}
    assert len(drawn) == 3
    assert [entry["id"] for entry in drawn] == sorted((entry["id"] for entry in drawn), key=lambda found: [e["id"] for e in FIVE].index(found))
    for entry in drawn:
        assert len(entry["known_by"]) == 1 and entry["known_by"][0] in originals[entry["id"]]["known_by"]
        assert (entry["topic"], entry["text"]) == (originals[entry["id"]]["topic"], originals[entry["id"]]["text"])


def test_an_item_with_a_single_holder_keeps_them() -> None:
    assert draw_news([item("wolves", ["ada"])], 1, Random(0))[0]["known_by"] == ["ada"]


def test_the_same_seed_draws_the_same_news() -> None:
    assert draw_news(FIVE, 2, Random("5:news")) == draw_news(FIVE, 2, Random("5:news"))


def test_drawing_leaves_the_original_news_untouched() -> None:
    before = json.dumps(FIVE)
    draw_news(FIVE, 2, Random(1))
    assert json.dumps(FIVE) == before


@pytest.mark.parametrize("count", [
    pytest.param(0, id="none"),
    pytest.param(6, id="more-than-there-are"),
    pytest.param(-1, id="negative"),
])
def test_telling_an_impossible_number_of_items_fails_loudly(count: int) -> None:
    with pytest.raises(ValueError, match="news"):
        draw_news(FIVE, count, Random(0))


def guest(guest_id: str, arrives_at: float = 0) -> dict[str, Any]:
    """Describe a guest the way a scenario file does."""
    return {"id": guest_id, "name": guest_id.title(), "color": "#c09060", "sprite": "visitor",
            "traits": {"patience": 0.5}, "arrives_at": arrives_at}


def scenario(**fields: Any) -> dict[str, Any]:
    """Describe an evening of Ada, Bea and Cid with five news items, plus the given fields."""
    return {"guests": [guest("ada"), guest("bea"), guest("cid", 30)], "arrival": {"needs": {"thirst": [50, 90]}},
            "closes_at": 300, "news": FIVE, **fields}


def hall() -> dict[str, Any]:
    """Build a 10×7 hall with a door with room for three guests at once, and a tap."""
    return {"width": 10, "height": 7, "blocked": [[x, 6] for x in range(10) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 6, "interaction_spots": [[5, 5], [4, 5], [6, 5]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5}]}


def evening(seed: int, **fields: Any) -> dict[str, Any]:
    """Open the evening and let time pass without decisions, so that every guest has come in."""
    world = open_evening(hall(), parse_scenario(scenario(**fields)), seed)
    for _ in range(80):
        step_world(world, 0.5)
    return world


def news_holders(world: dict[str, Any]) -> list[str]:
    """The guests who came in knowing something."""
    return [actor["id"] for actor in guests(world) if actor["knowledge"]["facts"]]


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in range(6)])
def test_with_one_item_told_exactly_one_guest_knows_it(seed: int) -> None:
    world = evening(seed, news_tonight=1)
    assert len(world["news"]) == 1
    assert news_holders(world) == world["news"][0]["known_by"]


def test_two_items_told_are_held_by_two_holders() -> None:
    world = evening(4, news_tonight=2)
    assert len(world["news"]) == 2 and all(len(entry["known_by"]) == 1 for entry in world["news"])


def test_a_scenario_without_the_field_tells_all_its_news_as_listed() -> None:
    world = evening(4)
    assert world["news"] == FIVE
    assert sorted(news_holders(world)) == ["ada", "bea", "cid"]


def test_drawing_the_news_does_not_move_anyones_arrival_needs() -> None:
    plain = open_evening(hall(), parse_scenario(scenario()), 4)
    drawn = open_evening(hall(), parse_scenario(scenario(news_tonight=1)), 4)
    assert [item["needs"] for item in [*guests(plain), *plain["expected"]]] == [
        item["needs"] for item in [*guests(drawn), *drawn["expected"]]]


@pytest.mark.parametrize("value", [
    pytest.param(0, id="zero"),
    pytest.param(6, id="more-than-the-items"),
    pytest.param(-1, id="negative"),
    pytest.param("one", id="text"),
    pytest.param(1.0, id="float"),
    pytest.param(True, id="boolean"),
])
def test_a_malformed_number_of_items_told_fails_loudly(value: Any) -> None:
    with pytest.raises(ValueError, match="news_tonight"):
        parse_scenario(scenario(news_tonight=value))


def test_telling_news_with_no_news_listed_fails_loudly() -> None:
    with pytest.raises(ValueError, match="news_tonight"):
        parse_scenario(scenario(news=[], news_tonight=1))


def first_evening_world(seed: int) -> dict[str, Any]:
    """Open the repository's first evening at a seed."""
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    return open_evening(room, parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text())), seed)


def test_the_first_evening_tells_one_item_and_the_seed_picks_it() -> None:
    told = {first_evening_world(seed)["news"][0]["id"] for seed in range(20)}
    assert len(first_evening_world(0)["news"]) == 1
    assert len(told) >= 3
