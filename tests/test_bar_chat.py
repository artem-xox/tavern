"""Leaning on the bar: guests stand at the counter and talk with the barkeep, who works the whole time."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.hall.world import start_action
from tavern.mind.agents import build_candidates
from tavern.mind.haiku_turns import turn_content
from tavern.mind.scripted import scripted_turn
from tavern.social.invitations import offered_kinds
from tavern.social.scenes import conversation_of, join_conversation, side_by_side, start_conversation
from tavern.social.turns import check_turn, turn_view
from staff_hall import HOB, advance, hob_of, opened, person, place, sees

SPOTS = [(3, 3), (4, 3), (5, 3)]
STAND = {"id": "stand_at_bar:bar", "verb": "stand_at_bar", "target_id": "bar"}
TALK = {"id": "talk:hob", "verb": "talk", "target_id": "hob"}


def idle(world: dict[str, Any]) -> None:
    """Leave the world as it is."""


def seated(world: dict[str, Any]) -> None:
    """Ada sits on a chair."""
    person(world, "ada")["seat_id"] = "chair-1"


def walking(world: dict[str, Any]) -> None:
    """Ada is on her way somewhere."""
    person(world, "ada")["status"] = "walking"


@pytest.mark.parametrize("first, second, cells, change, expected", [
    pytest.param("ada", "hob", {"ada": (3, 3)}, idle, True, id="guest-on-a-spot-and-the-barkeep"),
    pytest.param("ada", "bea", {"ada": (3, 3), "bea": (5, 3)}, idle, True, id="two-guests-on-spots"),
    pytest.param("ada", "hob", {"ada": (6, 3)}, idle, False, id="guest-on-the-taps-spot"),
    pytest.param("ada", "hob", {"ada": (2, 3)}, idle, False, id="guest-beside-the-bar-but-off-its-spots"),
    pytest.param("ada", "bea", {"ada": (3, 3), "bea": (12, 6)}, idle, False, id="one-guest-away-from-the-bar"),
    pytest.param("ada", "hob", {"ada": (3, 3)}, walking, False, id="guest-still-walking"),
    pytest.param("ada", "hob", {"ada": (3, 3)}, seated, False, id="guest-seated"),
])
def test_two_people_at_the_same_bar_are_side_by_side(first: str, second: str, cells: dict[str, tuple[int, int]],
                                                     change: Callable[[dict[str, Any]], None],
                                                     expected: bool) -> None:
    world = opened(HOB)
    for actor_id, cell in cells.items():
        place(world, actor_id, cell)
    change(world)
    assert side_by_side(world, person(world, first), person(world, second)) is expected


def offered(world: dict[str, Any], actor_id: str = "ada") -> list[str]:
    """The IDs of the concrete actions a guest is offered, with the members of each family."""
    return [item["id"] for option in build_candidates(sees(world, actor_id)) for item in option.get("members", [option])]


def without_the_barkeep(world: dict[str, Any]) -> None:
    """Hob goes off to the cellar: he is not in the hall."""
    world["actors"].remove(hob_of(world))


def closed(world: dict[str, Any]) -> None:
    """Closing time has come."""
    world["closes_at"] = world["time"]


def crowded(world: dict[str, Any]) -> None:
    """Every spot at the bar has a guest on it."""
    for actor_id, cell in zip(("bea", "cid", "dan"), SPOTS):
        place(world, actor_id, cell)


def already_there(world: dict[str, Any]) -> None:
    """Ada already leans on the bar."""
    place(world, "ada", SPOTS[1])


@pytest.mark.parametrize("change, expected", [
    pytest.param(idle, True, id="barkeep-in-sight-and-room-at-the-bar"),
    pytest.param(without_the_barkeep, False, id="nobody-tends-the-bar"),
    pytest.param(closed, False, id="inn-closed"),
    pytest.param(crowded, False, id="every-spot-taken"),
    pytest.param(already_there, False, id="already-leaning-on-it"),
])
def test_leaning_on_the_bar_is_offered_while_the_barkeep_is_there_and_a_spot_is_free(
        change: Callable[[dict[str, Any]], None], expected: bool) -> None:
    world = opened(HOB, guests=4)
    # The door holds three at a time: the three first in move out of the way for the fourth to come in.
    for actor_id, cell in zip(("ada", "bea", "cid"), ((12, 6), (12, 7), (12, 8))):
        place(world, actor_id, cell)
    advance(world, 0.2)
    change(world)
    assert ("stand_at_bar:bar" in offered(world)) is expected


def test_guests_take_different_spots_and_a_crowd_is_refused() -> None:
    world = opened(HOB, guests=4)
    for actor_id, cell in zip(("ada", "bea", "cid"), ((3, 6), (3, 7), (3, 8))):
        place(world, actor_id, cell)
    advance(world, 0.2)
    results = [start_action(world, actor_id, STAND) for actor_id in ("ada", "bea", "cid", "dan")]
    assert ([item["accepted"] for item in results], sorted(person(world, who)["_spot"] for who in ("ada", "bea", "cid"))
            ) == ([True, True, True, False], [[3, 3], [4, 3], [5, 3]])


def test_a_guest_at_the_bar_can_start_a_conversation_with_the_barkeep() -> None:
    world = opened(HOB)
    place(world, "ada", SPOTS[0])
    assert start_action(world, "ada", TALK)["accepted"]
    advance(world, 0.3)
    scene = conversation_of(world, "hob")
    assert scene is not None and scene["participants"] == ["ada", "hob"]


def scene_with_hob(world: dict[str, Any]) -> dict[str, Any]:
    """Ada, Hob and Bea in one conversation at the bar, in that order."""
    for actor_id, cell in (("ada", SPOTS[0]), ("bea", SPOTS[2])):
        place(world, actor_id, cell)
    scene = start_conversation(world, person(world, "ada"), hob_of(world))
    join_conversation(world, person(world, "bea"), hob_of(world))
    return scene


def test_nobody_invites_the_barkeep_and_he_invites_nobody() -> None:
    world = opened(HOB, guests=2)
    scene = scene_with_hob(world)
    assert (offered_kinds(world, scene, hob_of(world)), "invite" in turn_view(world, scene)["acts"]) == ([], True)
    alone = opened(HOB)
    place(alone, "ada", SPOTS[0])
    duo = start_conversation(alone, person(alone, "ada"), hob_of(alone))
    assert (offered_kinds(alone, duo, person(alone, "ada")), "invite" in turn_view(alone, duo)["acts"]) == ([], False)


def test_an_invitation_to_a_guest_is_accepted_from_a_view_with_the_barkeep_in_it() -> None:
    world = opened(HOB, guests=2)
    view = turn_view(world, scene_with_hob(world))
    invite = {"line": "A round of darts?", "act": "invite", "addressee": "bea", "topic": "darts",
              "invitation": "darts_together"}
    assert check_turn(view, invite)["addressee"] == "bea"


def test_an_invitation_to_the_barkeep_is_refused() -> None:
    world = opened(HOB, guests=2)
    view = turn_view(world, scene_with_hob(world))
    invite = {"line": "A round of darts?", "act": "invite", "addressee": "hob", "topic": "darts",
              "invitation": "darts_together"}
    with pytest.raises(ValueError, match="on duty"):
        check_turn(view, invite)


def test_the_view_says_who_is_on_duty() -> None:
    world = opened(HOB, guests=2)
    scene = scene_with_hob(world)
    barkeep_view = turn_view(world, scene)
    scene["turns"].append({"speaker": "ada", "addressee": "hob", "line": "Evening.", "act": "greet", "time": 0.0})
    hob_view = turn_view(world, scene)
    assert (barkeep_view["speaker"].get("on_duty"), hob_view["speaker"]["on_duty"],
            [(item["id"], item.get("on_duty", False)) for item in barkeep_view["conversation"]["participants"]]) == (
        None, "Oak bar", [("ada", False), ("hob", True), ("bea", False)])


def test_the_scripted_barkeep_never_takes_his_leave_first() -> None:
    world = opened(HOB)
    place(world, "ada", SPOTS[0])
    scene = start_conversation(world, person(world, "ada"), hob_of(world))
    acts = []
    for number in range(14):
        scene["turns"].append({"speaker": "ada", "addressee": "hob", "line": "And the road?", "act": "small_talk",
                               "time": float(number)})
        result = scripted_turn(turn_view(world, scene))
        acts.append(result["act"])
        scene["turns"].append({"speaker": "hob", "addressee": "ada", "line": result["line"], "act": result["act"],
                               "time": float(number)})
    assert "leave_conversation" not in acts


def test_the_writers_are_told_he_is_the_barkeep_at_work() -> None:
    world = opened(HOB, guests=2)
    scene = scene_with_hob(world)
    as_guest = turn_content(turn_view(world, scene))
    scene["turns"].append({"speaker": "ada", "addressee": "hob", "line": "Evening.", "act": "greet", "time": 0.0})
    as_barkeep = turn_content(turn_view(world, scene))
    assert ("Hob (the barkeep)" in as_guest, "excuse themselves" in as_barkeep,
            "You are the barkeep, on duty behind the Oak bar" in as_barkeep) == (True, False, True)
