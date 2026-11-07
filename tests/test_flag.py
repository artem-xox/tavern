"""Kim Jong Un's little flag: whom it threatens, who takes it to heart, and when it is offered."""

from typing import Any

import pytest

from tavern.hall.world import create_world, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.options import option_text
from tavern.social.signature_acts import BRANDISH_BELOW, BRANDISHES_AGAIN_AFTER
from social_hall import actor, advance, command, hall


def regarding(**opinions: float) -> dict[str, Any]:
    """The relations of a guest whose opinion of each named person is as given."""
    return {other: {"name": other.title(), "opinion": opinion, "familiarity": "acquaintance"}
            for other, opinion in opinions.items()}


def watching(*rivals: str, opinion: float = -60.0, memory: list[dict[str, Any]] | None = None, time: float = 500.0,
             flags: int = 1) -> dict[str, Any]:
    """An observation of a guest who carries a flag and sees these people, all of whom they rate as given."""
    return {"actor": {"id": "kim", "name": "Kim", "x": 1, "y": 1, "inventory": {"beer": 0, "flag": flags},
                      "needs": {"thirst": 20, "fatigue": 20, "bladder": 20}, "memory": memory or [],
                      "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5}, "thoughts": [],
                      "relations": regarding(**dict.fromkeys(rivals, opinion))},
            "objects": [], "memory": [], "time": time, "people": [{"id": other} for other in rivals]}


def brandished(at: float) -> dict[str, Any]:
    """A memory of having brandished the flag at that time."""
    return {"time": at, "actor_id": "kim", "type": "signature_act", "message": "Kim brandishes a flag",
            "verb": "brandish_flag"}


def offers_the_flag(view: dict[str, Any]) -> bool:
    return "brandish_flag" in {member["verb"] for option in build_candidates(view)
                               for member in option.get("members", [option])}


@pytest.mark.parametrize("view, expected", [
    pytest.param(watching("cid"), True, id="a-guest-they-dislike-in-sight"),
    pytest.param(watching(), False, id="nobody-in-sight"),
    pytest.param(watching("cid", opinion=BRANDISH_BELOW), False, id="a-grudge-too-small-to-threaten-over"),
    pytest.param(watching("cid", opinion=BRANDISH_BELOW - 1), True, id="a-grudge-just-big-enough"),
    pytest.param(watching("cid", opinion=40.0), False, id="a-friend"),
    pytest.param(watching("cid", flags=0), False, id="no-flag"),
    pytest.param(watching("cid", memory=[brandished(450.0)]), False, id="brandished-a-moment-ago"),
    pytest.param(watching("cid", memory=[brandished(500.0 - BRANDISHES_AGAIN_AFTER - 1)]), True,
                 id="brandished-long-ago"),
    pytest.param(watching("cid", memory=[{**brandished(450.0), "verb": "raise_sign"}]), True,
                 id="another-act-does-not-count"),
])
def test_the_flag_is_offered_against_someone_disliked_and_not_overused(view: dict[str, Any], expected: bool) -> None:
    assert offers_the_flag(view) is expected


def test_the_option_names_the_guest_who_would_be_threatened() -> None:
    view = watching("bea", "cid")
    view["actor"]["relations"]["cid"]["opinion"] = -80.0
    assert "cid" in option_text(view, {"verb": "brandish_flag", "target_id": None}).lower()


def threat() -> dict[str, Any]:
    """Ada brandishes her flag: Cid is the one she likes least, Bea is fond of her, Dan is out of mind."""
    world = create_world(hall(), 4)
    actor(world, "ada")["inventory"]["flag"] = 1
    for about, value in (("cid", -70.0), ("bea", 10.0), ("dan", -20.0)):
        actor(world, "ada")["relations"][about] = {"name": about.title(), "opinion": value,
                                                    "familiarity": "acquaintance"}
    assert start_action(world, "ada", command("brandish_flag")) == {"accepted": True, "reason": None}
    advance(world, 7)
    return world


def kinds(world: dict[str, Any], holder: str) -> list[tuple[str, str | None]]:
    return [(thought["kind"], thought["about"]) for thought in actor(world, holder)["thoughts"]
            if thought["kind"] == "threatened"]


@pytest.mark.parametrize("holder, expected", [
    pytest.param("cid", [("threatened", "ada")], id="the-threatened-guest-is-shaken"),
    pytest.param("bea", [], id="a-bystander-is-not"),
    pytest.param("ada", [], id="the-one-with-the-flag-has-no-such-thought"),
])
def test_the_target_of_a_brandished_flag_takes_it_to_heart(holder: str, expected: list[tuple[str, str | None]]) -> None:
    assert kinds(threat(), holder) == expected


def test_one_brandished_flag_is_one_logged_act_aimed_at_the_guest_disliked_most() -> None:
    acts = [item for item in threat()["events"] if item["type"] == "signature_act"]
    assert [(item["verb"], item["item"], item["subject"]) for item in acts] == [
        ("brandish_flag", "flag", ["cid"])]


def test_the_flag_is_refused_without_one() -> None:
    world = create_world(hall(), 4)
    assert start_action(world, "ada", command("brandish_flag"))["reason"] == "No flag in inventory"
