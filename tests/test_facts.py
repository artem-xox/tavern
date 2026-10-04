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
from tavern.mind.scripted import scripted_turn
from tavern.social.turns import check_turn, turn_view
from social_hall import actor, advance, scene_of, say, seated_talk


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


def befriend(world: dict[str, Any], listener: str, other: str, familiarity: str) -> None:
    """Let a guest regard another with the given familiarity."""
    actor(world, listener)["relations"][other] = {"name": other.title(), "opinion": 0.0, "familiarity": familiarity,
                                                  "knows_name": True}


def copy_of(world: dict[str, Any], guest_id: str, fact_id: str = "toll") -> dict[str, Any] | None:
    """A guest's copy of a news item, or None."""
    return actor(world, guest_id)["knowledge"]["facts"].get(fact_id)


def tell(world: dict[str, Any], line: str = "They say the toll is doubled.", fact_id: str = "toll") -> str:
    """Let the speaker of Ada and Bea's scene tell the news."""
    return say(world, "share_news", line, fact_id=fact_id)


def test_the_listener_carries_the_words_they_heard_one_hop_further() -> None:
    world = talk_with_news("ada")
    tell(world, "They say the toll is doubled.")
    assert copy_of(world, "bea") == {"topic": "the toll", "told_as": "They say the toll is doubled.",
                                     "heard_from": "ada", "heard_at": scene_of(world)["turns"][-1]["time"],
                                     "confidence": 0.6, "hops": 1, "overheard": False}


@pytest.mark.parametrize("familiarity, confidence", [
    pytest.param("friend", 0.9, id="friend"),
    pytest.param("acquaintance", 0.75, id="acquaintance"),
    pytest.param("stranger", 0.6, id="stranger"),
])
def test_belief_is_the_tellers_confidence_times_trust_in_the_teller(familiarity: str, confidence: float) -> None:
    world = talk_with_news("ada")
    befriend(world, "bea", "ada", familiarity)
    tell(world)
    assert copy_of(world, "bea")["confidence"] == pytest.approx(confidence)


def test_a_doubtful_teller_passes_on_less_belief() -> None:
    world = talk_with_news()
    hold(world, "ada", confidence=0.8, heard_from="cid", hops=2)
    befriend(world, "bea", "ada", "acquaintance")
    tell(world)
    assert (copy_of(world, "bea")["confidence"], copy_of(world, "bea")["hops"]) == (pytest.approx(0.6), 3)


def test_everyone_in_the_scene_but_the_teller_gets_a_copy_whoever_is_addressed() -> None:
    world = seated_talk(social=100.0, cid_joins=True)
    hold(world, "ada")
    say(world, "share_news", "They say the toll is doubled.", addressee="bea", fact_id="toll")
    assert [guest for guest in ("ada", "bea", "cid") if copy_of(world, guest)["hops"] > 0] == ["bea", "cid"]


def test_a_guest_outside_the_scene_and_out_of_earshot_gets_nothing() -> None:
    world = talk_with_news("ada")
    out_of_earshot(world)
    tell(world)
    assert copy_of(world, "cid") is None


def test_a_guest_who_already_knows_the_news_keeps_their_first_version() -> None:
    world = talk_with_news("ada", "bea")
    actor(world, "bea")["knowledge"]["facts"]["toll"]["told_as"] = "Bea's own version."
    tell(world)
    assert copy_of(world, "bea")["told_as"] == "Bea's own version."


def test_a_second_telling_does_not_replace_the_first_version() -> None:
    world = talk_with_news("ada")
    tell(world, "They say the toll is doubled.")
    say(world, "small_talk")
    tell(world, "A different telling.")
    assert copy_of(world, "bea")["told_as"] == "They say the toll is doubled."


def test_news_told_is_logged_with_the_teller_and_listeners() -> None:
    world = seated_talk(social=100.0, cid_joins=True)
    hold(world, "ada")
    tell(world)
    [event] = [item for item in world["events"] if item["type"] == "news_told"]
    assert (event["actor_id"], "Ada" in event["message"], "the toll" in event["message"],
            "Bea and Cid" in event["message"]) == ("ada", True, True, True)


def test_nothing_is_logged_when_everyone_already_knew() -> None:
    world = talk_with_news("ada", "bea")
    tell(world)
    assert [item for item in world["events"] if item["type"] == "news_told"] == []


def test_telling_news_eases_everyones_wish_for_company() -> None:
    world = talk_with_news("ada")
    before = [actor(world, guest)["needs"]["social"] for guest in ("ada", "bea")]
    tell(world)
    after = [actor(world, guest)["needs"]["social"] for guest in ("ada", "bea")]
    assert all(now < was for now, was in zip(after, before))


def test_telling_the_same_line_without_the_act_gives_no_copy() -> None:
    world = talk_with_news("ada")
    say(world, "remark", "They say the toll is doubled.")
    assert copy_of(world, "bea") is None


def break_rules(**fields: Any) -> Callable[[dict[str, Any]], None]:
    """Overwrite the saved news rules."""
    return lambda world: world["rules"]["news"].update(fields)


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world["rules"].pop("news"), id="no-news-rules"),
    pytest.param(break_rules(extra=1), id="unknown-news-rule"),
    pytest.param(break_rules(trust={"friend": 0.9, "acquaintance": 0.75}), id="trust-without-strangers"),
    pytest.param(break_rules(trust={"friend": 1.5, "acquaintance": 0.75, "stranger": 0.6}), id="trust-above-one"),
    pytest.param(break_rules(trust={"friend": 0.9, "acquaintance": 0.75, "stranger": 0.0}), id="no-trust-at-all"),
    pytest.param(break_rules(overheard=0.0), id="overheard-counts-for-nothing"),
    pytest.param(break_rules(overheard=2), id="overheard-above-one"),
])
def test_corrupt_news_rules_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = talk_with_news("ada")
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


def next_table(world: dict[str, Any]) -> None:
    """Cid, at the next table, hears Ada and Bea well enough to make out their words."""


def out_of_earshot(world: dict[str, Any]) -> None:
    """Cid has walked to the far wall, curious about nothing."""
    cid = actor(world, "cid")
    cid.update(x=11, y=7, seat_id=None, action=None, status="idle")
    cid["traits"]["curiosity"] = 0.0


def noticed_only(world: dict[str, Any]) -> None:
    """Cid is far enough to notice the talk but not to make out the words, and curious about nothing."""
    cid = actor(world, "cid")
    cid.update(x=2, y=7, seat_id=None, action=None, status="idle")
    cid["traits"]["curiosity"] = 0.0


@pytest.mark.parametrize("place, copied", [
    pytest.param(next_table, True, id="words-made-out-at-the-next-table"),
    pytest.param(noticed_only, False, id="only-the-act-noticed"),
    pytest.param(out_of_earshot, False, id="out-of-earshot"),
])
def test_news_is_overheard_only_where_the_words_are_made_out(place: Callable[[dict[str, Any]], None],
                                                              copied: bool) -> None:
    world = talk_with_news("ada")
    advance(world, 0.2)
    place(world)
    tell(world)
    assert (copy_of(world, "cid") is not None) is copied


def test_an_overheard_copy_has_half_the_tellers_confidence_and_says_so() -> None:
    world = talk_with_news("ada")
    advance(world, 0.2)
    tell(world, "They say the toll is doubled.")
    assert copy_of(world, "cid") == {"topic": "the toll", "told_as": "They say the toll is doubled.",
                                     "heard_from": "ada", "heard_at": scene_of(world)["turns"][-1]["time"],
                                     "confidence": 0.5, "hops": 1, "overheard": True}


def test_an_overheard_copy_halves_a_doubtful_tellers_confidence() -> None:
    world = talk_with_news()
    hold(world, "ada", confidence=0.8, heard_from="bea", hops=1)
    advance(world, 0.2)
    tell(world)
    assert copy_of(world, "cid")["confidence"] == pytest.approx(0.4)


def test_an_overhearer_who_already_knows_the_news_keeps_their_version() -> None:
    world = talk_with_news("ada", "cid")
    actor(world, "cid")["knowledge"]["facts"]["toll"]["told_as"] = "Cid's own version."
    advance(world, 0.2)
    tell(world)
    assert copy_of(world, "cid")["told_as"] == "Cid's own version."


def test_overhearing_is_logged_in_the_overhearers_terms() -> None:
    world = talk_with_news("ada")
    advance(world, 0.2)
    tell(world)
    [event] = [item for item in world["events"] if item["type"] == "news_overheard"]
    assert (event["actor_id"], event["message"]) == ("cid", "Cid overheard Ada tell the toll")


def test_a_guest_in_the_scene_is_not_counted_as_overhearing() -> None:
    world = talk_with_news("ada")
    tell(world)
    assert copy_of(world, "bea")["overheard"] is False


def speak_scripted(world: dict[str, Any]) -> dict[str, Any]:
    """Let the next speaker's scripted turn be written and spoken; return it."""
    result = scripted_turn(view_of(world))
    say(world, result["act"], result["line"], fact_id=result.get("fact_id"))
    return result


def after_a_greeting(*holders: str, seed: int = 4) -> dict[str, Any]:
    """Ada has greeted Bea; the given guests hold the toll news; Bea speaks next."""
    world = seated_talk(social=100.0, seed=seed)
    for guest_id in holders:
        hold(world, guest_id)
    say(world, "greet", "Evening, Bea.")
    return world


def test_a_scripted_speaker_with_news_tells_it() -> None:
    result = scripted_turn(view_of(after_a_greeting("bea")))
    assert (result["act"], result["fact_id"], result["addressee"]) == ("share_news", "toll", "ada")


def test_a_scripted_speaker_without_news_never_tells_any() -> None:
    assert scripted_turn(view_of(after_a_greeting("ada")))["act"] != "share_news"


def test_a_scripted_speaker_does_not_tell_back_what_was_just_told_in_the_scene() -> None:
    world = after_a_greeting("bea")
    speak_scripted(world)
    assert scripted_turn(view_of(world))["act"] != "share_news"


@pytest.mark.parametrize("told_as, heard_from, line", [
    pytest.param("The toll is doubled.", None, "The toll is doubled.", id="first-holder-says-it-as-it-is"),
    pytest.param("The toll is doubled.", "cid", "Heard from Cid: The toll is doubled.", id="names-the-teller"),
    pytest.param("Heard from Edda: The toll is doubled.", "cid", "Heard from Cid: The toll is doubled.",
                 id="prefixes-do-not-nest"),
    pytest.param("x" * 300, "cid", ("Heard from Cid: " + "x" * 300)[:160], id="cut-to-160-characters"),
    pytest.param("x" * 300, None, "x" * 160, id="first-holder-cut-to-160-characters"),
])
def test_the_scripted_line_retells_the_speakers_own_version(told_as: str, heard_from: str | None, line: str) -> None:
    world = after_a_greeting()
    hold(world, "bea", told_as=told_as, heard_from=heard_from, hops=0 if heard_from is None else 1)
    assert scripted_turn(view_of(world))["line"] == line


def test_scripted_speakers_choose_among_their_news_by_the_seeded_draw() -> None:
    chosen = set()
    for seed in range(1, 9):
        world = after_a_greeting(seed=seed)
        hold(world, "bea", "toll")
        hold(world, "bea", "wolves")
        first = scripted_turn(view_of(world))
        assert first == scripted_turn(view_of(world))
        chosen.add(first["fact_id"])
    assert chosen == {"toll", "wolves"}


@pytest.mark.parametrize("confidence, words", [
    pytest.param(1.0, "you are sure of it", id="first-hand"),
    pytest.param(0.9, "you are sure of it", id="from-a-friend"),
    pytest.param(0.6, "you believe it", id="from-a-stranger"),
    pytest.param(0.45, "a rumour you half believe", id="overheard-from-a-stranger"),
])
def test_the_writer_is_told_how_sure_the_speaker_is_in_words(confidence: float, words: str) -> None:
    world = talk_with_news()
    hold(world, "ada", confidence=confidence, heard_from="bea", hops=1)
    content = turn_question(view_of(world))["content"]
    assert words in content and "0.45" not in content and "0.6" not in content


def test_the_writer_sees_each_copy_in_the_speakers_words_with_its_teller() -> None:
    world = talk_with_news("ada")
    hold(world, "ada", "wolves", "Wolves took a sheep.", heard_from="bea", hops=1, confidence=0.75)
    content = turn_question(view_of(world))["content"]
    assert [text in content for text in ('id "toll"', "The toll is doubled.", 'id "wolves"', "Wolves took a sheep.",
                                         "heard from Bea")] == [True] * 5


def test_the_writer_never_sees_the_original_text() -> None:
    world = talk_with_news("ada")
    world["news"][0]["text"] = "The ORIGINAL words."
    assert "ORIGINAL" not in turn_question(view_of(world))["content"]


def test_a_writer_with_no_news_is_told_it_has_none_to_tell() -> None:
    assert "cannot use share_news" in turn_question(view_of(talk_with_news()))["content"]


@pytest.mark.parametrize("holders, nudged", [
    pytest.param([], False, id="no-news-no-nudge"),
    pytest.param(["ada"], True, id="news-not-yet-told"),
])
def test_the_writer_is_nudged_to_tell_news_it_carries(holders: list[str], nudged: bool) -> None:
    content = turn_question(view_of(talk_with_news(*holders)))["content"]
    assert ("carries news" in content) is nudged


def test_news_told_once_is_not_nudged_again() -> None:
    world = talk_with_news("ada")
    tell(world)
    say(world, "small_talk")
    assert "carries news" not in turn_question(view_of(world))["content"]


def test_the_prefix_teaches_retelling_and_no_longer_allows_invented_news() -> None:
    prefix = turn_question(view_of(talk_with_news()))["system"][0]
    assert ("small personal news from the road is fine" in prefix, "fact_id" in prefix, "Example 22." in prefix) == (
        False, True, True)
