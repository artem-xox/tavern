"""Whose table is whose, and who is welcome at it."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.options import option_text
from tavern.social.tables import liked, table_hosts, welcome
from social_hall import actor, advance, command, know, spotted_hall


def relation(opinion: float = 0.0, familiarity: str = "acquaintance") -> dict[str, Any]:
    """Describe what Ada thinks of Bea."""
    return {"name": "Bea", "opinion": opinion, "familiarity": familiarity}


@pytest.mark.parametrize("actor, expected", [
    pytest.param({}, False, id="no-relations-at-all"),
    pytest.param({"relations": {"bea": relation(0.0, "stranger")}}, False, id="a-stranger"),
    pytest.param({"relations": {"bea": relation(9.0)}}, False, id="just-below-liked"),
    pytest.param({"relations": {"bea": relation(10.0)}}, True, id="liked"),
    pytest.param({"relations": {"bea": relation(0.0, "friend")}}, True, id="a-friend-of-no-opinion"),
    pytest.param({"relations": {"bea": relation(-40.0, "friend")}}, True, id="an-old-friend-is-still-a-friend"),
    pytest.param({"relations": {"bea": relation(5.0)},
                  "thoughts": [{"kind": "chat", "about": "bea", "text": "x", "mood": 3.0, "opinion": 6.0,
                                "expires_at": 100.0, "source_event": "chat"}]}, True,
                 id="a-pleasant-chat-tips-it"),
    pytest.param({"relations": {"cid": relation(50.0)}}, False, id="liking-someone-else"),
])
def test_a_guest_likes_someone_they_think_well_of_or_count_a_friend(actor: dict[str, Any], expected: bool) -> None:
    assert liked(actor, "bea", 50.0) is expected


def hall_of(**seats: str) -> dict[str, Any]:
    """Seat the named guests (Ada, Bea, Cid, Dan) on the given chairs of `spotted_hall`, let them settle and let
    everyone know both tables and their chairs."""
    world = create_world(spotted_hall(), 4)
    for name, chair in seats.items():
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 10)
    for item in world["actors"]:
        know(world, item["id"], "near", "w", "e", "n", "far", "fw", "fe")
    return world


def cid_away(world: dict[str, Any]) -> None:
    """Cid is on his feet, but the far table's west chair is his own."""
    actor(world, "cid").update(favorite_seat_id="fw")


def cid_on_duty(world: dict[str, Any]) -> None:
    """Cid works behind a bar."""
    actor(world, "cid")["post"] = "bar"


def ids(people: list[dict[str, Any]]) -> list[str]:
    """The IDs of some guests."""
    return [item["id"] for item in people]


@pytest.mark.parametrize("seats, prepare, newcomer, expected", [
    pytest.param({}, None, "ada", [], id="an-empty-table"),
    pytest.param({"cid": "fw"}, None, "ada", ["cid"], id="a-seated-host"),
    pytest.param({}, cid_away, "ada", ["cid"], id="an-absent-owner-of-a-chair"),
    pytest.param({"cid": "fw"}, cid_on_duty, "ada", [], id="staff-hold-no-table"),
    pytest.param({"cid": "fw"}, None, "cid", [], id="the-newcomer-is-no-host"),
    pytest.param({"cid": "fw", "dan": "fe"}, None, "ada", ["cid", "dan"], id="two-hosts-in-the-order-of-the-hall"),
    pytest.param({"cid": "fw", "dan": "fe"}, None, "dan", ["cid"], id="the-other-of-two"),
    pytest.param({"ada": "w"}, None, "ada", [], id="nobody-else-at-the-newcomers-table"),
])
def test_the_hosts_of_a_table_are_those_who_sit_at_it_or_own_a_chair_there(
        seats: dict[str, str], prepare: Callable[[dict[str, Any]], None] | None, newcomer: str,
        expected: list[str]) -> None:
    world = hall_of(**seats)
    if prepare:
        prepare(world)
    assert ids(table_hosts(world, "far", actor(world, newcomer))) == expected


def friend(world: dict[str, Any]) -> None:
    """Cid counts Ada a friend."""
    actor(world, "cid")["relations"]["ada"] = {"name": "Ada", "opinion": 0.0, "familiarity": "friend"}


def fond(opinion: float) -> Callable[[dict[str, Any]], None]:
    """Cid thinks the given amount of Ada."""
    return lambda world: actor(world, "cid")["relations"].update(
        ada={"name": "Ada", "opinion": opinion, "familiarity": "acquaintance"})


def promised(world: dict[str, Any]) -> None:
    """Ada promised Cid to come and sit with him."""
    world["commitments"].append({"kind": "sit_with", "from": "ada", "to": "cid", "made_at": 0.0, "by": 90.0})


def invited(who: str, whom: str) -> Callable[[dict[str, Any]], None]:
    """An errand between two guests is under way to the far table."""
    return lambda world: world["invitations"].append(
        {"kind": "join_table", "from": who, "to": whom, "stage": "seating", "held": 0, "table": "far"})


def cid_promised(world: dict[str, Any]) -> None:
    """Cid promised Ada to come and sit with her, which is no leave for her to sit with him."""
    world["commitments"].append({"kind": "sit_with", "from": "cid", "to": "ada", "made_at": 0.0, "by": 90.0})


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda world: None, False, id="a-stranger"),
    pytest.param(friend, True, id="a-friend"),
    pytest.param(fond(10.0), True, id="liked"),
    pytest.param(fond(9.0), False, id="not-quite-liked"),
    pytest.param(promised, True, id="a-promise-to-come-and-sit"),
    pytest.param(cid_promised, False, id="the-hosts-own-promise-is-no-leave"),
    pytest.param(invited("cid", "ada"), True, id="asked-over-by-the-host"),
    pytest.param(invited("ada", "cid"), True, id="the-host-was-asked-over-by-the-guest"),
    pytest.param(invited("bea", "dan"), False, id="an-errand-of-two-others"),
])
def test_a_host_welcomes_a_guest_they_like_or_who_was_asked(prepare: Callable[[dict[str, Any]], None],
                                                           expected: bool) -> None:
    world = hall_of(cid="fw")
    prepare(world)
    assert welcome(world, actor(world, "cid"), actor(world, "ada")) is expected


def test_the_hall_shows_whose_chair_and_table_is_whose() -> None:
    world = hall_of(ada="w", bea="e", cid="fw")
    seen = {item["id"]: item for item in observe_actor(world, "dan")["objects"]}
    assert (seen["fw"]["owner"], seen["fe"]["owner"], seen["far"]["hosts"], seen["near"]["hosts"]) == (
        {"id": "cid", "name": "Cid"}, None, [{"id": "cid", "name": "Cid"}],
        [{"id": "ada", "name": "Ada"}, {"id": "bea", "name": "Bea"}])


def test_ones_own_table_is_nobody_elses() -> None:
    world = hall_of(ada="w", bea="e")
    seen = {item["id"]: item for item in observe_actor(world, "ada")["objects"]}
    assert (seen["w"]["owner"], seen["e"]["owner"], seen["near"]["hosts"]) == (None, {"id": "bea", "name": "Bea"}, [])


def look_from(world: dict[str, Any], who: str) -> dict[str, Any]:
    """A guest's observation as a decision gets it."""
    return {**observe_actor(world, who), "people": observe_people(world, who)}


def briefed(world: dict[str, Any], who: str = "ada") -> dict[str, Any]:
    """What the briefing tells one guest."""
    observation = look_from(world, who)
    return brief(observation, build_candidates(observation))


def test_the_briefing_names_the_table_a_guest_holds_and_warns_against_barging_in() -> None:
    situation = briefed(hall_of(ada="w", cid="fw"))["situation"]
    assert ("Far table (Cid's table" in situation, "without being asked" in situation) == (True, True)


def test_the_briefing_says_when_the_hosts_are_away() -> None:
    world = hall_of(ada="w")
    cid_away(world)
    assert "Cid's table, though Cid is away" in briefed(world)["situation"]


def test_the_briefing_has_no_warning_while_no_table_is_held_by_others() -> None:
    assert "without being asked" not in briefed(hall_of(ada="w"))["situation"]


def ada_gets_on_with_cid(world: dict[str, Any]) -> None:
    """Ada counts Cid a friend."""
    actor(world, "ada")["relations"]["cid"] = {"name": "Cid", "opinion": 0.0, "familiarity": "friend"}


def cid_gone_to_the_fire(world: dict[str, Any]) -> None:
    """Cid got up and left; the far table's west chair is still his own."""
    actor(world, "cid").update(seat_id=None, x=9, y=7)


@pytest.mark.parametrize("prepare, chair, present, absent", [
    pytest.param(None, "fe", ["Far table", "Cid's table", "uninvited"], [], id="a-free-chair-at-a-strangers-table"),
    pytest.param(ada_gets_on_with_cid, "fe", ["Cid's table", "get on with Cid"], ["uninvited"],
                 id="a-free-chair-at-a-friends-table"),
    pytest.param(cid_gone_to_the_fire, "fw", ["Cid's own seat", "wrong Cid", "Cid is away"], [],
                 id="a-chair-someone-calls-their-own"),
])
def test_a_chair_is_told_with_whose_it_is(prepare: Callable[[dict[str, Any]], None] | None, chair: str,
                                          present: list[str], absent: list[str]) -> None:
    world = hall_of(ada="w", cid="fw")
    if prepare:
        prepare(world)
    text = option_text(look_from(world, "ada"), {"id": f"sit:{chair}", "verb": "sit", "target_id": chair})
    assert [phrase in text for phrase in present + absent] == [True] * len(present) + [False] * len(absent)
