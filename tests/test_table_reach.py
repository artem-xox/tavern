"""Standing by a table: who is within reach of a chat across its edge, and how that reads to a guest."""

from typing import Any

import pytest

from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.social.scenes import conversation_of, within_reach
from social_hall import actor, advance, command, say, spotted_hall


def room(seated: dict[str, str] | None = None, standing: dict[str, tuple[int, int]] | None = None,
         social: float = 95.0) -> dict[str, Any]:
    """Seat the named guests on the given chairs of `spotted_hall` and stand the others on the given cells."""
    world = create_world(spotted_hall(standing), 4)
    for name, chair in (seated or {}).items():
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 1)
    for item in world["actors"]:
        item["needs"]["social"] = social
    return world


def walking_past(world: dict[str, Any]) -> None:
    """Ada is on her way somewhere."""
    actor(world, "ada").update(status="walking", path=[[3, 4]])


@pytest.mark.parametrize("seated, standing, prepare, expected", [
    pytest.param({"ada": "w", "bea": "e"}, {}, None, True, id="seated-tablemates"),
    pytest.param({"bea": "e"}, {"ada": (3, 3)}, None, True, id="stander-on-the-tables-spot"),
    pytest.param({"ada": "w"}, {"bea": (4, 3)}, None, True, id="seated-one-and-stander-the-other-way-round"),
    pytest.param({}, {"ada": (3, 3), "bea": (4, 3)}, None, True, id="two-standers-on-one-tables-spots"),
    pytest.param({"cid": "fw"}, {"ada": (3, 3), "bea": (8, 1)}, None, False, id="stander-at-another-table"),
    pytest.param({"bea": "e"}, {"ada": (3, 4)}, None, False, id="stander-one-cell-off-the-spot"),
    pytest.param({"bea": "e"}, {"ada": (3, 3)}, walking_past, False, id="stander-walking-past-the-spot"),
    pytest.param({}, {"ada": (3, 3), "bea": (3, 6)}, None, False, id="standers-at-different-tables"),
    pytest.param({}, {}, None, False, id="strangers-in-the-open"),
])
def test_guests_are_within_reach_at_one_table(seated: dict[str, str], standing: dict[str, tuple[int, int]],
                                              prepare: Any, expected: bool) -> None:
    world = room(seated, standing)
    if prepare:
        prepare(world)
    assert within_reach(world, actor(world, "ada"), actor(world, "bea")) is expected


def test_a_standing_guest_talks_with_a_seated_one() -> None:
    world = room({"bea": "e"}, {"ada": (4, 3)})
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    say(world, "small_talk")
    say(world, "remark")
    scene = conversation_of(world, "ada")
    assert (scene["table_id"], len(scene["turns"]), conversation_of(world, "bea") is scene) == ("near", 2, True)


def test_a_stander_joins_a_conversation_at_the_table() -> None:
    world = room({"ada": "w", "bea": "e"}, {"cid": (4, 3)})
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    assert start_action(world, "cid", command("join_conversation", "ada"))["accepted"]
    assert conversation_of(world, "ada")["participants"] == ["ada", "bea", "cid"]


def test_a_stander_who_walks_off_leaves_the_conversation() -> None:
    world = room({"bea": "e"}, {"ada": (4, 3)})
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    assert start_action(world, "ada", command("take_beer", "tap"))["accepted"]
    advance(world, 1)
    assert (conversation_of(world, "ada"), conversation_of(world, "bea")) == (None, None)
    assert any(event["type"] == "left_conversation" for event in actor(world, "ada")["memory"])


def test_a_table_spot_must_be_walkable() -> None:
    data = spotted_hall()
    next(item for item in data["objects"] if item["id"] == "near")["interaction_spots"] = [[3, 2]]
    with pytest.raises(ValueError, match="walkable"):
        create_world(data, 4)


def options_of(world: dict[str, Any], who: str) -> dict[str, str]:
    """What the briefing tells one guest of each option."""
    observation = {**observe_actor(world, who), "people": observe_people(world, who)}
    return brief(observation, build_candidates(observation))["options"]


@pytest.mark.parametrize("seated, standing, viewer, option, phrase", [
    pytest.param({"bea": "e"}, {"ada": (4, 3), "cid": (8, 1)}, "ada", "talk:bea", "sits at the table they stand by",
                 id="standing-guest-talks-to-a-seated-one"),
    pytest.param({"ada": "w"}, {"bea": (4, 3)}, "ada", "talk:bea", "stands beside them",
                 id="seated-guest-talks-to-a-stander"),
    pytest.param({"ada": "w", "bea": "e"}, {}, "ada", "talk:bea", "across the table",
                 id="tablemates-keep-their-wording"),
])
def test_a_chat_across_the_table_edge_is_told_as_it_is(seated: dict[str, str], standing: dict[str, tuple[int, int]],
                                                       viewer: str, option: str, phrase: str) -> None:
    assert phrase in options_of(room(seated, standing), viewer)[option]


def offered_talks(world: dict[str, Any], who: str = "ada") -> list[str]:
    """The IDs of the chats a guest is offered, whichever family holds them."""
    observation = {**observe_actor(world, who), "people": observe_people(world, who)}
    return [item["id"] for option in build_candidates(observation) for item in option.get("members", [option])
            if item["verb"] == "talk"]


@pytest.mark.parametrize("standing, expected", [
    pytest.param({"ada": (7, 0), "bea": (8, 0)}, ["talk:bea"], id="a-stander-beside-them-in-the-open"),
    pytest.param({"ada": (7, 0), "bea": (7, 3)}, [], id="a-stander-three-cells-off"),
])
def test_a_guest_is_offered_a_chat_with_someone_standing_beside_them_in_the_open(
        standing: dict[str, tuple[int, int]], expected: list[str]) -> None:
    assert offered_talks(room({}, standing)) == expected


def test_a_stander_on_a_tables_spot_talks_with_one_in_the_open_beside_them() -> None:
    world = room({}, {"ada": (3, 3), "bea": (5, 3)})
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 1)
    scene = conversation_of(world, "ada")
    assert (scene["table_id"], scene["participants"]) == (None, ["ada", "bea"])
