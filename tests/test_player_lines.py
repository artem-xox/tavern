"""The player's typed lines: how a reading becomes a turn, the offline reader, and the claim a line is delivered to."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from social_hall import seated_talk
from test_app import room
from tavern.server.runtime import TavernRuntime
from tavern.mind.turn_view import turn_view
from tavern.social.player_lines import deliver_reading, player_turn, read_as_remark
from tavern.social.scenes import Conversation, conversation_of

TEXT = "Nice weather for a quarrel, Bea."


def played_talk() -> tuple[dict[str, Any], Conversation]:
    """Ada, played and steered, has the next slot of her talk with Bea claimed for her reading."""
    world = seated_talk()
    world["player"] = {"actor_id": "ada", "steering": True}
    scene = conversation_of(world, "ada")
    assert scene is not None
    scene["writing"] = {"turn": len(scene["turns"]), "speaker": "ada", "since": world["time"]}
    return world, scene


def reading(**fields: Any) -> dict[str, Any]:
    """A reading of the text with a topic; the fields given override it."""
    return {"act": "small_talk", "addressee": "bea", "topic": "weather", **fields}


def returns(answer: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    """An outcome that returns the reader's answer."""
    return lambda: answer


def fails() -> dict[str, Any]:
    """An outcome that raises, as a failed request does."""
    raise RuntimeError("the reader is down")


@pytest.mark.parametrize("outcome, to, expected", [
    pytest.param(returns(reading()), "auto", ("small_talk", "bea", "weather"), id="as-read"),
    pytest.param(returns(reading(addressee=None)), "bea", ("small_talk", "bea", "weather"), id="explicit-to-wins"),
    pytest.param(returns(reading()), "everyone", ("small_talk", None, "weather"), id="everyone-to-none"),
    pytest.param(returns(reading(act="dance")), "auto", ("remark", None, "SCENE"), id="unknown-act-is-remark"),
    pytest.param(returns(reading(addressee="zed")), "auto", ("remark", None, "SCENE"),
                 id="addressee-outside-is-remark"),
    pytest.param(returns(reading(act="invite")), "bea", ("remark", "bea", "SCENE"), id="invite-without-kind-is-remark"),
    pytest.param(returns(reading(line="Words the reader made up.")), "auto", ("small_talk", "bea", "weather"),
                 id="reader-returns-its-own-line"),
    pytest.param(fails, "auto", ("remark", None, "SCENE"), id="reader-failed-is-remark"),
    pytest.param(fails, "bea", ("remark", "bea", "SCENE"), id="reader-failed-keeps-the-explicit-to"),
    pytest.param(returns({"act": "small_talk"}), "auto", ("remark", None, "SCENE"), id="reading-lacks-fields"),
])
def test_a_reading_becomes_the_turn_of_the_players_own_words(
        outcome: Callable[[], Any], to: str, expected: tuple[str, str | None, str]) -> None:
    world, scene = played_talk()
    act, addressee, topic = expected
    deliver_reading(world, scene["id"], 0, TEXT, to, outcome)
    assert scene["written"] == {"line": TEXT, "act": act, "addressee": addressee,
                                "topic": scene["topic"] if topic == "SCENE" else topic}


@pytest.mark.parametrize("outcome, misread", [
    pytest.param(returns(reading()), 0, id="a-sound-reading"),
    pytest.param(returns(reading(act="dance")), 1, id="a-refused-reading"),
    pytest.param(fails, 1, id="a-failed-reading"),
])
def test_a_reading_the_world_refuses_is_logged_as_misread(outcome: Callable[[], Any], misread: int) -> None:
    world, scene = played_talk()
    deliver_reading(world, scene["id"], 0, TEXT, "auto", outcome)
    assert sum(event["type"] == "misread" for event in world["events"]) == misread


def end_the_scene(world: dict[str, Any], scene: Conversation) -> None:
    world["conversations"].remove(scene)


def claim_goes_to_bea(world: dict[str, Any], scene: Conversation) -> None:
    scene["writing"]["speaker"] = "bea"


def claim_is_gone(world: dict[str, Any], scene: Conversation) -> None:
    scene["writing"] = None


def another_turn_is_claimed(world: dict[str, Any], scene: Conversation) -> None:
    scene["writing"]["turn"] = 1


def wheel_is_given_back(world: dict[str, Any], scene: Conversation) -> None:
    world["player"]["steering"] = False


@pytest.mark.parametrize("change", [
    pytest.param(end_the_scene, id="scene-ended"),
    pytest.param(claim_goes_to_bea, id="claim-changed-speaker"),
    pytest.param(claim_is_gone, id="claim-gone"),
    pytest.param(another_turn_is_claimed, id="claim-changed-turn"),
    pytest.param(wheel_is_given_back, id="autopilot"),
])
def test_a_reading_for_a_claim_that_changed_is_dropped(change: Callable[[dict[str, Any], Conversation], None]) -> None:
    world, scene = played_talk()
    change(world, scene)
    deliver_reading(world, scene["id"], 0, TEXT, "auto", returns(reading()))
    assert scene["written"] is None


@pytest.mark.parametrize("to, spoke_last_to_ada, expected", [
    pytest.param("auto", True, "bea", id="auto-answers-whoever-spoke-to-the-player"),
    pytest.param("auto", False, None, id="auto-with-nobody-speaking-to-them-is-everyone"),
    pytest.param("everyone", True, None, id="everyone"),
    pytest.param("bea", False, "bea", id="named"),
])
def test_the_offline_reader_makes_a_remark_to_whom_it_was_told(
        to: str, spoke_last_to_ada: bool, expected: str | None) -> None:
    world, scene = played_talk()
    scene["turns"].append({"speaker": "bea", "addressee": "ada" if spoke_last_to_ada else None, "line": "Ada!",
                           "act": "greet", "time": 0.0})
    answer = asyncio.run(read_as_remark(turn_view(world, scene, "ada"), TEXT, to))
    assert answer == {"act": "remark", "addressee": expected, "topic": scene["topic"]}


def turn_of(player: dict[str, Any] | None, claim_by: str | None = None, typed: float | None = None,
            alone: bool = False, speed: float = 1.0) -> Any:
    """The player_turn of Ada's talk with Bea (Ada speaks first), the played guest and what is going on varying."""
    world = seated_talk()
    world.update(player=player, speed=speed)
    scene = conversation_of(world, "ada")
    assert scene is not None
    if player is not None and typed is not None:
        player["typing_at"] = typed
    if claim_by is not None:
        scene["writing"] = {"turn": 0, "speaker": claim_by, "since": world["time"]}
    if alone:
        world["conversations"].remove(scene)
    return player_turn(world), scene


@pytest.mark.parametrize("player, kwargs, state, has_silence", [
    pytest.param(None, {}, None, False, id="no-player"),
    pytest.param({"actor_id": "ada", "steering": True}, {"alone": True}, "none", False, id="in-no-scene"),
    pytest.param({"actor_id": "bea", "steering": True}, {}, "free", False, id="someone-else-next"),
    pytest.param({"actor_id": "ada", "steering": True}, {}, "your_turn", True, id="addressed"),
    pytest.param({"actor_id": "ada", "steering": True}, {"claim_by": "ada"}, "reading", False, id="being-read"),
    pytest.param({"actor_id": "ada", "steering": False}, {}, "none", False, id="autopilot"),
])
def test_the_players_turn_names_what_the_scene_waits_for(
        player: Any, kwargs: dict[str, Any], state: str | None, has_silence: bool) -> None:
    turn, _ = turn_of(player, **kwargs)
    assert (None if turn is None else turn["state"]) == state
    assert turn is None or (turn["silence_at"] is not None) == has_silence


@pytest.mark.parametrize("typed, speed, offset", [
    pytest.param(None, 1.0, 20.0, id="from-the-line-falling-due"),
    pytest.param(None, 2.0, 40.0, id="faster-world-waits-longer"),
    pytest.param(1000.0, 1.0, None, id="a-keystroke-holds-the-turn"),
])
def test_the_turn_passes_in_silence_after_the_wait(typed: float | None, speed: float, offset: float | None) -> None:
    turn, scene = turn_of({"actor_id": "ada", "steering": True}, typed=typed, speed=speed)
    expected = scene["next_turn_at"] + offset if offset is not None else typed + 20.0
    assert turn["silence_at"] == expected


@pytest.mark.parametrize("player, state", [
    pytest.param(None, None, id="no-player-no-turn"),
    pytest.param({"actor_id": "ada", "steering": True}, "your_turn", id="played-guest-is-asked"),
])
def test_the_snapshot_carries_the_players_turn_computed_not_saved(tmp_path: Any, player: Any, state: str | None) -> None:
    runtime = TavernRuntime(room(), tmp_path / "save.json", {"typesafe_api_key": None})
    world = seated_talk()
    world["player"] = player
    runtime.world = world
    shown = runtime.snapshot()["player_turn"]
    assert (None if shown is None else shown["state"]) == state
    assert "player_turn" not in world
