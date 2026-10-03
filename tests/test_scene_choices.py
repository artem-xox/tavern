"""Scenes in the guests' choices and bodies: who decides, the options to talk or join, facing, counts."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.agents import build_candidates
from tavern.briefing import brief
from tavern.decisions import decision_requests
from tavern.lockstep import Evening
from tavern.metrics import conversation_counts
from tavern.world import create_world, observe_actor, observe_people, start_action, step_world


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def hall(*guests: tuple[str, int, int]) -> dict[str, Any]:
    """Build a 12×10 hall with a three-chair table and two windows, and the named guests on cells."""
    return {"width": 12, "height": 10, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 5, "y": 4, "width": 2, "height": 1},
        chair("west", 4, 4), chair("east", 7, 4), chair("north", 5, 3),
        {"id": "window-a", "kind": "window", "name": "Window", "x": 0, "y": 6,
         "interaction_spots": [[1, 6]], "appeal": 0.2, "reach": 3},
        {"id": "window-b", "kind": "window", "name": "Window", "x": 0, "y": 8,
         "interaction_spots": [[1, 8]], "appeal": 0.2, "reach": 3},
    ], "actors": [{"id": name, "name": name.title(), "x": x, "y": y} for name, x, y in guests]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a guest in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def seated(*joiners: str) -> dict[str, Any]:
    """Seat Ada, Bea and Cid, let Ada talk to Bea and the joiners join; their sitting is over."""
    world = create_world(hall(("ada", 4, 4), ("bea", 7, 4), ("cid", 5, 3)))
    for actor_id, seat in (("ada", "west"), ("bea", "east"), ("cid", "north")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
        actor(world, actor_id)["needs"]["social"] = 100.0
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    for joiner in joiners:
        assert start_action(world, joiner, command("join_conversation", "ada"))["accepted"]
    for item in world["actors"]:
        if item["action"] and item["action"]["verb"] == "sit":
            item["_remaining"] = 0.05
    step_world(world, 0.1)
    return world


def at_windows(talk: bool) -> dict[str, Any]:
    """Ada and Bea stand at the two windows, Cid beside them; Ada may have started talking to Bea."""
    world = create_world(hall(("ada", 1, 6), ("bea", 1, 8), ("cid", 2, 7)))
    if talk:
        assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    return world


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda: seated(), ["cid"], id="pair-in-a-scene-does-not-decide"),
    pytest.param(lambda: seated("cid"), [], id="joiner-does-not-decide-either"),
    pytest.param(lambda: at_windows(talk=False), ["ada", "bea", "cid"], id="nobody-talking"),
])
def test_scene_members_get_no_new_decisions(prepare: Callable[[], dict[str, Any]], expected: list[str]) -> None:
    assert [actor_id for actor_id, _view in decision_requests(prepare(), (), {})] == expected


def test_member_who_left_decides_again() -> None:
    world = seated("cid")
    assert start_action(world, "cid", command("wait"))["accepted"]
    for _ in range(12):
        step_world(world, 0.1)
    assert [actor_id for actor_id, _view in decision_requests(world, (), {})] == ["cid"]


def options(world: dict[str, Any], actor_id: str) -> list[str]:
    """The concrete conversation options a guest is offered, as the runners observe."""
    observation = {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}
    concrete = [item for option in build_candidates(observation) for item in option.get("members", [option])]
    return sorted(item["id"] for item in concrete if item["verb"] in ("talk", "join_conversation"))


def hurried() -> dict[str, Any]:
    """Seat Ada, Bea and Cid, nobody talking; Bea badly needs the WC."""
    world = seated()
    world["conversations"].clear()
    actor(world, "bea")["needs"]["bladder"] = 90.0
    actor(world, "ada")["action"] = None
    return world


@pytest.mark.parametrize("prepare, actor_id, expected", [
    pytest.param(lambda: seated(), "cid", ["join_conversation:ada"], id="tablemate-may-join"),
    pytest.param(hurried, "cid", ["talk:ada"], id="someone-in-a-hurry-is-not-offered"),
    pytest.param(lambda: at_windows(talk=False), "ada", ["talk:bea", "talk:cid"], id="standing-side-by-side"),
    pytest.param(lambda: at_windows(talk=True), "cid", ["join_conversation:ada"], id="bystander-may-join"),
])
def test_conversation_options(prepare: Callable[[], dict[str, Any]], actor_id: str, expected: list[str]) -> None:
    assert options(prepare(), actor_id) == expected


@pytest.mark.parametrize("prepare, option, phrases", [
    pytest.param(lambda: seated(), "join_conversation:ada", ["join", "Ada", "Bea"], id="join-names-the-talkers"),
    pytest.param(lambda: at_windows(talk=False), "talk:bea", ["Bea", "beside them"], id="talk-to-someone-standing"),
])
def test_conversation_options_are_briefed(prepare: Callable[[], dict[str, Any]], option: str,
                                          phrases: list[str]) -> None:
    world = prepare()
    actor_id = "cid" if option.startswith("join") else "ada"
    observation = {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}
    text = brief(observation, build_candidates(observation))["options"]
    # Several ways to keep company are offered together as the family.
    sentence = text.get(option, text.get("company", ""))
    assert [phrase for phrase in phrases if phrase not in sentence] == [], sentence


@pytest.mark.parametrize("actor_id, facing", [
    pytest.param("ada", "east", id="listener-faces-the-speaker"),
    pytest.param("bea", "west", id="speaker-faces-the-addressee"),
    pytest.param("cid", "east", id="addressee-faces-the-speaker"),
])
def test_everyone_in_a_scene_faces_the_current_speaker(actor_id: str, facing: str) -> None:
    world = seated("cid")
    while len(world["conversations"][0]["turns"]) < 2:
        step_world(world, 0.1)
    last = world["conversations"][0]["turns"][-1]
    assert ((last["speaker"], last["addressee"]), actor(world, actor_id)["facing"]) == (("bea", "cid"), facing)


def evening(*kinds: str) -> Evening:
    """An evening whose log holds events of the given kinds."""
    events = [{"time": float(index), "actor_id": "ada", "type": kind, "message": f"{kind} {index}"}
              for index, kind in enumerate(kinds)]
    return Evening(events, [], [], ["ada"], 10.0)


@pytest.mark.parametrize("kinds, expected", [
    pytest.param((), {"scenes": 0, "turns": 0, "joins": 0, "leaves": 0}, id="empty-evening"),
    pytest.param(("conversation_started", "turn"), {"scenes": 1, "turns": 1, "joins": 0, "leaves": 0},
                 id="single-scene"),
    pytest.param(("conversation_started", "turn", "turn", "joined_conversation", "joined_conversation",
                  "left_conversation", "action_started"),
                 {"scenes": 1, "turns": 2, "joins": 2, "leaves": 1}, id="duplicate-kinds"),
])
def test_conversation_counts(kinds: tuple[str, ...], expected: dict[str, int]) -> None:
    assert conversation_counts(evening(*kinds)) == expected


def test_malformed_event_fails_loudly() -> None:
    with pytest.raises(KeyError):
        conversation_counts(Evening([{"time": 0.0}], [], [], [], 0.0))
