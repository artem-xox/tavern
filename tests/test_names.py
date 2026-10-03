"""Names: strangers are known by their looks until introduced, by old ties, or by an overheard name."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.hall.arrival import create_actor
from tavern.mind.briefing import brief
from tavern.mind.cards import parse_card
from tavern.social.names import called
from tavern.adapters.persistence import load_world, save_world
from tavern.social.turns import turn_view
from tavern.hall.world import observe_actor, observe_people
from tavern.hall.world import start_action
from social_hall import LOOKS, actor, advance, card, command, say, scene_of, seated_talk


def person(guest_id: str, looks: bool = True, **relations: Any) -> dict[str, Any]:
    """A guest record with only what naming reads."""
    return {"id": guest_id, "name": guest_id.title(), "card": card(guest_id) if looks else None,
            "relations": relations}


@pytest.mark.parametrize("viewer, other, expected", [
    pytest.param(person("ada"), person("ada"), "Ada", id="oneself"),
    pytest.param(person("ada"), person("cid"), LOOKS["cid"], id="stranger-by-looks"),
    pytest.param(person("ada"), person("cid", looks=False), "Cid", id="no-looks-only-a-name"),
    pytest.param(person("ada", cid={"name": "Cid", "opinion": 0.0, "familiarity": "acquaintance",
                                    "knows_name": True}), person("cid"), "Cid", id="introduced"),
    pytest.param(person("ada", cid={"name": LOOKS["cid"], "opinion": 0.0, "familiarity": "acquaintance",
                                    "knows_name": False}), person("cid"), LOOKS["cid"], id="met-but-nameless"),
    pytest.param(person("ada", cid={"name": "Cid", "opinion": 0.0, "familiarity": "friend"}), person("cid"),
                 LOOKS["cid"], id="relation-without-the-flag-is-nameless"),
])
def test_guests_are_called_by_name_only_when_it_is_known(viewer: dict[str, Any], other: dict[str, Any],
                                                         expected: str) -> None:
    assert called(viewer, other) == expected


@pytest.mark.parametrize("looks, valid", [
    pytest.param("the grey-bearded man in a green cloak", True, id="short-looks"),
    pytest.param("", False, id="empty-looks"),
    pytest.param(7, False, id="malformed-looks"),
    pytest.param("x" * 201, False, id="too-long"),
])
def test_card_looks_are_short_text(looks: Any, valid: bool) -> None:
    data = {**card("cid"), "looks": looks}
    if valid:
        assert parse_card(data)["looks"] == looks
    else:
        with pytest.raises(ValueError):
            parse_card(data)


def test_every_preset_card_has_looks() -> None:
    root = Path(__file__).parents[1] / "data" / "characters"
    looks = [parse_card(json.loads(path.read_text())).get("looks") for path in sorted(root.glob("*.json"))]
    assert looks and all(looks) and len(set(looks)) == len(looks)


def test_old_ties_know_each_others_names() -> None:
    world_map = {"width": 3, "height": 3}
    guest = {"id": "ada", "name": "Ada", "x": 0, "y": 0, "ties": [
        {"with": "bea", "name": "Bea", "kind": "old friends", "note": "Old friends."},
        {"with": "cid", "name": "Cid", "kind": "rivals", "note": "Rivals."}]}
    relations = create_actor(guest, {**world_map, "blocked": [], "objects": []})["relations"]
    assert [relations[other]["knows_name"] for other in ("bea", "cid")] == [True, True]


def test_an_old_friend_who_learns_a_name_passes_it_on() -> None:
    world = seated_talk(cards=True)
    for one, other in (("bea", "cid"), ("cid", "bea")):
        actor(world, one)["relations"][other] = {"name": other.title(), "opinion": 50.0, "familiarity": "friend",
                                                 "knows_name": True}
    say(world, "introduce", "I'm Ada.")
    assert actor(world, "cid")["relations"]["ada"]["knows_name"] is True


@pytest.mark.parametrize("wall, learns", [
    pytest.param(False, True, id="next-table-catches-the-name"),
    pytest.param(True, False, id="through-a-wall-only-a-murmur"),
])
def test_an_overheard_introduction_teaches_the_name(wall: bool, learns: bool) -> None:
    world = seated_talk(cards=True, wall=wall)
    advance(world, 0.2)
    say(world, "introduce", "I'm Ada, from the ford.")
    assert actor(world, "cid")["relations"].get("ada", {}).get("knows_name", False) is learns


def test_briefing_names_only_people_whose_names_are_known() -> None:
    world = seated_talk(cards=True)
    advance(world, 0.2)
    say(world, "introduce", "I'm Ada.")
    seen = {**observe_actor(world, "bea"), "people": observe_people(world, "bea")}
    situation = brief(seen, [])["situation"]
    assert ("Ada sits" in situation, LOOKS["cid"] in situation, "Cid" in situation) == (True, True, False)


def test_writer_view_names_only_known_participants() -> None:
    world = seated_talk(cards=True)
    say(world, "greet")
    seen = turn_view(world, scene_of(world))["conversation"]["participants"]
    assert seen == [{"id": "ada", "name": LOOKS["ada"], "known": False}, {"id": "bea", "name": "Bea", "known": True}]


def test_a_stranger_who_took_a_seat_is_resented_by_their_looks() -> None:
    world = seated_talk(cards=True)
    advance(world, 15)
    assert start_action(world, "ada", command("sit", "fe"))["accepted"]
    assert start_action(world, "cid", command("sit", "w"))["accepted"]
    advance(world, 8)
    assert [item["text"] for item in actor(world, "ada")["thoughts"] if item["kind"] == "seat_taken"] == [
        f"{LOOKS['cid']} took my seat (Near table · w)"]


def test_names_survive_save_and_load(tmp_path: Path) -> None:
    world = seated_talk(cards=True)
    say(world, "introduce", "I'm Ada.")
    save_world(world, tmp_path / "save.json")
    assert load_world(tmp_path / "save.json")["actors"][1]["relations"]["ada"]["knows_name"] is True


def test_malformed_saved_name_knowledge_is_rejected(tmp_path: Path) -> None:
    world = seated_talk(cards=True)
    say(world, "introduce", "I'm Ada.")
    actor(world, "bea")["relations"]["ada"]["knows_name"] = "yes"
    save_world(world, tmp_path / "save.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "save.json")
