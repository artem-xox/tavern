"""A guest whose invitation was just turned down does not ask the same person again at once, and knows why."""

from typing import Any

import pytest

from social_hall import actor, advance, know, say, seated_talk, scene_of
from tavern.hall.world import observe_actor, start_action
from tavern.mind.briefing import brief
from tavern.social.aims import offered_aims
from tavern.social.invitations import offered_kinds
from tavern.social.scenes import end_conversation, leave_conversation

TALK_TO_BEA = {"id": "talk:bea", "verb": "talk", "target_id": "bea"}


def turned_down(later: float) -> dict[str, Any]:
    """Bea turns down Ada's darts; the scene ends, `later` seconds pass, and Ada sits down to talk to Bea again."""
    world = seated_talk()
    know(world, "ada", "darts", "tap")
    say(world, "invite", "Darts?", invitation="darts_together")
    say(world, "decline", "Not tonight.")
    end_conversation(world, scene_of(world), pleasant=True)
    advance(world, later)
    return world


@pytest.mark.parametrize("later, invites", [
    pytest.param(1.0, False, id="just-turned-down"),
    pytest.param(200.0, True, id="after-a-while"),
])
def test_the_inviter_means_no_invitation_to_whoever_just_turned_them_down(later: float, invites: bool) -> None:
    aims = offered_aims(observe_actor(turned_down(later), "ada"), TALK_TO_BEA)
    assert any(aim.startswith("invite:") for aim in aims) is invites


@pytest.mark.parametrize("later, offered", [
    pytest.param(1.0, False, id="just-turned-down"),
    pytest.param(200.0, True, id="after-a-while"),
])
def test_the_inviter_may_not_invite_them_in_the_next_scene_either(later: float, offered: bool) -> None:
    world = turned_down(later)
    assert start_action(world, "ada", TALK_TO_BEA)["accepted"]
    kinds = offered_kinds(world, scene_of(world), actor(world, "ada"))
    assert ("darts_together" in kinds) is offered


def test_the_inviter_has_it_on_their_mind() -> None:
    view = observe_actor(turned_down(1.0), "ada")
    assert "Bea turned down my invitation to play darts together" in brief(view, [TALK_TO_BEA])["situation"]


def left_hanging(walks_off: str, later: float) -> dict[str, Any]:
    """Ada asks Bea to darts; before Bea answers, `walks_off` leaves the talk (or, for "nobody", the talk just ends),
    and `later` seconds pass."""
    world = seated_talk()
    know(world, "ada", "darts", "tap")
    say(world, "invite", "Darts?", invitation="darts_together")
    if walks_off == "nobody":
        end_conversation(world, scene_of(world), pleasant=True)
    else:
        leave_conversation(world, actor(world, walks_off))
    advance(world, later)
    return world


@pytest.mark.parametrize("walks_off, later, offered", [
    # Live seed 5 (2026-10-25): of 13 invitations 11 were never answered, and the same pairs were asked again and again.
    pytest.param("bea", 1.0, False, id="the-invitee-walked-off"),
    pytest.param("ada", 1.0, False, id="the-inviter-walked-off"),
    pytest.param("nobody", 1.0, False, id="the-talk-ended-first"),
    pytest.param("bea", 200.0, True, id="after-a-while"),
])
def test_an_invitation_left_unanswered_is_not_made_again_at_once(walks_off: str, later: float, offered: bool) -> None:
    world = left_hanging(walks_off, later)
    assert start_action(world, "ada", TALK_TO_BEA)["accepted"]
    kinds = offered_kinds(world, scene_of(world), actor(world, "ada"))
    assert ("darts_together" in kinds) is offered


def test_the_inviter_has_the_unanswered_invitation_on_their_mind() -> None:
    view = observe_actor(left_hanging("bea", 1.0), "ada")
    assert "Bea never answered my invitation" in brief(view, [TALK_TO_BEA])["situation"]
