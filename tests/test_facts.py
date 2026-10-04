"""News and the copies of it that guests carry: the scenario's items, who starts holding them, and saves."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import step_world
from tavern.mind.haiku_turns import RejectedTurn, parse_turn, turn_question
from tavern.social.turns import check_turn, turn_view
from social_hall import actor, scene_of, say, seated_talk


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


def hold(world: dict[str, Any], guest_id: str, fact_id: str = "toll", told_as: str = "The toll is doubled.",
         **fields: Any) -> None:
    """Let a guest of a hall without a scenario hold a copy of a news item, adding the item to the world."""
    if all(entry["id"] != fact_id for entry in world["news"]):
        world["news"].append({"id": fact_id, "topic": f"the {fact_id}", "text": "The toll has doubled.",
                              "known_by": [guest_id]})
    actor(world, guest_id)["knowledge"]["facts"][fact_id] = {
        "topic": f"the {fact_id}", "told_as": told_as, "heard_from": None, "heard_at": 0.0, "confidence": 1.0,
        "hops": 0, "overheard": False, **fields}


def talk_with_news(*holders: str) -> dict[str, Any]:
    """Ada and Bea sit talking; the given guests hold the toll news."""
    world = seated_talk(social=100.0)
    for guest_id in holders:
        hold(world, guest_id)
    return world


def view_of(world: dict[str, Any]) -> dict[str, Any]:
    """The turn view of Ada and Bea's scene; Ada speaks first."""
    return turn_view(world, scene_of(world))


@pytest.mark.parametrize("holders, offered", [
    pytest.param([], False, id="speaker-without-news"),
    pytest.param(["bea"], False, id="only-the-listener-holds-news"),
    pytest.param(["ada"], True, id="speaker-with-news"),
    pytest.param(["ada", "bea"], True, id="both-hold-news"),
])
def test_share_news_is_offered_only_while_the_speaker_holds_news(holders: list[str], offered: bool) -> None:
    assert ("share_news" in view_of(talk_with_news(*holders))["acts"]) is offered


def test_the_view_shows_the_speaker_their_own_copies_by_id() -> None:
    world = talk_with_news()
    hold(world, "ada", "wolves", "Wolves took a sheep.", heard_from="bea", hops=1, confidence=0.75)
    hold(world, "ada", "toll")
    assert view_of(world)["speaker"]["news"] == [
        {"id": "toll", "topic": "the toll", "told_as": "The toll is doubled.", "heard_from": None, "confidence": 1.0},
        {"id": "wolves", "topic": "the wolves", "told_as": "Wolves took a sheep.", "heard_from": "Bea",
         "confidence": 0.75}]


def test_the_view_names_a_teller_as_the_speaker_calls_them() -> None:
    world = talk_with_news()
    actor(world, "ada")["relations"] = {}
    actor(world, "bea")["card"] = {"looks": "the stout woman with a pipe"}
    hold(world, "ada", "toll", heard_from="bea", hops=1)
    assert view_of(world)["speaker"]["news"][0]["heard_from"] == "the stout woman with a pipe"


def test_the_view_names_a_teller_who_has_gone_home() -> None:
    world = talk_with_news()
    hold(world, "ada", "toll", heard_from="cid", hops=1)
    world["departed"].append(world["actors"].pop(2))
    assert view_of(world)["speaker"]["news"][0]["heard_from"] == "Cid"


def retold(**fields: Any) -> dict[str, Any]:
    """A writer's answer that tells the toll news."""
    return {"line": "They say the toll is doubled.", "act": "share_news", "addressee": "bea", "topic": "the toll",
            "fact_id": "toll", **fields}


def without(*names: str) -> dict[str, Any]:
    """A news-telling answer lacking some fields."""
    return {key: value for key, value in retold().items() if key not in names}


def test_a_turn_telling_news_the_speaker_holds_is_valid() -> None:
    assert check_turn(view_of(talk_with_news("ada")), retold()) == retold()


@pytest.mark.parametrize("answer", [
    pytest.param(without("fact_id"), id="news-without-a-fact"),
    pytest.param(retold(fact_id=None), id="news-with-a-null-fact"),
    pytest.param(retold(fact_id="rumour"), id="a-fact-the-speaker-does-not-hold"),
    pytest.param(retold(fact_id=7), id="malformed-fact"),
    pytest.param({**retold(), "act": "joke"}, id="fact-on-a-joke"),
    pytest.param({**retold(fact_id=None), "act": "joke"}, id="null-fact-on-a-joke"),
])
def test_a_turn_with_the_wrong_fact_is_rejected(answer: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        check_turn(view_of(talk_with_news("ada")), answer)


def test_news_cannot_be_told_by_a_speaker_who_holds_none() -> None:
    with pytest.raises(ValueError):
        check_turn(view_of(talk_with_news("bea")), retold())


@pytest.mark.parametrize("answer, expected", [
    pytest.param(retold(), retold(), id="news-with-its-fact"),
    pytest.param({**without("fact_id", "act"), "act": "small_talk", "fact_id": None},
                 without("fact_id", "act") | {"act": "small_talk"}, id="null-fact-means-none"),
])
def test_the_model_boundary_reads_a_fact_and_drops_a_null_one(answer: dict[str, Any],
                                                               expected: dict[str, Any]) -> None:
    assert parse_turn(view_of(talk_with_news("ada")), answer) == expected


@pytest.mark.parametrize("answer", [
    pytest.param(retold(fact_id=None), id="news-with-a-null-fact"),
    pytest.param(retold(fact_id="rumour"), id="unknown-fact"),
    pytest.param({**retold(), "act": "joke"}, id="fact-on-a-joke"),
])
def test_the_model_boundary_rejects_a_wrong_fact(answer: dict[str, Any]) -> None:
    with pytest.raises(RejectedTurn):
        parse_turn(view_of(talk_with_news("ada")), answer)


def test_a_spoken_news_turn_keeps_its_fact_and_other_turns_have_none() -> None:
    world = talk_with_news("ada")
    say(world, "share_news", "They say the toll is doubled.", fact_id="toll")
    say(world, "small_talk", "Hm.")
    assert [turn.get("fact_id") for turn in scene_of(world)["turns"]] == ["toll", None]


def test_a_conversation_with_news_survives_save_and_load(tmp_path: Path) -> None:
    world = talk_with_news("ada")
    say(world, "share_news", "They say the toll is doubled.", fact_id="toll")
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda scene: scene["turns"][0].update(fact_id="rumour"), id="turn-names-an-unknown-fact"),
    pytest.param(lambda scene: scene["turns"][0].update(fact_id=7), id="turn-fact-is-not-text"),
    pytest.param(lambda scene: scene["turns"][0].update(fact_id=None), id="turn-with-a-null-fact"),
])
def test_a_saved_turn_with_a_wrong_fact_is_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = talk_with_news("ada")
    say(world, "share_news", "They say the toll is doubled.", fact_id="toll")
    corrupt(scene_of(world))
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


def test_the_answer_schema_allows_a_fact_id_or_null_whatever_the_act() -> None:
    schema = turn_question(view_of(talk_with_news()))["schema"]
    assert schema["properties"]["fact_id"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
