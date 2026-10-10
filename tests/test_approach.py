"""Walking over for a word: a guest goes to a spot at another table and talks with those seated there."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.social.scenes import conversation_of
from social_hall import actor, advance, command, say, spotted_hall

FAR_SPOTS = [[3, 6], [4, 6]]


def evening(seated: dict[str, str], standing: dict[str, tuple[int, int]] | None = None,
            social: float = 95.0) -> dict[str, Any]:
    """Seat the named guests on chairs of `spotted_hall`, stand the others, and let them settle."""
    world = create_world(spotted_hall(standing), 4)
    for name, chair in seated.items():
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = social
    return world


def approach(world: dict[str, Any], who: str = "ada", target: Any = "cid") -> dict[str, Any]:
    """Start a walk over to someone."""
    return start_action(world, who, command("approach", target))


def cid_talks_with_dan(world: dict[str, Any]) -> None:
    """Cid and Dan, who share the far table, are in a conversation."""
    assert start_action(world, "cid", command("talk", "dan"))["accepted"]


@pytest.mark.parametrize("prepare, members", [
    pytest.param(None, ["ada", "cid"], id="a-free-partner"),
    pytest.param(cid_talks_with_dan, ["cid", "dan", "ada"], id="a-partner-in-a-conversation-with-a-tablemate"),
])
def test_an_approach_ends_in_a_conversation_at_the_partners_table(
        prepare: Callable[[dict[str, Any]], None] | None, members: list[str]) -> None:
    world = evening({"ada": "w", "cid": "fw", "dan": "fe"})
    if prepare:
        prepare(world)
    assert approach(world)["accepted"]
    advance(world, 6)
    scene, ada = conversation_of(world, "ada"), actor(world, "ada")
    assert (scene["participants"], scene["table_id"], ada["seat_id"], ada["action"]["verb"]) == (
        members, "far", None, "approach")
    assert [ada["x"], ada["y"]] in FAR_SPOTS


def test_the_two_who_met_this_way_go_on_talking() -> None:
    world = evening({"ada": "w", "cid": "fw"})
    assert approach(world)["accepted"]
    advance(world, 6)
    say(world, "small_talk")
    say(world, "remark")
    assert [turn["act"] for turn in conversation_of(world, "ada")["turns"]][-2:] == ["small_talk", "remark"]


def test_a_walker_leaving_the_table_ends_the_talk() -> None:
    world = evening({"ada": "w", "cid": "fw"})
    assert approach(world)["accepted"]
    advance(world, 6)
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    advance(world, 1)
    assert (conversation_of(world, "ada"), conversation_of(world, "cid")) == (None, None)


def staff_cid(world: dict[str, Any]) -> None:
    """Cid works behind a bar."""
    actor(world, "cid")["post"] = "bar"


def pressed_cid(world: dict[str, Any]) -> None:
    """Cid badly needs the WC."""
    actor(world, "cid")["needs"]["bladder"] = 90.0


def full_scene(world: dict[str, Any]) -> None:
    """The far table's conversation holds as many as it may."""
    cid_talks_with_dan(world)
    world["rules"]["conversation"]["max_participants"] = 2


def ada_talking_to_bea(world: dict[str, Any]) -> None:
    """Ada is already in a conversation at her own table."""
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]


@pytest.mark.parametrize("seated, standing, prepare, who, target", [
    pytest.param({"ada": "w", "cid": "fw"}, None, None, "ada", "ada", id="oneself"),
    pytest.param({"ada": "w", "cid": "fw"}, None, None, "ada", "nobody", id="unknown-guest"),
    pytest.param({"ada": "w", "cid": "fw"}, None, None, "ada", None, id="no-target"),
    pytest.param({"ada": "w", "cid": "fw"}, None, None, "ada", [], id="malformed-target"),
    pytest.param({"ada": "w", "cid": "fw"}, None, staff_cid, "ada", "cid", id="staff"),
    pytest.param({"ada": "w"}, None, None, "ada", "cid", id="a-partner-who-stands"),
    pytest.param({"ada": "w", "bea": "e"}, None, None, "ada", "bea", id="a-partner-at-the-same-table"),
    pytest.param({"cid": "fw"}, {"ada": (3, 6)}, None, "ada", "cid", id="already-standing-at-that-table"),
    pytest.param({"ada": "w", "cid": "fw"}, None, pressed_cid, "ada", "cid", id="a-partner-pressed-by-a-need"),
    pytest.param({"ada": "w", "cid": "fw", "dan": "fe"}, None, full_scene, "ada", "cid", id="a-full-conversation"),
    pytest.param({"ada": "w", "bea": "e", "cid": "fw"}, None, ada_talking_to_bea, "ada", "cid",
                 id="already-in-a-conversation"),
    pytest.param({"cid": "fw", "ada": "w"}, {"bea": (3, 6), "dan": (4, 6)}, None, "ada", "cid",
                 id="every-spot-at-that-table-is-taken"),
])
def test_an_approach_is_refused(seated: dict[str, str], standing: dict[str, tuple[int, int]] | None,
                                prepare: Callable[[dict[str, Any]], None] | None, who: str, target: Any) -> None:
    world = evening(seated, standing)
    if prepare:
        prepare(world)
    assert not approach(world, who, target)["accepted"]


def test_an_approach_fails_when_the_partner_leaves_before_arrival() -> None:
    world = evening({"ada": "w", "cid": "fw"})
    assert approach(world)["accepted"]
    assert start_action(world, "cid", command("take_beer", "tap"))["accepted"]
    advance(world, 8)
    assert (conversation_of(world, "ada"), actor(world, "ada")["action"]) == (None, None)
    assert any(event["type"] == "action_failed" for event in actor(world, "ada")["memory"])


def sees(world: dict[str, Any], who: str = "ada") -> dict[str, Any]:
    """A guest's observation as a decision gets it."""
    return {**observe_actor(world, who), "people": observe_people(world, who)}


def approaches(observation: dict[str, Any]) -> list[str]:
    """The IDs of the walks over a guest is offered, whichever family holds them."""
    options = build_candidates(observation)
    return [item["id"] for option in options for item in option.get("members", [option])
            if item["verb"] == "approach"]


@pytest.mark.parametrize("seated, standing, expected", [
    pytest.param({"ada": "w", "cid": "fw", "dan": "fe"}, None, ["approach:cid"],
                 id="one-for-each-other-table-by-its-first-guest"),
    pytest.param({"ada": "w", "bea": "e"}, None, [], id="only-tablemates"),
    pytest.param({"ada": "w"}, None, [], id="nobody-else-sits"),
    pytest.param({"cid": "fw"}, {"ada": (3, 6)}, [], id="already-at-that-table"),
    pytest.param({"cid": "fw", "ada": "w"}, {"bea": (3, 6), "dan": (4, 6)}, [],
                 id="nobody-can-stand-at-that-table-for-the-others-there"),
    pytest.param({"cid": "fw", "ada": "w"}, {"bea": (3, 6)}, ["approach:cid"], id="one-spot-is-still-free"),
    pytest.param({"cid": "fw", "bea": "e"}, {"ada": (8, 6)}, ["approach:bea", "approach:cid"],
                 id="a-guest-on-their-feet-may-walk-over-too"),
])
def test_a_guest_may_walk_over_to_someone_at_another_table(
        seated: dict[str, str], standing: dict[str, tuple[int, int]] | None, expected: list[str]) -> None:
    assert approaches(sees(evening(seated, standing))) == expected


def test_the_option_says_where_and_with_whom() -> None:
    observation = sees(evening({"ada": "w", "cid": "fw", "dan": "fe"}))
    text = brief(observation, build_candidates(observation))["options"]["approach:cid"]
    assert ("Far table" in text, "Cid" in text, "standing beside it" in text, "Dan" in text) == (True, True, True, True)


def lonely(world_social: float, opinion: float = 0.0) -> float:
    """Ada's local score for walking over to Cid, with the given wish for company and opinion of him."""
    world = evening({"ada": "w", "cid": "fw"}, social=world_social)
    observation = sees(world)
    observation["actor"]["relations"] = {"cid": {"name": "Cid", "opinion": opinion, "familiarity": "acquaintance"}}
    return local_scores(observation, [{"id": "approach:cid", "verb": "approach", "target_id": "cid"}])["approach:cid"]


def test_the_lonelier_walk_over_more_readily() -> None:
    assert lonely(90) > lonely(10)


def test_nobody_walks_over_to_someone_they_dislike() -> None:
    assert lonely(90, opinion=-50) < lonely(90)


def feverish_cid(world: dict[str, Any]) -> None:
    """Cid came in unwell: the fever leaves him as tired as a guest ready for bed."""
    cid = actor(world, "cid")
    cid["ailing"], cid["needs"]["fatigue"] = True, 80.0


@pytest.mark.parametrize("prepare, offered", [
    pytest.param(feverish_cid, ["approach:cid"], id="a-feverish-guest-has-nothing-pressing"),
    pytest.param(pressed_cid, [], id="a-guest-who-needs-the-wc-has"),
])
def test_only_a_real_need_keeps_a_guest_from_being_walked_over_to(
        prepare: Callable[[dict[str, Any]], None], offered: list[str]) -> None:
    world = evening({"ada": "w", "cid": "fw"})
    prepare(world)
    assert (approaches(sees(world)), approach(world)["accepted"]) == (offered, bool(offered))
