"""Invitations end to end: an invite, the invitee's answer, and the game setting both in motion."""

import asyncio
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import choose_action
from tavern.mind.briefing import brief
from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import observe_actor, observe_people
from tavern.social.thoughts import THOUGHTS, opinion_of
from social_hall import actor, advance, by_the_fire, know, say, scene_of, seated_talk


def invite(world: dict[str, Any], kind: str, answer: str = "accept") -> None:
    """Ada invites the other guest in her scene, who answers."""
    say(world, "invite", "Shall we?", invitation=kind)
    say(world, answer, "Gladly." if answer == "accept" else "Not tonight.")


def verbs(world: dict[str, Any], *actor_ids: str) -> list[str | None]:
    """What each guest is doing."""
    return [(actor(world, item)["action"] or {}).get("verb") for item in actor_ids]


def test_joining_a_table_seats_the_invitee_at_the_inviters_table() -> None:
    world = by_the_fire()
    invite(world, "join_table")
    advance(world, 8)
    seat = actor(world, "dan")["seat_id"]
    assert (seat, next(item for item in world["map"]["objects"] if item["id"] == seat)["table_id"]) == ("n", "near")


def test_darts_together_sends_both_to_the_board() -> None:
    world = seated_talk()
    know(world, "ada", "darts")
    invite(world, "darts_together")
    assert verbs(world, "ada", "bea") == ["play_darts", "play_darts"]


def test_a_bought_drink_ends_in_the_invitees_hand() -> None:
    world = seated_talk()
    know(world, "ada", "tap")
    invite(world, "buy_drink")
    advance(world, 12)
    ada, bea = actor(world, "ada"), actor(world, "bea")
    assert (ada["inventory"]["beer"], bea["inventory"]["beer"], world["invitations"]) == (0, 1, [])
    assert opinion_of(bea, "ada", world["time"]) == pytest.approx(THOUGHTS["treated"].opinion)


def test_leaving_together_walks_both_out_one_after_the_other() -> None:
    world = seated_talk()
    know(world, "ada", "door")
    invite(world, "leave_together")
    advance(world, 20)
    departures = [event["actor_id"] for event in world["events"] if event["type"] == "departure"]
    assert (departures, world["invitations"]) == (["ada", "bea"], [])


def test_a_declined_invitation_changes_nothing() -> None:
    world = seated_talk()
    know(world, "ada", "darts")
    before = verbs(world, "ada", "bea")
    invite(world, "darts_together", answer="decline")
    assert (verbs(world, "ada", "bea"), scene_of(world)["invitation"], world["invitations"]) == (before, None, [])


def test_pending_invitation_lapses_when_the_inviter_leaves_the_scene() -> None:
    world = seated_talk(cid_joins=True)
    know(world, "ada", "darts")
    say(world, "invite", "Darts, Bea?", addressee="bea", invitation="darts_together")
    say(world, "leave_conversation", "I'll be off.")  # Bea, addressed, says goodbye: the invitation lapses
    assert scene_of(world)["invitation"] is None


def situation(world: dict[str, Any], actor_id: str) -> str:
    """A guest's briefing, as Jev reads it."""
    return brief({**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}, [])["situation"]


def asked(world: dict[str, Any]) -> None:
    """Ada invites Bea to play darts; Bea has yet to answer."""
    say(world, "invite", "Darts?", invitation="darts_together")


def agreed_to_leave(world: dict[str, Any]) -> None:
    """Bea agreed to walk home with Ada, who holds the door."""
    invite(world, "leave_together")


@pytest.mark.parametrize("prepare, actor_id, sentence", [
    pytest.param(asked, "bea", "Ada invited them to play darts together; they have yet to answer.",
                 id="invitee-of-a-pending-invitation"),
    pytest.param(asked, "ada", "They invited Bea to play darts together and await an answer.",
                 id="inviter-of-a-pending-invitation"),
    pytest.param(agreed_to_leave, "bea", "They agreed with Ada to walk home together.", id="follower"),
    pytest.param(lambda world: None, "bea", "", id="no-invitation"),
])
def test_briefing_tells_invitations(prepare: Any, actor_id: str, sentence: str) -> None:
    world = seated_talk()
    know(world, "ada", "darts", "door")
    prepare(world)
    told = situation(world, actor_id)
    assert (sentence in told, "invit" in told or "agreed with" in told) == (True, bool(sentence))


def test_local_policy_follows_the_inviter_home() -> None:
    world = seated_talk()
    know(world, "ada", "door")
    know(world, "bea", "door")
    agreed_to_leave(world)
    seen = {**observe_actor(world, "bea"), "people": observe_people(world, "bea")}
    choice = asyncio.run(choose_action(seen, {"typesafe_api_key": None, "temperature": 0.0}, Random(0)))
    assert choice["action"]["verb"] == "leave"


def test_pending_and_running_invitations_survive_save_and_load(tmp_path: Path) -> None:
    world = seated_talk()
    know(world, "ada", "door", "darts")
    say(world, "invite", "Shall we go?", invitation="leave_together")
    save_world(world, tmp_path / "save.json")
    assert load_world(tmp_path / "save.json")["conversations"][0]["invitation"] == {
        "kind": "leave_together", "from": "ada", "to": "bea"}


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(invitations=None), id="malformed-list"),
    pytest.param(lambda world: world["invitations"].append({"kind": "dance", "from": "ada", "to": "bea",
                                                            "stage": "accepted", "held": 0}), id="unknown-kind"),
    pytest.param(lambda world: world["conversations"][0].update(invitation={"kind": "buy_drink"}),
                 id="pending-without-guests"),
    pytest.param(lambda world: world["conversations"][0].update(invitation={
        "kind": "buy_drink", "from": "ada", "to": "zed"}), id="pending-to-a-stranger-of-the-hall"),
])
def test_corrupt_invitations_are_rejected(tmp_path: Path, corrupt: Any) -> None:
    world = seated_talk()
    advance(world, 1)
    corrupt(world)
    save_world(world, tmp_path / "save.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "save.json")
