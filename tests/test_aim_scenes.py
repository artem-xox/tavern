"""An aim travels with the action that carries it, into the scene, the line writer's view and the log."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, start_action
from tavern.social.scenes import conversation_of
from tavern.social.turns import claim_turns
from social_hall import actor, advance, command, hall, say, spotted_hall


def aimed(verb: str, target: str, aim: str | None) -> dict[str, Any]:
    """An action with an aim."""
    return {**command(verb, target), **({} if aim is None else {"aim": aim})}


def seated(**chairs: str) -> dict[str, Any]:
    """Seat the named guests on chairs of `spotted_hall` and make them all lonely."""
    world = create_world(spotted_hall(), 4)
    for name, chair in chairs.items():
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    return world


def test_a_talk_with_an_aim_gives_the_scene_the_speakers_aim_and_logs_it() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", aimed("talk", "bea", "pass_time"))["accepted"]
    scene = conversation_of(world, "ada")
    assert scene is not None
    assert (scene["aims"], [item["message"] for item in world["events"] if item["type"] == "aim_set"]) == (
        {"ada": {"aim": "pass_time", "about": "bea", "kept": False}},
        ["Ada means to pass the time with Bea (pass_time)"])


def test_a_talk_without_an_aim_leaves_the_scene_as_it_was() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    scene = conversation_of(world, "ada")
    assert scene is not None and "aims" not in scene


def test_a_walk_over_with_an_aim_carries_it_to_the_partners_table() -> None:
    world = seated(ada="w", cid="fw")
    assert start_action(world, "ada", aimed("approach", "cid", "win_over"))["accepted"]
    advance(world, 6)
    scene = conversation_of(world, "ada")
    assert scene is not None and scene["aims"]["ada"]["aim"] == "win_over"


def test_joining_a_conversation_with_an_aim_adds_it_beside_the_others() -> None:
    world = seated(ada="w", bea="e", cid="n")
    assert start_action(world, "ada", aimed("talk", "bea", "pass_time"))["accepted"]
    assert start_action(world, "cid", aimed("join_conversation", "ada", "win_over"))["accepted"]
    scene = conversation_of(world, "ada")
    assert scene is not None and {who: item["aim"] for who, item in scene["aims"].items()} == {
        "ada": "pass_time", "cid": "win_over"}


def writer_view(world: dict[str, Any]) -> dict[str, Any]:
    """The view a line writer gets for the next speaker of Ada's scene."""
    [(_, _, view)] = claim_turns(world)
    return view


def test_the_line_writer_is_told_what_the_speaker_came_for_until_it_is_said() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", aimed("talk", "bea", "win_over"))["accepted"]
    first = writer_view(world)["speaker"]
    assert (first["id"], first["aim"]) == ("ada", {
        "id": "win_over", "words": "make a good impression on Bea", "done": False, "detail": None,
        "acts": ["introduce", "compliment", "small_talk"]})


def test_an_aim_is_kept_once_and_logged_when_the_speaker_says_one_of_its_acts() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", aimed("talk", "bea", "win_over"))["accepted"]
    assert say(world, "greet") == "ada"
    say(world, "greet")
    assert say(world, "compliment") == "ada"
    say(world, "compliment")
    say(world, "compliment")
    kept = [item["message"] for item in world["events"] if item["type"] == "aim_kept"]
    assert kept == ["Ada got round to it: make a good impression on Bea (win_over)"]


def test_no_aim_is_none_in_the_view() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    assert writer_view(world)["speaker"]["aim"] is None


def test_the_action_keeps_its_aim_while_it_is_carried_out() -> None:
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", aimed("talk", "bea", "pass_time"))["accepted"]
    assert actor(world, "ada")["action"] == {"id": "talk:bea", "verb": "talk", "target_id": "bea", "aim": "pass_time"}


@pytest.mark.parametrize("verb, target, aim", [
    pytest.param("sit", "w", "pass_time", id="an-aim-on-a-chair"),
    pytest.param("talk", "bea", "nothing", id="an-unknown-aim"),
    pytest.param("talk", "bea", "tell_news", id="news-without-a-fact"),
])
def test_an_action_with_a_wrong_aim_is_refused(verb: str, target: str, aim: str) -> None:
    world = seated(ada="w", bea="e")
    assert not start_action(world, "ada", aimed(verb, target, aim))["accepted"]


def saved_with_aim(tmp_path: Any, mutate: Any = None) -> Any:
    """Save a world in which Ada talks with an aim, after changing the JSON by `mutate`."""
    world = seated(ada="w", bea="e")
    assert start_action(world, "ada", aimed("talk", "bea", "pass_time"))["accepted"]
    path = tmp_path / "world.json"
    save_world(world, path)
    if mutate:
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))
    return path


def test_an_aim_survives_a_save(tmp_path: Any) -> None:
    world = load_world(saved_with_aim(tmp_path))
    scene = conversation_of(world, "ada")
    assert scene is not None
    assert (actor(world, "ada")["action"]["aim"], scene["aims"]["ada"]["aim"]) == ("pass_time", "pass_time")


def ada_of(data: dict[str, Any]) -> dict[str, Any]:
    """Ada's saved record."""
    return next(item for item in data["actors"] if item["id"] == "ada")


@pytest.mark.parametrize("mutate", [
    pytest.param(lambda data: ada_of(data)["action"].update(aim="nothing"), id="action-with-an-unknown-aim"),
    pytest.param(lambda data: ada_of(data)["action"].update(verb="wait", target_id=None), id="action-aim-on-a-wait"),
    pytest.param(lambda data: data["conversations"][0]["aims"]["ada"].update(aim="nothing"), id="scene-unknown-aim"),
    pytest.param(lambda data: data["conversations"][0]["aims"]["ada"].update(about="eve"), id="scene-unknown-person"),
    pytest.param(lambda data: data["conversations"][0]["aims"]["ada"].update(kept="yes"), id="scene-kept-not-a-bool"),
    pytest.param(lambda data: data["conversations"][0]["aims"].update(eve={"aim": "pass_time", "about": "bea",
                                                                          "kept": False}), id="scene-unknown-speaker"),
    pytest.param(lambda data: data["conversations"][0].update(aims=[]), id="scene-aims-not-a-mapping"),
])
def test_a_saved_aim_that_is_not_one_is_rejected(tmp_path: Any, mutate: Any) -> None:
    with pytest.raises(ValueError):
        load_world(saved_with_aim(tmp_path, mutate))


def test_what_a_member_came_for_is_forgotten_when_they_leave() -> None:
    from tavern.social.scenes import leave_conversation
    world = seated(ada="w", bea="e", cid="n")
    assert start_action(world, "ada", aimed("talk", "bea", "pass_time"))["accepted"]
    assert start_action(world, "cid", aimed("join_conversation", "ada", "win_over"))["accepted"]
    leave_conversation(world, actor(world, "cid"))
    scene = conversation_of(world, "ada")
    assert scene is not None and list(scene["aims"]) == ["ada"]
