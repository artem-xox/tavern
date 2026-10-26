"""Walking over for a word: a guest goes to a spot at another table and talks with those seated there."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.social.scenes import conversation_of, side_by_side
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


def dan_walks(world: dict[str, Any]) -> None:
    """Dan is on his way somewhere."""
    actor(world, "dan").update(status="walking", path=[[9, 5]])


def dan_is_blocked_mid_route(world: dict[str, Any]) -> None:
    """Dan waits on a blocked route, with steps left to take."""
    actor(world, "dan").update(status="waiting", path=[[9, 5]])


@pytest.mark.parametrize("seated, standing, prepare, expected", [
    pytest.param({"cid": "fw"}, None, None, (False, "far"), id="a-seated-guest-is-at-their-table"),
    pytest.param({}, None, None, (False, None), id="an-idle-stander-in-the-open"),
    pytest.param({}, {"dan": (3, 6)}, None, (False, "far"), id="a-stander-on-a-tables-spot"),
    pytest.param({}, None, dan_walks, (True, None), id="a-walker"),
    pytest.param({}, None, dan_is_blocked_mid_route, (True, None), id="a-guest-blocked-mid-route"),
])
def test_people_show_who_is_on_the_move_and_which_table_they_are_at(
        seated: dict[str, str], standing: dict[str, tuple[int, int]] | None,
        prepare: Callable[[dict[str, Any]], None] | None, expected: tuple[bool, str | None]) -> None:
    world = evening(seated, standing)
    if prepare:
        prepare(world)
    who = "cid" if "cid" in seated else "dan"
    seen = next(item for item in observe_people(world, "ada") if item["id"] == who)
    assert (seen["walking"], seen["at_table"]) == expected


def surrounded(world: dict[str, Any]) -> None:
    """Walls close in every cell round Dan within reach of him."""
    world["map"]["blocked"].extend([x, y] for x in range(7, 12) for y in range(4, 8) if (x, y) != (9, 6))


@pytest.mark.parametrize("standing, prepare, reason", [
    pytest.param(None, dan_walks, "Dan is on the move", id="someone-on-the-move"),
    pytest.param({"ada": (8, 6)}, None, "Dan is right beside them", id="someone-already-within-reach"),
])
def test_walking_up_to_someone_standing_is_refused_with_a_reason(
        standing: dict[str, tuple[int, int]] | None, prepare: Callable[[dict[str, Any]], None] | None,
        reason: str) -> None:
    world = evening({}, standing)
    if prepare:
        prepare(world)
    assert reason in str(approach(world, "ada", "dan")["reason"])


def test_walking_up_to_someone_no_free_cell_reaches_is_refused() -> None:
    world = evening({})
    surrounded(world)
    assert not approach(world, "ada", "dan")["accepted"]


def test_an_approach_to_someone_standing_ends_in_a_standing_scene_beside_them() -> None:
    world = evening({})
    assert approach(world, "ada", "dan")["accepted"]
    advance(world, 12)
    scene, ada, dan = conversation_of(world, "ada"), actor(world, "ada"), actor(world, "dan")
    assert (scene["participants"], scene["table_id"], ada["action"]["verb"], side_by_side(world, ada, dan)) == (
        ["ada", "dan"], None, "approach", True)


def test_an_approach_to_someone_in_a_standing_conversation_joins_it() -> None:
    world = evening({}, {"bea": (9, 5)})
    assert start_action(world, "dan", command("talk", "bea"))["accepted"]
    assert approach(world, "ada", "dan")["accepted"]
    advance(world, 12)
    assert conversation_of(world, "ada")["participants"] == ["dan", "bea", "ada"]


def test_an_approach_to_someone_standing_fails_when_they_walk_off() -> None:
    world = evening({})
    assert approach(world, "ada", "dan")["accepted"]
    assert start_action(world, "dan", command("take_beer", "tap"))["accepted"]
    advance(world, 12)
    assert (conversation_of(world, "ada"), actor(world, "ada")["action"]) == (None, None)
    assert any(event["type"] == "action_failed" for event in actor(world, "ada")["memory"])


def dan_plays_darts(world: dict[str, Any]) -> None:
    """Dan throws darts at the board."""
    assert start_action(world, "dan", command("play_darts", "darts"))["accepted"]
    advance(world, 6)


def dan_waits_a_moment(world: dict[str, Any]) -> None:
    """Dan stands where he is for a moment."""
    assert start_action(world, "dan", command("wait"))["accepted"]


def dan_chats_with_bea(world: dict[str, Any]) -> None:
    """Dan and Bea, side by side in the open, are in a conversation."""
    assert start_action(world, "dan", command("talk", "bea"))["accepted"]


def dan_fetches_a_beer(world: dict[str, Any]) -> None:
    """Dan walks to the tap."""
    assert start_action(world, "dan", command("take_beer", "tap"))["accepted"]
    advance(world, 0.5)


@pytest.mark.parametrize("standing, prepare, expected", [
    pytest.param(None, dan_plays_darts, ["approach:dan"], id="someone-busy-at-the-darts"),
    pytest.param(None, None, [], id="someone-standing-idle"),
    pytest.param(None, dan_fetches_a_beer, [], id="someone-on-the-move"),
    pytest.param({"dan": (3, 6)}, dan_waits_a_moment, [], id="someone-at-a-tables-spot"),
    pytest.param({"bea": (9, 5)}, dan_chats_with_bea, ["approach:bea"], id="two-in-one-standing-conversation-by-the-first"),
])
def test_a_guest_may_walk_up_to_someone_standing_who_is_busy_or_in_company(
        standing: dict[str, tuple[int, int]] | None, prepare: Callable[[dict[str, Any]], None] | None,
        expected: list[str]) -> None:
    world = evening({}, standing)
    if prepare:
        prepare(world)
    assert approaches(sees(world)) == expected


@pytest.mark.parametrize("seen_of_dan", [
    pytest.param({"asleep": True, "available": False}, id="a-sleeper"),
    pytest.param({"post": "Bar"}, id="staff"),
    pytest.param({"fighting": "bea", "available": False}, id="a-fighter"),
])
def test_nobody_walks_up_to_a_sleeper_staff_or_a_fighter_standing_busy(seen_of_dan: dict[str, Any]) -> None:
    world = evening({})
    dan_plays_darts(world)
    observation = sees(world)
    next(item for item in observation["people"] if item["id"] == "dan").update(seen_of_dan)
    assert approaches(observation) == []


def test_the_option_says_how_far_and_what_they_are_doing() -> None:
    world = evening({})
    dan_plays_darts(world)
    observation = sees(world)
    text = brief(observation, build_candidates(observation))["options"]["approach:dan"]
    assert ("Dan" in text, "on their feet" in text, "playing darts" in text) == (True, True, True)


def stander_score(cell: tuple[int, int]) -> float:
    """Ada's local score for walking up to Dan, who stands on a cell."""
    world = evening({}, {"dan": cell}, social=90.0)
    return local_scores(sees(world), [{"id": "approach:dan", "verb": "approach", "target_id": "dan"}])["approach:dan"]


def test_the_farther_a_stander_the_less_readily_a_guest_walks_up() -> None:
    assert stander_score((7, 0)) > stander_score((11, 7))
