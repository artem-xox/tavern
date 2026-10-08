"""Whose table is whose, and who is welcome at it."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.memory import record_event
from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.intentions import SALIENT_THOUGHTS
from tavern.mind.options import option_text
from tavern.social.hostility import HOSTILE_CAUSES
from tavern.social.tables import liked, table_hosts, welcome
from tavern.social.thoughts import THOUGHTS, opinion_of
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
    world = create_world({**spotted_hall(), "table_manners": True}, 4)
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


def sit_down(world: dict[str, Any], who: str, chair: str) -> None:
    """A guest takes a chair and settles."""
    assert start_action(world, who, command("sit", chair))["accepted"]
    advance(world, 10)


def upset(world: dict[str, Any], newcomer: str) -> list[str]:
    """The guests who took it ill that a guest sat down at their table."""
    name = actor(world, newcomer)["name"]
    return [item["id"] for item in world["actors"] if any(
        e["type"] == "table_intruded" and e["message"].startswith(name) for e in item["memory"])]


def ada_calls_far_east_hers(world: dict[str, Any]) -> None:
    """The far table's east chair is Ada's own seat, though she sits elsewhere."""
    actor(world, "ada").update(favorite_seat_id="fe")


def cid_owns_far_west(world: dict[str, Any]) -> None:
    """Cid is away, but the far table's west chair is his own."""
    actor(world, "cid").update(seat_id=None, favorite_seat_id="fw", x=9, y=7)


def bea_is_a_friend_of_cid(world: dict[str, Any]) -> None:
    """Bea counts Cid a friend."""
    actor(world, "bea")["relations"]["cid"] = {"name": "Cid", "opinion": 0.0, "familiarity": "friend"}


@pytest.mark.parametrize("seats, prepare, newcomer, chair, expected", [
    pytest.param({"cid": "fw"}, None, "ada", "fe", ["cid"], id="a-stranger-sits-down-at-a-hosted-table"),
    pytest.param({"cid": "fw"}, friend, "ada", "fe", [], id="a-friend"),
    pytest.param({"cid": "fw"}, fond(10.0), "ada", "fe", [], id="someone-liked"),
    pytest.param({"cid": "fw"}, promised, "ada", "fe", [], id="a-promise-kept"),
    pytest.param({"cid": "fw"}, invited("cid", "ada"), "ada", "fe", [], id="asked-over"),
    pytest.param({"cid": "fw"}, ada_calls_far_east_hers, "ada", "fe", [], id="returning-to-ones-own-seat"),
    pytest.param({}, None, "ada", "fe", [], id="an-empty-table"),
    pytest.param({}, cid_owns_far_west, "ada", "fw", [], id="the-owners-own-chair-is-a-wrong-of-its-own"),
    pytest.param({"bea": "e", "dan": "n"}, bea_is_a_friend_of_cid, "cid", "w", ["dan"],
                id="only-the-hosts-who-do-not-welcome-them"),
])
def test_sitting_down_at_a_table_uninvited_upsets_its_hosts(
        seats: dict[str, str], prepare: Callable[[dict[str, Any]], None] | None, newcomer: str, chair: str,
        expected: list[str]) -> None:
    world = hall_of(**seats)
    if prepare:
        prepare(world)
    sit_down(world, newcomer, chair)
    assert upset(world, newcomer) == expected
    assert sum(e["type"] == "sat_uninvited" and e["message"].startswith(actor(world, newcomer)["name"])
               for e in actor(world, newcomer)["memory"]) == len(expected)


def test_an_intrusion_is_told_remembered_and_felt() -> None:
    world = hall_of(cid="fw")
    sit_down(world, "ada", "fe")
    cid, ada = actor(world, "cid"), actor(world, "ada")
    told = "Ada sat down at Cid's table uninvited (Far table)"
    assert [e["message"] for e in cid["memory"] if e["type"] == "table_intruded"] == [told]
    assert [e["message"] for e in ada["memory"] if e["type"] == "sat_uninvited"] == [told]
    assert opinion_of(cid, "ada", world["time"]) == pytest.approx(THOUGHTS["table_intruded"].opinion)
    assert opinion_of(ada, "cid", world["time"]) == 0.0


def test_the_host_shows_it_and_nobody_is_called_a_fighter_for_it() -> None:
    world = hall_of(cid="fw")
    sit_down(world, "ada", "fe")
    assert "table_intruded" in SALIENT_THOUGHTS and "table_intruded" not in HOSTILE_CAUSES
    record_event(world, actor(world, "cid"), "table_intruded", "x")
    assert actor(world, "cid")["emote"]["kind"] == "angry"


def test_an_intrusion_survives_save_and_load(tmp_path: Path) -> None:
    world = hall_of(cid="fw")
    sit_down(world, "ada", "fe")
    save_world(world, tmp_path / "save.json")
    loaded = load_world(tmp_path / "save.json")
    assert [t["kind"] for t in actor(loaded, "cid")["thoughts"]] == ["table_intruded"]


def test_the_shipped_inn_keeps_table_manners() -> None:
    layout = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
    assert create_world(layout)["rules"]["manners"] == {"table_intrusion": True}


def test_a_hall_that_does_not_ask_for_table_manners_has_none() -> None:
    world = create_world(spotted_hall(), 4)
    assert_cid_first = start_action(world, "cid", command("sit", "fw"))["accepted"]
    advance(world, 10)
    sit_down(world, "ada", "fe")
    assert (world["rules"]["manners"], assert_cid_first, upset(world, "ada")) == ({"table_intrusion": False}, True, [])


@pytest.mark.parametrize("setting", [
    pytest.param("yes", id="a-word"),
    pytest.param(1, id="a-number"),
    pytest.param(None, id="null"),
])
def test_table_manners_are_on_or_off(setting: Any) -> None:
    with pytest.raises(ValueError, match="table_manners"):
        create_world({**spotted_hall(), "table_manners": setting}, 4)


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda rules: rules.pop("manners"), id="missing"),
    pytest.param(lambda rules: rules.update(manners={}), id="empty"),
    pytest.param(lambda rules: rules.update(manners={"table_intrusion": "yes"}), id="not-a-boolean"),
    pytest.param(lambda rules: rules.update(manners={"table_intrusion": True, "grace": 1}), id="unknown-rule"),
])
def test_corrupt_manners_are_rejected_on_load(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = hall_of()
    corrupt(world["rules"])
    save_world(world, tmp_path / "save.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "save.json")
