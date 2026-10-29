"""Signature items: what an item offers only its carrier, and Kim's phone (S2-08)."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import load_catalog
from tavern.body.activities import ACTIVITIES
from tavern.body.fights import open_fight
from tavern.body.items import ITEMS, empty_inventory
from tavern.evening.story_score import WEIGHTS, story_moments, story_score
from tavern.hall.world import create_world, start_action
from tavern.mind.agents import build_candidates
from tavern.social.scenes import start_conversation
from tavern.social.signature_acts import film_room
from social_hall import actor, advance, command, hall
from test_character_catalog_files import catalog


def carrying(*kinds: str) -> dict[str, Any]:
    """A bare observation of a guest holding these things and standing among nobody."""
    return {"actor": {"id": "visitor", "name": "Visitor", "x": 1, "y": 1,
                      "inventory": {"beer": 0, **{kind: 1 for kind in kinds}},
                      "needs": {"thirst": 20, "fatigue": 20, "bladder": 20},
                      "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5}},
            "objects": [], "memory": []}


def offered(view: dict[str, Any]) -> set[str]:
    """The verbs a guest is offered, with families opened up."""
    return {member["verb"] for option in build_candidates(view) for member in option.get("members", [option])}


def with_phone(seed: int = 4) -> dict[str, Any]:
    """The Ada, Bea, Cid and Dan hall, with Ada holding a phone."""
    world = create_world(hall(), seed)
    actor(world, "ada")["inventory"]["phone"] = 1
    return world


@pytest.mark.parametrize("kinds, expected", [
    pytest.param((), False, id="empty-handed"),
    pytest.param(("beer",), False, id="beer-only"),
    pytest.param(("phone",), True, id="phone"),
    pytest.param(("beer", "phone"), True, id="phone-and-beer"),
])
def test_a_phone_offers_livestreaming_to_whoever_carries_it(kinds: tuple[str, ...], expected: bool) -> None:
    assert ("livestream" in offered(carrying(*kinds))) is expected


@pytest.mark.parametrize("kind", [pytest.param(kind, id=kind) for kind, item in ITEMS.items() if item.offers])
def test_a_signature_item_offers_real_verbs_that_need_it_and_stays_with_its_owner(kind: str) -> None:
    item = ITEMS[kind]
    assert ([ACTIVITIES[verb].requires_item for verb in item.offers], item.giftable) == ([kind] * len(item.offers), False)


def test_the_world_refuses_filming_to_a_guest_without_a_phone() -> None:
    world = create_world(hall(), 4)
    assert start_action(world, "ada", command("livestream")) == {"accepted": False, "reason": "No phone in inventory"}


def test_a_phone_cannot_be_given_away() -> None:
    world = with_phone()
    for guest, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, guest, command("sit", chair))["accepted"]
    advance(world, 1)
    result = start_action(world, "ada", {"id": "give:phone:bea", "verb": "give", "target_id": "bea", "item": "phone"})
    assert (result["accepted"], "not for giving away" in result["reason"]) == (False, True)


def quarrel(world: dict[str, Any]) -> None:
    """Bea and Cid trade insults at the near table's edge."""
    scene = start_conversation(world, actor(world, "bea"), actor(world, "cid"))
    scene["turns"] = [{"speaker": speaker, "addressee": other, "line": "Fool!", "act": "insult", "time": 0.0}
                      for speaker, other in (("bea", "cid"), ("cid", "bea"))]


def brawl(world: dict[str, Any]) -> None:
    """Bea and Cid come to blows."""
    open_fight(world, actor(world, "bea"), actor(world, "cid"))


def oration(world: dict[str, Any]) -> None:
    """Dan is up on the stage, giving a speech."""
    dan = actor(world, "dan")
    dan.update(action={"id": "give_speech:stage", "verb": "give_speech", "target_id": None}, status="interacting")


def small_talk(world: dict[str, Any]) -> None:
    """Bea and Cid exchange a single remark, which is no quarrel."""
    scene = start_conversation(world, actor(world, "bea"), actor(world, "cid"))
    scene["turns"] = [{"speaker": "bea", "addressee": "cid", "line": "Fool!", "act": "insult", "time": 0.0}]


@pytest.mark.parametrize("scenes, subjects", [
    pytest.param((), [], id="nothing-happening-is-a-selfie"),
    pytest.param((small_talk,), [], id="a-single-remark-is-no-quarrel"),
    pytest.param((oration,), ["dan"], id="a-speech"),
    pytest.param((quarrel,), ["bea", "cid"], id="a-quarrel"),
    pytest.param((brawl,), ["bea", "cid"], id="a-fight"),
    pytest.param((oration, quarrel), ["bea", "cid"], id="a-quarrel-beats-a-speech"),
    pytest.param((quarrel, brawl, oration), ["bea", "cid"], id="a-fight-beats-everything"),
])
def test_the_phone_films_the_loudest_thing_in_sight_and_only_those_in_it_mind(
        scenes: tuple[Any, ...], subjects: list[str]) -> None:
    world = with_phone()
    for scene in scenes:
        scene(world)
    film_room(world, actor(world, "ada"), None)
    acts = [item for item in world["events"] if item["type"] == "signature_act"]
    minded = sorted(item["id"] for item in world["actors"] if any(thought["kind"] == "filmed" for thought in item["thoughts"]))
    assert ([(item["verb"], item["item"], item["subject"]) for item in acts], minded) == (
        [("livestream", "phone", subjects)], sorted(subjects))


def test_filming_runs_its_course_and_logs_one_act_the_story_score_counts() -> None:
    world = with_phone()
    assert start_action(world, "ada", command("livestream"))["accepted"]
    advance(world, 9)
    moments = story_moments(world["events"])
    assert (actor(world, "ada")["action"], story_score(moments, WEIGHTS)["moments"]["signature_act"]) == (None, 1)


def test_a_signature_act_weighs_less_than_a_fight() -> None:
    assert 0 < WEIGHTS["signature_act"] < WEIGHTS["fight"]


def with_art(tmp_path: Path, carries: dict[str, int], filming: bool) -> Path:
    """A one-guest catalog whose guest carries these things, with or without the `Filming` art."""
    root = catalog(tmp_path)
    folder = root / "locals" / "ada"
    record = json.loads((folder / "character.json").read_text())
    (folder / "character.json").write_text(json.dumps({**record, "carries": carries}))
    if filming:
        for source in (folder / "art" / "Idle" / "rotations").iterdir():
            target = folder / "art" / "Filming" / "rotations" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    return root


@pytest.mark.parametrize("carries, filming, poses_end", [
    pytest.param({}, False, "HelpingUp", id="no-phone-no-filming"),
    pytest.param({"phone": 1}, True, "Filming", id="phone-and-filming"),
])
def test_a_guests_poses_follow_what_they_carry(tmp_path: Path, carries: dict[str, int], filming: bool,
                                               poses_end: str) -> None:
    loaded = load_catalog(with_art(tmp_path, carries, filming))
    assert loaded.public()["characters"][0]["visuals"]["poses"][-1] == poses_end


def test_a_guest_who_carries_a_phone_without_filming_art_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Filming"):
        load_catalog(with_art(tmp_path, {"phone": 1}, False))


def test_empty_inventory_names_every_kind() -> None:
    assert set(empty_inventory()) == set(ITEMS)
