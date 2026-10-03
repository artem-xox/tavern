"""Conversation scenes: who may start one, join it or leave it, when it ends, and saving it."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tavern.hearing import EVENT_SOUNDS, Sound, emit
from tavern.persistence import load_world, save_world
from tavern.scenes import conversation_of
from tavern.world import create_world, start_action, step_world


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the round table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def guest(actor_id: str, x: int, y: int, **needs: float) -> dict[str, Any]:
    """Build a guest standing on a cell, with any needs given."""
    return {"id": actor_id, "name": actor_id.title(), "x": x, "y": y, "needs": needs}


def hall(*guests: dict[str, Any]) -> dict[str, Any]:
    """Build a 12×10 hall: a four-chair table, a tap with a line, a WC, two windows and a door."""
    return {"width": 12, "height": 10, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 5, "y": 4, "width": 2, "height": 1},
        chair("west", 4, 4), chair("east", 7, 4), chair("north", 5, 3), chair("south", 6, 5),
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 0, "y": 0, "interaction_spots": [[1, 0]],
         "queue_spots": [[2, 0], [3, 0], [4, 0]], "stock": 10},
        {"id": "wc", "kind": "toilet", "name": "WC", "x": 11, "y": 0, "interaction_spots": [[11, 1]]},
        {"id": "window-a", "kind": "window", "name": "Window", "x": 0, "y": 6,
         "interaction_spots": [[1, 6]], "appeal": 0.2, "reach": 3},
        {"id": "window-b", "kind": "window", "name": "Window", "x": 0, "y": 8,
         "interaction_spots": [[1, 8]], "appeal": 0.2, "reach": 3},
        {"id": "door", "kind": "door", "name": "Door", "x": 11, "y": 9, "interaction_spots": [[10, 9]]},
    ], "actors": list(guests)}


def command(verb: str, target: Any = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks, without anyone deciding."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a guest in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def at_table(*names: str, **needs: float) -> dict[str, Any]:
    """Seat the named guests (of ada, bea, cid, dan) at the table; eve stands far off."""
    chairs = {"ada": ("west", 4, 4), "bea": ("east", 7, 4), "cid": ("north", 5, 3), "dan": ("south", 6, 5)}
    world = create_world(hall(*(guest(name, *chairs[name][1:], **needs) for name in names), guest("eve", 9, 8)))
    for name in names:
        assert start_action(world, name, command("sit", chairs[name][0]))["accepted"]
    return world


def in_line() -> dict[str, Any]:
    """Ada and Bea wait in the tap's line behind Cid, who pours; Dan waits far behind nobody."""
    world = create_world(hall(guest("cid", 6, 0), guest("ada", 7, 0), guest("bea", 8, 0), guest("dan", 9, 6)))
    for name in ("cid", "ada", "bea"):
        assert start_action(world, name, command("take_beer", "tap"))["accepted"]
    advance(world, 4)
    assert [entry["actor_id"] for entry in world["map"]["objects"][5]["queue"]] == ["ada", "bea"]
    return world


def by_the_windows() -> dict[str, Any]:
    """Ada and Bea stand at the two windows, two steps apart; Cid stands beside them; Dan far off."""
    return create_world(hall(guest("ada", 1, 6), guest("bea", 1, 8), guest("cid", 2, 7), guest("dan", 9, 2)))


def talking(world: dict[str, Any], *joiners: str) -> dict[str, Any]:
    """Let Ada start talking to Bea, then the joiners join her."""
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    for name in joiners:
        assert start_action(world, name, command("join_conversation", "ada"))["accepted"]
    return world


@pytest.mark.parametrize("prepare, table_id", [
    pytest.param(lambda: at_table("ada", "bea"), "table", id="seated-tablemates"),
    pytest.param(in_line, None, id="side-by-side-in-a-line"),
    pytest.param(by_the_windows, None, id="side-by-side-by-the-windows"),
])
def test_talk_starts_a_scene(prepare: Callable[[], dict[str, Any]], table_id: str | None) -> None:
    world = prepare()
    started = world["time"]
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    scene = conversation_of(world, "bea")
    opening = world["rules"]["conversation"]["opening"]
    assert (scene["participants"], scene["table_id"], scene["turns"], scene["started_at"], scene["next_turn_at"]) == (
        ["ada", "bea"], table_id, [], started, started + opening)
    assert conversation_of(world, "ada") is scene


def test_talking_in_a_line_keeps_the_place_in_it() -> None:
    world = talking(in_line())
    assert [entry["actor_id"] for entry in world["map"]["objects"][5]["queue"]] == ["ada", "bea"]
    assert (actor(world, "ada")["status"], actor(world, "ada")["action"]["verb"]) == ("queued", "take_beer")


def busy_bea(world: dict[str, Any]) -> None:
    """Bea is already talking to Cid."""
    assert start_action(world, "bea", command("talk", "cid"))["accepted"]


def busy_ada(world: dict[str, Any]) -> None:
    """Ada is already talking to Cid."""
    assert start_action(world, "ada", command("talk", "cid"))["accepted"]


def pressed_bea(world: dict[str, Any]) -> None:
    """Bea badly needs the WC."""
    actor(world, "bea")["needs"]["bladder"] = 90.0


@pytest.mark.parametrize("prepare, target", [
    pytest.param(lambda world: None, None, id="empty-target"),
    pytest.param(pressed_bea, "bea", id="partner-pressed-by-a-need"),
    pytest.param(lambda world: None, "ada", id="talking-to-oneself"),
    pytest.param(lambda world: None, "nobody", id="unknown-guest"),
    pytest.param(lambda world: None, [], id="malformed-target"),
    pytest.param(lambda world: None, "eve", id="stranger-across-the-hall"),
    pytest.param(busy_bea, "bea", id="partner-already-in-a-scene"),
    pytest.param(busy_ada, "bea", id="already-in-a-scene"),
])
def test_talk_is_refused_without_a_free_partner_close_by(prepare: Callable[[dict[str, Any]], None],
                                                         target: Any) -> None:
    world = at_table("ada", "bea", "cid")
    prepare(world)
    assert not start_action(world, "ada", command("talk", target))["accepted"]


@pytest.mark.parametrize("prepare, joiner", [
    pytest.param(lambda: at_table("ada", "bea", "cid"), "cid", id="tablemate-joins"),
    pytest.param(by_the_windows, "cid", id="bystander-joins-a-standing-scene"),
])
def test_others_join_a_scene(prepare: Callable[[], dict[str, Any]], joiner: str) -> None:
    world = talking(prepare(), joiner)
    assert conversation_of(world, joiner)["participants"] == ["ada", "bea", joiner]
    assert any(event["type"] == "joined_conversation" for event in actor(world, joiner)["memory"])


def full_table() -> dict[str, Any]:
    """Seat everyone at the table and let Ada, Bea and Cid talk; the scene allows three."""
    world = talking(at_table("ada", "bea", "cid", "dan"), "cid")
    world["rules"]["conversation"]["max_participants"] = 3
    return world


@pytest.mark.parametrize("prepare, joiner, target", [
    pytest.param(lambda: talking(at_table("ada", "bea")), "eve", "ada", id="stranger-across-the-hall"),
    pytest.param(lambda: at_table("ada", "bea", "cid"), "cid", "ada", id="nobody-is-talking"),
    pytest.param(lambda: talking(at_table("ada", "bea", "cid"), "cid"), "cid", "bea", id="duplicate-joiner"),
    pytest.param(lambda: talking(by_the_windows()), "dan", "ada", id="too-far-from-a-standing-scene"),
    pytest.param(full_table, "dan", "ada", id="scene-is-full"),
    pytest.param(lambda: talking(at_table("ada", "bea", "cid")), "cid", None, id="malformed-target"),
])
def test_joining_is_refused(prepare: Callable[[], dict[str, Any]], joiner: str, target: Any) -> None:
    world = prepare()
    assert not start_action(world, joiner, command("join_conversation", target))["accepted"]


def test_three_way_conversation_survives_a_member_leaving_for_the_wc() -> None:
    world = talking(at_table("ada", "bea", "cid", social=100), "cid")
    advance(world, 3)
    scene = conversation_of(world, "ada")
    assert start_action(world, "cid", command("use_toilet", "wc"))["accepted"]
    spoken = len(scene["turns"])
    advance(world, 5)
    assert (conversation_of(world, "ada"), scene["participants"], conversation_of(world, "cid")) == (
        scene, ["ada", "bea"], None)
    assert len(scene["turns"]) > spoken
    assert any(event["type"] == "left_conversation" for event in actor(world, "cid")["memory"])


def partner_leaves(world: dict[str, Any]) -> None:
    """Bea gets up for a beer."""
    assert start_action(world, "bea", command("take_beer", "tap"))["accepted"]


def closing(world: dict[str, Any]) -> None:
    """The inn closes."""
    world["closes_at"] = world["time"] + 0.05


def content(world: dict[str, Any]) -> None:
    """Both have had all the company they want."""
    for item in world["actors"]:
        item["needs"]["social"] = 0.0


def quarrel_nearby(world: dict[str, Any]) -> None:
    """A loud quarrel breaks out beside the table."""
    emit(world, EVENT_SOUNDS["quarrel"], ["eve"], [8, 4], [], "Eve and someone quarreled", "quarrel")


@pytest.mark.parametrize("cause", [
    pytest.param(partner_leaves, id="fewer-than-two-remain"),
    pytest.param(closing, id="closing-time"),
    pytest.param(content, id="social-need-satisfied"),
    pytest.param(quarrel_nearby, id="loud-interrupt"),
])
def test_scene_ends(cause: Callable[[dict[str, Any]], None]) -> None:
    world = talking(at_table("ada", "bea"))
    cause(world)
    advance(world, 3.5)
    assert (world["conversations"], actor(world, "ada")["action"]) == ([], None)


def test_loud_interrupt_takes_a_member_out_of_a_bigger_scene() -> None:
    world = talking(at_table("ada", "bea", "cid", "dan"), "cid", "dan")
    # A bang right behind Bea's chair carries only three cells: loud for her, a murmur for Dan.
    emit(world, Sound("bang", 1.0, 3.0, "a bang"), [], [8, 4], [], "A bench fell over", None)
    advance(world, 0.1)
    assert (conversation_of(world, "bea"), conversation_of(world, "ada")["participants"]) == (
        None, ["ada", "cid", "dan"])


def test_scene_ending_pleasantly_is_remembered_as_a_conversation() -> None:
    world = talking(at_table("ada", "bea", social=90))
    advance(world, 6)
    content(world)
    advance(world, 0.2)
    chats = [event["message"] for event in world["events"] if event["type"] == "conversation"]
    assert chats and chats[0].startswith("Ada and Bea chatted about")


def test_scene_survives_save_and_load(tmp_path: Path) -> None:
    world = talking(at_table("ada", "bea", "cid"), "cid")
    advance(world, 3)
    save_world(world, tmp_path / "scene.json")
    assert load_world(tmp_path / "scene.json") == world


def scene_of(world: dict[str, Any]) -> dict[str, Any]:
    """The only scene."""
    return world["conversations"][0]


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(conversations={}), id="malformed-list"),
    pytest.param(lambda world: scene_of(world).update(participants=["ada"]), id="single-participant"),
    pytest.param(lambda world: scene_of(world).update(participants=["ada", "ada"]), id="duplicate-participant"),
    pytest.param(lambda world: scene_of(world).update(participants=["ada", "nobody"]), id="unknown-participant"),
    pytest.param(lambda world: world["conversations"].append(dict(scene_of(world), id="scene-x")),
                 id="guest-in-two-scenes"),
    pytest.param(lambda world: scene_of(world)["turns"].append({"speaker": "ada"}), id="malformed-turn"),
    pytest.param(lambda world: scene_of(world).update(next_turn_at="soon"), id="malformed-turn-time"),
    pytest.param(lambda world: scene_of(world).update(table_id="nowhere"), id="unknown-table"),
    pytest.param(lambda world: scene_of(world).update(writing={"turn": "one"}), id="malformed-claim"),
])
def test_corrupt_saved_scenes_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], None]) -> None:
    world = talking(at_table("ada", "bea", "cid"))
    advance(world, 3)
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
