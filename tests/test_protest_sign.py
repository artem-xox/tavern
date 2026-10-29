"""Greta's protest sign: whom it names, who is shamed and who cheers, and when it is offered (S2-18)."""

from typing import Any

import pytest

from tavern.hall.world import create_world, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.options import option_text
from tavern.social.signature_acts import RAISES_AGAIN_AFTER, accused_of
from social_hall import actor, advance, command, hall


def regarding(**opinions: float) -> dict[str, Any]:
    """A protester whose opinion of each named person is as given."""
    return {"id": "greta", "thoughts": [], "relations": {
        other: {"name": other.title(), "opinion": opinion, "familiarity": "acquaintance"}
        for other, opinion in opinions.items()}}


def people(*ids: str) -> list[dict[str, Any]]:
    return [{"id": other} for other in ids]


@pytest.mark.parametrize("opinions, present, expected", [
    pytest.param({}, (), None, id="nobody-present"),
    pytest.param({"cid": 10.0}, ("cid",), "cid", id="one-guest"),
    pytest.param({"cid": -30.0, "bea": -30.0}, ("cid", "bea"), "bea", id="a-tie-goes-to-the-lower-id"),
    pytest.param({"bea": -10.0, "cid": -60.0, "dan": 20.0}, ("dan", "cid", "bea"), "cid", id="the-lowest-of-three"),
    pytest.param({"bea": -10.0, "cid": -60.0}, ("bea",), "bea", id="the-absent-are-not-named"),
])
def test_the_accused_is_the_guest_the_protester_thinks_worst_of(
        opinions: dict[str, float], present: tuple[str, ...], expected: str | None) -> None:
    accused = accused_of(regarding(**opinions), people(*present), 0.0)
    assert (accused["id"] if accused else None) == expected


def watching(*rivals: str, memory: list[dict[str, Any]] | None = None, time: float = 500.0,
             signs: int = 1) -> dict[str, Any]:
    """An observation of a guest who carries a sign and sees these people."""
    return {"actor": {"id": "greta", "name": "Greta", "x": 1, "y": 1, "inventory": {"beer": 0, "protest_sign": signs},
                      "needs": {"thirst": 20, "fatigue": 20, "bladder": 20}, "memory": memory or [],
                      "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5}, "thoughts": [],
                      "relations": regarding(cid=-60.0)["relations"]},
            "objects": [], "memory": [], "time": time, "people": people(*rivals)}


def raised(at: float) -> dict[str, Any]:
    """A memory of having raised the sign at that time."""
    return {"time": at, "actor_id": "greta", "type": "signature_act", "message": "Greta raises a protest sign",
            "verb": "raise_sign"}


def offers_the_sign(view: dict[str, Any]) -> bool:
    return "raise_sign" in {member["verb"] for option in build_candidates(view) for member in option.get("members", [option])}


@pytest.mark.parametrize("view, expected", [
    pytest.param(watching("cid"), True, id="a-rival-in-sight"),
    pytest.param(watching(), False, id="nobody-in-sight"),
    pytest.param(watching("cid", signs=0), False, id="no-sign"),
    pytest.param(watching("cid", memory=[raised(450.0)]), False, id="raised-a-moment-ago"),
    pytest.param(watching("cid", memory=[raised(500.0 - RAISES_AGAIN_AFTER - 1)]), True, id="raised-long-ago"),
    pytest.param(watching("cid", memory=[{**raised(450.0), "verb": "livestream"}]), True, id="another-act-does-not-count"),
])
def test_the_sign_is_offered_when_there_is_someone_to_protest_at_and_it_is_not_overused(
        view: dict[str, Any], expected: bool) -> None:
    assert offers_the_sign(view) is expected


def test_the_option_names_the_guest_who_would_be_accused() -> None:
    view = watching("bea", "cid")
    assert "cid" in option_text(view, {"verb": "raise_sign", "target_id": None}).lower()


def opinion(world: dict[str, Any], holder: str, about: str, value: float) -> None:
    actor(world, holder)["relations"][about] = {"name": about.title(), "opinion": value, "familiarity": "acquaintance"}


def protest() -> dict[str, Any]:
    """Ada raises her sign: Cid is the one she likes least, Dan dislikes Cid too, Bea is fond of him."""
    world = create_world(hall(), 4)
    actor(world, "ada")["inventory"]["protest_sign"] = 1
    for holder, about, value in (("ada", "cid", -70.0), ("ada", "bea", 10.0), ("ada", "dan", -20.0),
                                 ("dan", "cid", -40.0), ("bea", "cid", 30.0)):
        opinion(world, holder, about, value)
    assert start_action(world, "ada", command("raise_sign")) == {"accepted": True, "reason": None}
    advance(world, 11)
    return world


def kinds(world: dict[str, Any], holder: str) -> list[tuple[str, str | None]]:
    return [(thought["kind"], thought["about"]) for thought in actor(world, holder)["thoughts"]
            if thought["kind"] in ("shamed", "protest_cheered")]


@pytest.mark.parametrize("holder, expected", [
    pytest.param("cid", [("shamed", "ada")], id="the-accused-is-shamed"),
    pytest.param("dan", [("protest_cheered", "ada")], id="a-listener-who-dislikes-the-accused-cheers"),
    pytest.param("bea", [], id="a-friend-of-the-accused-does-not"),
    pytest.param("ada", [], id="the-protester-has-no-such-thought"),
])
def test_the_hall_takes_a_raised_sign_to_heart(holder: str, expected: list[tuple[str, str | None]]) -> None:
    assert kinds(protest(), holder) == expected


def test_one_raised_sign_is_one_logged_act_aimed_at_the_accused() -> None:
    acts = [item for item in protest()["events"] if item["type"] == "signature_act"]
    assert [(item["verb"], item["item"], item["subject"], item["message"]) for item in acts] == [
        ("raise_sign", "protest_sign", ["cid"], "Ada raises a protest sign at Cid and shouts")]


def test_the_sign_is_refused_without_one() -> None:
    world = create_world(hall(), 4)
    assert start_action(world, "ada", command("raise_sign"))["reason"] == "No protest_sign in inventory"
