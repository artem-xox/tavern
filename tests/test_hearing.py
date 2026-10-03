"""Sounds in the hall: what activities and events emit, and who hears them how loudly."""

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.activities import ACTIVITIES
from tavern.closing import call_closing
from tavern.hearing import EVENT_SOUNDS, Sound, Stimulus, heard_loudness, salience
from tavern.memory import record_event
from tavern.world import create_world, start_action

HALL = Path(__file__).resolve().parents[1] / "data" / "tavern.json"


def hall(*actors: Mapping[str, Any]) -> dict[str, Any]:
    """Open the real hall with the given visitors and no arrival draws."""
    data = {key: value for key, value in json.loads(HALL.read_text()).items() if key != "arrival"}
    return create_world({**data, "actors": list(actors)})


def guest(actor_id: str, x: int, y: int, **extra: Any) -> dict[str, Any]:
    """Describe a visitor standing on a cell."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": x, "y": y, **extra}


def corridor(*walls: tuple[int, int]) -> dict[str, Any]:
    """Build a bare 9×3 room map with the given wall cells."""
    return create_world({"width": 9, "height": 3, "blocked": [list(cell) for cell in walls], "objects": [],
                         "actors": []})["map"]


def stimulus(cell: Sequence[int], loudness: float = 1.0, reach: float = 10.0, sources: Sequence[str] = (),
             about: Sequence[str] = (), cause: str = "Something happened") -> Stimulus:
    """Build a stimulus heard at the given cell."""
    return {"id": 0, "kind": "noise", "noun": "a noise", "sources": list(sources), "cell": list(cell),
            "loudness": loudness, "reach": reach, "time": 0.0, "about": list(about), "cause": cause,
            "event": None}


@pytest.mark.parametrize("walls, source, listener, reach, expected", [
    pytest.param([], (2, 1), (2, 1), 10.0, 1.0, id="same-cell"),
    pytest.param([], (0, 0), (5, 0), 10.0, 0.5, id="open-air-falloff"),
    pytest.param([], (0, 0), (3, 2), 5.0, pytest.approx(1 - 13 ** 0.5 / 5), id="diagonal-distance"),
    pytest.param([], (0, 0), (8, 0), 4.0, 0.0, id="beyond-reach"),
    pytest.param([(4, 1)], (0, 1), (8, 1), 10.0, pytest.approx(0.1), id="through-one-wall"),
    pytest.param([(3, 1), (5, 1)], (0, 1), (8, 1), 10.0, pytest.approx(0.05), id="through-two-walls"),
    pytest.param([(4, 1)], (0, 0), (8, 0), 10.0, pytest.approx(0.2), id="wall-beside-the-line"),
])
def test_sound_falls_off_with_distance_and_walls(walls: list[tuple[int, int]], source: tuple[int, int],
                                                 listener: tuple[int, int], reach: float, expected: float) -> None:
    assert heard_loudness(corridor(*walls), stimulus(source, reach=reach), listener, 0.5) == expected


def test_heard_loudness_rejects_impossible_damping() -> None:
    with pytest.raises(ValueError, match="damping"):
        heard_loudness(corridor(), stimulus((0, 0)), (1, 0), 1.5)


QUARREL, CHAT = EVENT_SOUNDS["quarrel"], ACTIVITIES["talk"].sound


@pytest.mark.parametrize("sound, source, listener, heard", [
    pytest.param(QUARREL, (5, 6), (17, 3), True, id="quarrel-at-a-table-heard-from-the-wc"),
    pytest.param(QUARREL, (5, 6), (14, 11), True, id="quarrel-heard-across-the-hall"),
    pytest.param(CHAT, (3, 6), (5, 6), True, id="remark-heard-across-the-table"),
    pytest.param(CHAT, (3, 6), (16, 6), False, id="remark-not-heard-across-the-hall"),
    pytest.param(CHAT, (14, 6), (17, 3), False, id="remark-at-the-hearth-not-heard-in-the-wc"),
    pytest.param(ACTIVITIES["play_darts"].sound, (3, 9), (5, 11), True, id="darts-thud-heard-nearby"),
    pytest.param(EVENT_SOUNDS["arrival"], (10, 12), (14, 11), True, id="door-heard-from-a-near-table"),
])
def test_who_hears_what_in_the_hall(sound: Sound, source: tuple[int, int], listener: tuple[int, int],
                                    heard: bool) -> None:
    world = hall(guest("ada", *listener))
    noise = stimulus(source, sound.loudness, sound.reach, sources=["bea"])
    glance = world["rules"]["attention"]["glance"]
    assert (salience(world, noise, world["actors"][0], ()) >= glance) is heard


@pytest.mark.parametrize("listener, noise, friends, factor", [
    pytest.param(guest("ada", 4, 1), stimulus((4, 1)), (), 1.0, id="neutral-listener"),
    pytest.param(guest("ada", 4, 1, traits={}), stimulus((4, 1)), (), 1.0, id="no-traits-count-as-middling"),
    pytest.param(guest("ada", 4, 1, traits={"curiosity": 1.0}), stimulus((4, 1)), (), 1.25, id="curious"),
    pytest.param(guest("ada", 4, 1, traits={"curiosity": 0.0}), stimulus((4, 1)), (), 0.75, id="incurious"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), about=["ada"]), (), 1.5, id="concerns-me"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), cause="Bea shouted at Ada"), (), 1.5, id="names-me"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), cause="Bea shouted at Adalbert"), (), 1.0,
                 id="name-inside-a-longer-word"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), about=["ada", "ada"], cause="Ada!"), (), 1.5,
                 id="duplicate-reasons-count-once"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), sources=["bea"]), ("bea",), 1.5, id="friend-makes-it"),
    pytest.param(guest("ada", 4, 1), stimulus((4, 1), sources=["ada"]), (), 0.0, id="own-noise-unheard"),
])
def test_salience_weighs_relevance_and_temperament(listener: dict[str, Any], noise: Stimulus,
                                                   friends: tuple[str, ...], factor: float) -> None:
    world = create_world({"width": 9, "height": 3, "blocked": [], "objects": [], "actors": [listener]})
    assert salience(world, noise, world["actors"][0], friends) == pytest.approx(factor)


@pytest.mark.parametrize("sound", [
    pytest.param(dict(kind="noise", loudness=1.5, reach=4.0, noun="a noise"), id="too-loud"),
    pytest.param(dict(kind="noise", loudness=-0.1, reach=4.0, noun="a noise"), id="negative-loudness"),
    pytest.param(dict(kind="noise", loudness=0.5, reach=0.0, noun="a noise"), id="no-reach"),
    pytest.param(dict(kind="", loudness=0.5, reach=4.0, noun="a noise"), id="unnamed"),
])
def test_impossible_sounds_fail_loudly(sound: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        Sound(**sound)


@pytest.mark.parametrize("verb, interruptible, sound", [
    pytest.param("sit", True, None, id="sitting"),
    pytest.param("rest", True, None, id="resting"),
    pytest.param("drink", True, None, id="drinking"),
    pytest.param("watch", True, None, id="watching"),
    pytest.param("play_darts", True, "thud", id="darts"),
    pytest.param("wait", True, None, id="waiting"),
    pytest.param("inspect", True, None, id="looking-around"),
    pytest.param("use_toilet", False, None, id="wc-finishes-first"),
    pytest.param("take_beer", False, None, id="pouring-finishes-first"),
    pytest.param("talk", False, "chat", id="chat-ends-by-its-own-rules"),
    pytest.param("leave", False, None, id="leaving"),
])
def test_activity_table_says_what_can_be_interrupted_and_what_sounds(
        verb: str, interruptible: bool, sound: str | None) -> None:
    activity = ACTIVITIES[verb]
    assert (activity.interruptible, activity.sound.kind if activity.sound else None) == (interruptible, sound)


def test_quiet_sounds_never_reach_the_interrupt_threshold() -> None:
    # Even a curious listener named by a chat right beside them only glances at it.
    world = hall(guest("ada", 4, 7, traits={"curiosity": 1.0}))
    for sound in (CHAT, ACTIVITIES["play_darts"].sound, EVENT_SOUNDS["arrival"], EVENT_SOUNDS["action_failed"]):
        noise = stimulus((4, 7), sound.loudness, sound.reach, about=["ada"], cause="Bea talks to Ada")
        assert salience(world, noise, world["actors"][0], ()) < world["rules"]["attention"]["interrupt"]


@pytest.mark.parametrize("kinds, expected", [
    pytest.param([], [], id="no-events"),
    pytest.param(["action_started"], [], id="silent-event"),
    pytest.param(["conversation"], [], id="finished-chat-is-silent"),
    pytest.param(["quarrel"], [("quarrel", ["ada"])], id="single-quarrel"),
    pytest.param(["quarrel", "quarrel"], [("quarrel", ["ada", "bea"])], id="both-quarrelers-one-sound"),
    pytest.param(["arrival"], [("door", ["ada"])], id="arrival"),
    pytest.param(["departure"], [("door", ["ada"])], id="departure"),
    pytest.param(["action_failed"], [("grumble", ["ada"])], id="refusal"),
])
def test_events_emit_stimuli(kinds: list[str], expected: list[tuple[str, list[str]]]) -> None:
    world = hall(guest("ada", 6, 7), guest("bea", 7, 7))
    for kind, actor in zip(kinds, world["actors"]):
        record_event(world, actor, kind, "Ada and Bea did something")
    assert [(item["kind"], item["sources"]) for item in world["stimuli"]] == expected
    assert all(item["cell"] == [6, 7] and item["event"] in kinds for item in world["stimuli"])


@pytest.mark.parametrize("verb, target, cell, about", [
    pytest.param("talk", "bea", [3, 6], ["bea"], id="chat-concerns-the-partner"),
    pytest.param("play_darts", "darts", [3, 9], [], id="darts-thud"),
])
def test_activities_sound_when_the_interaction_begins(verb: str, target: str, cell: list[int],
                                                      about: list[str]) -> None:
    world = hall(guest("ada", *cell), guest("bea", 5, 6))
    if verb == "talk":
        for actor_id, chair in (("ada", "chair-3"), ("bea", "chair-4")):
            assert start_action(world, actor_id, {"id": "sit", "verb": "sit", "target_id": chair})["accepted"]
    assert start_action(world, "ada", {"id": verb, "verb": verb, "target_id": target})["accepted"]
    sound = ACTIVITIES[verb].sound
    assert [(item["kind"], item["sources"], item["cell"], item["about"], item["loudness"])
            for item in world["stimuli"]] == [(sound.kind, ["ada"], cell, about, sound.loudness)]


@pytest.mark.parametrize("since, expected", [
    pytest.param(0.5, [("closing_call", [], [5, 2], "closing")], id="called-on-the-tick-reaching-closing"),
    pytest.param(1.0, [], id="called-only-once"),
])
def test_closing_call_rings_out_from_the_bar(since: float, expected: list[tuple[Any, ...]]) -> None:
    world = hall(guest("ada", 6, 7))
    world.update(closes_at=1.0, time=1.0)
    call_closing(world, since)
    assert [(item["kind"], item["sources"], item["cell"], item["event"]) for item in world["stimuli"]] == expected
