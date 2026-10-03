"""What guests in or near a line can choose, how the local policy weighs it, and how it is told."""

import asyncio
import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import build_candidates, choose_action
from tavern.mind.briefing import brief
from tavern.evening.decisions import apply_decision, decision_requests
from tavern.hall.world import create_world, start_action, step_world

LOCAL = {"typesafe_api_key": None, "model": "jev-latest", "timeout": 1.0, "temperature": 0.0}


def wc(waiting: list[str] | None = None, used: bool = True, spots: int = 4, **fields: Any) -> dict[str, Any]:
    """Describe a remembered WC with a line, someone in it if `used`, and who waits, front first."""
    lined = {} if waiting is None else {
        "queue_spots": [[14 - index, 2] for index in range(spots)],
        "queue": [{"actor_id": actor_id, "since": 0.0} for actor_id in waiting]}
    return {"id": "toilet", "kind": "toilet", "name": "WC", "x": 17, "y": 2, "interaction_spots": [[17, 3]],
            "reserved_by": "zed" if used else None, "last_seen": 10.0, **lined, **fields}


def view(item: dict[str, Any], patience: float = 0.5, bladder: float = 60) -> dict[str, Any]:
    """Observe a guest standing at (12, 3) who knows only the WC."""
    return {"actor": {"id": "me", "name": "Me", "x": 12, "y": 3, "inventory": {"beer": 0},
                      "needs": {"thirst": 0, "fatigue": 0, "bladder": bladder, "social": 0, "boredom": 0},
                      "traits": {"patience": patience, "comfort": 0.5, "curiosity": 0.0}},
            "objects": [item], "memory": [], "time": 12.0}


@pytest.mark.parametrize("item, expected", [
    pytest.param(wc(used=False), ["use_toilet:toilet"], id="free-without-a-line"),
    pytest.param(wc(), [], id="busy-without-a-line-is-refused"),
    pytest.param(wc([], used=False), ["use_toilet:toilet"], id="empty-line-free-place"),
    pytest.param(wc([]), ["use_toilet:toilet"], id="busy-place-means-waiting-in-line"),
    pytest.param(wc(["bea"]), ["use_toilet:toilet", "cut_in_line:toilet"], id="single-guest-waiting"),
    pytest.param(wc(["bea", "cid"]), ["use_toilet:toilet", "cut_in_line:toilet"], id="two-guests-waiting"),
    pytest.param(wc(["bea"], spots=1), [], id="line-full"),
    pytest.param(wc(["me"]), ["use_toilet:toilet"], id="front-of-the-line-stays"),
    pytest.param(wc(["bea", "me"], spots=2), ["use_toilet:toilet", "cut_in_line:toilet"],
                 id="behind-someone-in-a-full-line"),
])
def test_a_busy_place_with_a_line_is_offered_as_waiting(item: dict[str, Any], expected: list[str]) -> None:
    assert [action["id"] for action in build_candidates(view(item))] == [*expected, "inspect", "wait"]


@pytest.mark.parametrize("item", [
    pytest.param(wc([], queue={}), id="malformed-line"),
    pytest.param(wc([], queue=[{"since": 0.0}]), id="entry-without-guest"),
    pytest.param(wc(["bea", "bea"]), id="duplicate-guest-in-line"),
    pytest.param(wc([], queue_spots="north"), id="malformed-queue-spots"),
])
def test_malformed_lines_are_rejected(item: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        build_candidates(view(item))


@pytest.mark.parametrize("patience, bladder, queue, expected", [
    pytest.param(1.0, 90, ["bea", "cid", "me"], "use_toilet:toilet", id="patient-and-pressed-waits-on"),
    pytest.param(0.0, 40, ["bea", "cid", "me"], "inspect", id="impatient-and-mild-gives-up"),
    pytest.param(0.0, 90, ["bea", "cid", "me"], "cut_in_line:toilet", id="impatient-and-desperate-cuts-in"),
    pytest.param(0.0, 90, ["bea", "me"], "use_toilet:toilet", id="short-line-is-worth-the-wait"),
    pytest.param(0.0, 90, ["me"], "use_toilet:toilet", id="single-front-of-the-line"),
])
def test_the_local_policy_weighs_the_wait(patience: float, bladder: float, queue: list[str], expected: str) -> None:
    decision = asyncio.run(choose_action(view(wc(queue), patience, bladder), LOCAL, Random(0)))
    assert decision["action"]["id"] == expected


@pytest.mark.parametrize("item, phrase", [
    pytest.param(wc(["me"]), "keep waiting in line for the WC (they are next, while someone uses it)",
                 id="front-of-the-line"),
    pytest.param(wc(["bea", "cid", "me"]), "keep waiting in line for the WC (two people are waiting for the WC "
                 "ahead of them, and someone is using it)", id="two-ahead"),
    pytest.param(wc([]), "walk 5 steps to the WC and wait in line (someone is using it)", id="join-behind-the-user"),
    pytest.param(wc(["bea"]), "walk 5 steps to the WC and wait in line (one person is waiting for the WC, "
                 "and someone is using it)", id="join-behind-one"),
])
def test_the_briefing_tells_the_line_in_plain_words(item: dict[str, Any], phrase: str) -> None:
    observation = view(item)
    assert brief(observation, build_candidates(observation))["options"]["use_toilet:toilet"] == phrase


def test_the_briefing_warns_that_cutting_in_is_resented() -> None:
    observation = view(wc(["bea", "cid"]))
    assert brief(observation, build_candidates(observation))["options"]["cut_in_line:toilet"] == (
        "push to the front of the line for the WC, ahead of the two people waiting, who will resent it")


@pytest.mark.parametrize("queue, sentence", [
    pytest.param(["me"], "They are standing in line for the WC, next to go in, empty-handed.", id="next"),
    pytest.param(["bea", "cid", "me"], "They are standing in line for the WC with two people waiting ahead of "
                 "them, empty-handed.", id="two-ahead"),
    pytest.param(["bea", "cid"], "Places they know: the WC 5 steps away (in use) (two people waiting in line).",
                 id="two-waiting-seen-from-outside-the-line"),
])
def test_the_situation_says_where_they_stand_in_line(queue: list[str], sentence: str) -> None:
    observation = view(wc(queue))
    assert sentence in brief(observation, [])["situation"]


HALL = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


@pytest.mark.parametrize("patience, gives_up", [
    pytest.param(0.0, True, id="impatient-guest-gives-up"),
    pytest.param(1.0, False, id="patient-guest-waits"),
])
def test_an_impatient_guest_gives_up_waiting_for_darts(patience: float, gives_up: bool) -> None:
    data = {key: value for key, value in HALL.items() if key != "arrival"}
    data["actors"] = [{"id": "ann", "name": "Ann", "x": 3, "y": 9, "needs": {"boredom": 90}},
                      {"id": "bob", "name": "Bob", "x": 6, "y": 10, "needs": {"boredom": 0, "fatigue": 50},
                       "traits": {"patience": patience}}]
    world = create_world(data)
    for guest in ("ann", "bob"):
        assert start_action(world, guest, {"id": "play_darts:darts", "verb": "play_darts", "target_id": "darts"})
    rested: dict[str, float] = {"ann": 99.0}
    for _ in range(90):
        step_world(world, 0.1)
        for actor_id, observation in decision_requests(world, [], rested):
            decision = asyncio.run(choose_action(observation, LOCAL, Random(0)))
            actor = next(item for item in world["actors"] if item["id"] == actor_id)
            rested[actor_id] = apply_decision(world, actor, lambda: decision)
    left = [event["actor_id"] for event in world["events"] if event["type"] == "left_line"]
    assert left == (["bob"] if gives_up else [])


@pytest.mark.parametrize("seen_ago, expected", [
    pytest.param(2.0, ["use_toilet:toilet", "cut_in_line:toilet"], id="line-seen-moments-ago"),
    pytest.param(30.0, ["use_toilet:toilet"], id="line-seen-long-ago-has-probably-cleared"),
])
def test_old_sightings_of_a_line_expire(seen_ago: float, expected: list[str]) -> None:
    observation = view(wc(["bea", "cid"], last_seen=12.0 - seen_ago))
    assert [action["id"] for action in build_candidates(observation)] == [*expected, "inspect", "wait"]
