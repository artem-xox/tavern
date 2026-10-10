"""An invitation's answer is the invitee's own choice: the options, the decided act the line must be, and a counter."""

from copy import deepcopy
import json
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, start_action
from tavern.social.conversation import offered_acts
from tavern.social.invitations import accept, answer_act, answer_options
from tavern.social.turns import claim_turns, turn_view
from social_hall import actor, advance, command, know, say, scene_of, spotted_hall
from test_dice_invitation import CHAIRS, TABLE


def inviting(kind: str = "dice_together", bea_knows: tuple[str, ...] = ()) -> dict[str, Any]:
    """Ada and Bea sit talking; Ada knows the places and has just invited Bea to something."""
    data = spotted_hall()
    data["objects"] += [deepcopy(TABLE), *deepcopy(CHAIRS)]
    world = create_world(data, 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    know(world, "ada", "dice-table", "darts", "tap", "door")
    if bea_knows:
        know(world, "bea", *bea_knows)
    say(world, "invite", "Fancy it?", invitation=kind)
    return world


def pending(world: dict[str, Any]) -> dict[str, Any]:
    """The invitation waiting in Ada's scene."""
    scene = scene_of(world)
    assert scene is not None and scene["invitation"] is not None
    return scene["invitation"]


def options(world: dict[str, Any]) -> list[str]:
    """What Bea may answer."""
    scene = scene_of(world)
    assert scene is not None
    return answer_options(world, scene, actor(world, "bea"))


@pytest.mark.parametrize("kind, knows, expected", [
    pytest.param("dice_together", (), ["accept", "decline", "counter:move_together"], id="a-guest-who-knows-nothing-to-offer-but-a-free-table"),
    pytest.param("dice_together", ("darts",), ["accept", "decline", "counter:darts_together", "counter:move_together"], id="darts-to-offer"),
    pytest.param("dice_together", ("darts", "tap"), ["accept", "decline", "counter:darts_together", "counter:buy_drink", "counter:move_together"],
                 id="darts-and-an-ale-in-the-order-of-the-kinds"),
    pytest.param("dice_together", ("dice-table",), ["accept", "decline", "counter:move_together"], id="the-kind-asked-is-never-countered"),
    pytest.param("darts_together", ("darts", "dice-table"), ["accept", "decline", "counter:dice_together", "counter:move_together"],
                 id="another-kind-than-the-one-asked"),
])
def test_the_answers_an_invitee_may_choose_between(kind: str, knows: tuple[str, ...], expected: list[str]) -> None:
    assert options(inviting(kind, knows)) == expected


@pytest.mark.parametrize("answer, act", [
    pytest.param("accept", "accept", id="accept"),
    pytest.param("decline", "decline", id="decline"),
    pytest.param("counter:darts_together", "invite", id="a-counter-is-an-invitation"),
])
def test_an_answer_is_said_with_one_act(answer: str, act: str) -> None:
    assert answer_act(answer) == act


def test_an_answer_that_is_not_one_fails_loudly() -> None:
    with pytest.raises(ValueError):
        answer_act("maybe")


@pytest.mark.parametrize("answer, acts, kinds", [
    pytest.param(None, {"accept", "decline"}, [], id="undecided-both-answers-are-open-as-before"),
    pytest.param("accept", {"accept"}, [], id="decided-to-accept"),
    pytest.param("decline", {"decline"}, [], id="decided-to-decline"),
    pytest.param("counter:darts_together", {"invite"}, ["darts_together"], id="decided-to-counter"),
])
def test_a_decided_answer_is_the_only_act_the_invitee_may_speak(answer: str | None, acts: set[str],
                                                                kinds: list[str]) -> None:
    world = inviting("dice_together", ("darts",))
    if answer:
        pending(world)["answer"] = answer
    scene = scene_of(world)
    assert scene is not None
    offered = set(offered_acts(world, scene, actor(world, "bea")))
    view = turn_view(world, scene)
    assert (acts <= offered if answer is None else offered == acts, view["invitations"], view["answer"]) == (
        True, kinds, answer)


def test_a_counter_declines_nothing_but_leaves_the_invitees_own_invitation_waiting() -> None:
    world = inviting("dice_together", ("darts",))
    pending(world)["answer"] = "counter:darts_together"
    say(world, "invite", "Darts instead?", invitation="darts_together")
    invitation = pending(world)
    countered = [item["message"] for item in world["events"] if item["type"] == "invitation_countered"]
    assert (invitation, countered, [item for item in world["events"] if item["type"] == "invitation_declined"]) == (
        {"kind": "darts_together", "from": "bea", "to": "ada"},
        ["Bea turned down an invitation to play a game of dice and invited Ada to play darts together instead"], [])


def test_a_counter_may_be_countered_in_turn() -> None:
    world = inviting("dice_together", ("darts",))
    pending(world)["answer"] = "counter:darts_together"
    say(world, "invite", "Darts instead?", invitation="darts_together")
    pending(world)["answer"] = "counter:dice_together"
    say(world, "invite", "Dice after all?", invitation="dice_together")
    assert [item["message"] for item in world["events"] if item["type"] == "invitation_countered"] == [
        "Bea turned down an invitation to play a game of dice and invited Ada to play darts together instead",
        "Ada turned down an invitation to play darts together and invited Bea to play a game of dice instead"]


def test_accepting_a_decided_invitation_still_sends_the_two_off() -> None:
    world = inviting("darts_together")
    pending(world)["answer"] = "accept"
    scene = scene_of(world)
    assert scene is not None
    accept(world, scene, actor(world, "bea"), actor(world, "ada"))
    assert [item for item in world["invitations"]] == [
        {"kind": "darts_together", "from": "ada", "to": "bea", "stage": "accepted", "held": 0}]


def saved(tmp_path: Any, mutate: Any = None) -> Any:
    world = inviting("dice_together", ("darts",))
    pending(world)["answer"] = "counter:darts_together"
    path = tmp_path / "world.json"
    save_world(world, path)
    if mutate:
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))
    return path


def test_a_decided_answer_survives_a_save(tmp_path: Any) -> None:
    scene = scene_of(load_world(saved(tmp_path)))
    assert scene is not None and scene["invitation"]["answer"] == "counter:darts_together"


@pytest.mark.parametrize("answer", [
    pytest.param("maybe", id="unknown-answer"),
    pytest.param("counter:waltz", id="a-counter-of-an-unknown-kind"),
    pytest.param("counter:dice_together", id="a-counter-of-the-kind-asked"),
    pytest.param(3, id="not-text"),
])
def test_a_saved_answer_that_is_not_one_is_rejected(tmp_path: Any, answer: Any) -> None:
    with pytest.raises(ValueError):
        load_world(saved(tmp_path, lambda data: data["conversations"][0]["invitation"].update(answer=answer)))


@pytest.mark.parametrize("act, words", [
    pytest.param("accept", "Bea said yes to Ada's invitation to play a game of dice", id="accepted"),
    pytest.param("decline", "Bea turned down Ada's invitation to play a game of dice", id="declined"),
])
def test_whoever_invited_is_told_the_answer_in_their_memory(act: str, words: str) -> None:
    world = inviting("dice_together")
    say(world, act, "Well now.")
    answered = [item["message"] for item in actor(world, "ada")["memory"] if item["type"] == "invitation_answered"]
    assert answered == [words]
