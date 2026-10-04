"""Attention: a glance below the threshold, above it an interrupt with the trigger in the briefing."""

from collections.abc import Callable, Mapping
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.mind.briefing import brief
from tavern.evening.decisions import stale_requests
from tavern.hall.memory import record_event
from tavern.hall.world import create_world, observe_actor, start_action, step_world

HALL = Path(__file__).resolve().parents[1] / "data" / "tavern.json"


def hall(*actors: Mapping[str, Any]) -> dict[str, Any]:
    """Open the real hall with the given visitors and no arrival draws."""
    data = {key: value for key, value in json.loads(HALL.read_text()).items() if key != "arrival"}
    return create_world({**data, "actors": list(actors)})


def guest(actor_id: str, cell: tuple[int, int], **extra: Any) -> dict[str, Any]:
    """Describe a visitor standing on a cell."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": cell[0], "y": cell[1], **extra}


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a visitor."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def start(world: dict[str, Any], verb: str, target: str | None = None) -> None:
    """Start Ada's action, which must begin at once where she stands."""
    assert start_action(world, "ada", {"id": verb, "verb": verb, "target_id": target})["accepted"]
    assert actor(world, "ada")["status"] == "interacting"


def drinking(world: dict[str, Any]) -> None:
    """Ada sits in her chair sipping a beer."""
    start(world, "sit", "chair-4")
    actor(world, "ada")["inventory"]["beer"] = 1
    start(world, "drink")


def quarrel(world: dict[str, Any], *cells: tuple[int, int]) -> None:
    """Bea and Cid, standing on the cells, quarrel loudly."""
    for actor_id, cell in zip(("bea", "cid"), cells):
        world["actors"].append({**actor(hall(guest(actor_id, cell)), actor_id)})
    for actor_id in ("bea", "cid"):
        record_event(world, actor(world, actor_id), "quarrel", "Bea and Cid quarreled about the inn's beer")


def ticks(world: dict[str, Any], count: int) -> None:
    """Advance the world by 0.1 s ticks."""
    for _ in range(count):
        step_world(world, 0.1)


def events(world: Mapping[str, Any], kind: str) -> list[str]:
    """Ada's logged events of a type."""
    return [item["message"] for item in world["events"] if item["actor_id"] == "ada" and item["type"] == kind]


@pytest.mark.parametrize("cell, prepare, noise, facing, verb", [
    pytest.param((5, 6), drinking, ((8, 7), (9, 7)), "east", None, id="drinking-breaks-off"),
    pytest.param((5, 6), lambda world: start(world, "sit", "chair-4"), ((8, 7), (9, 7)), "east", None,
                 id="sitting-breaks-off"),
    pytest.param((3, 9), lambda world: start(world, "play_darts", "darts"), ((8, 7), (9, 7)), "east", None,
                 id="darts-break-off"),
    pytest.param((1, 4), lambda world: start(world, "watch", "window-1"), ((6, 4), (7, 4)), "east", None,
                 id="watching-breaks-off"),
    pytest.param((17, 3), lambda world: start(world, "use_toilet", "toilet"), ((12, 3), (11, 3)), "west",
                 "use_toilet", id="wc-finishes-first"),
    pytest.param((6, 3), lambda world: start(world, "take_beer", "tap"), ((8, 7), (9, 7)), "south", "take_beer",
                 id="pouring-finishes-first"),
])
def test_a_shout_turns_heads_at_once_and_stops_what_can_stop(
        cell: tuple[int, int], prepare: Callable[[dict[str, Any]], None],
        noise: tuple[tuple[int, int], ...], facing: str, verb: str | None) -> None:
    world = hall(guest("ada", cell))
    prepare(world)
    quarrel(world, *noise)
    ticks(world, 1)
    turned = actor(world, "ada")["facing"]
    ticks(world, 4)
    action = actor(world, "ada")["action"]
    assert (turned, action["verb"] if action else None, actor(world, "ada")["emote"]["kind"]) == (
        facing, verb, "alert")


def test_a_guest_in_the_wc_finishes_and_then_knows_why_heads_turned() -> None:
    world = hall(guest("ada", (17, 3)))
    start(world, "use_toilet", "toilet")
    quarrel(world, (12, 3), (11, 3))
    ticks(world, 25)
    assert (events(world, "action_completed"), events(world, "interrupted")) == (["Ada completed use_toilet"], [])
    assert events(world, "alerted") == [
        "Ada heard a loud quarrel near the WC while busy: Bea and Cid quarreled about the inn's beer"]
    assert "Just now: Ada heard a loud quarrel" in brief(observe_actor(world, "ada"), [])["situation"]


def door_opens(world: dict[str, Any]) -> None:
    """Bea comes in at the front door."""
    record_event(world, actor(world, "bea"), "arrival", "Bea came in")


def darts_nearby(world: dict[str, Any]) -> None:
    """Bea starts a round of darts."""
    assert start_action(world, "bea", {"id": "darts", "verb": "play_darts", "target_id": "darts"})["accepted"]


@pytest.mark.parametrize("cell, bea, cause, gaze", [
    pytest.param((5, 11), (10, 12), door_opens, [10, 12], id="door-draws-a-glance"),
    pytest.param((5, 11), (3, 9), darts_nearby, [3, 9], id="darts-draw-a-glance"),
    pytest.param((16, 6), (3, 9), darts_nearby, None, id="darts-unheard-across-the-hall"),
    pytest.param((5, 11), (10, 12), lambda world: None, None, id="silence"),
])
def test_quiet_sounds_only_draw_a_glance(cell: tuple[int, int], bea: tuple[int, int],
                                         cause: Callable[[dict[str, Any]], None], gaze: list[int] | None) -> None:
    world = hall(guest("ada", cell), guest("bea", bea))
    actor(world, "ada")["inventory"]["beer"] = 1
    start(world, "drink")
    cause(world)
    ticks(world, 5)
    looked = actor(world, "ada")["gaze"]
    assert (actor(world, "ada")["action"]["verb"], looked["cell"] if looked else None, events(world, "interrupted")) == (
        "drink", gaze, [])


def test_the_same_shout_never_interrupts_twice() -> None:
    world = hall(guest("ada", (5, 6)))
    drinking(world)
    quarrel(world, (8, 7), (9, 7))
    ticks(world, 1)
    start(world, "drink")
    ticks(world, 31)
    assert (len(events(world, "interrupted")), events(world, "action_completed")[-1]) == (1, "Ada completed drink")


def test_the_briefing_names_the_trigger_while_it_is_fresh() -> None:
    world = hall(guest("ada", (5, 6)))
    drinking(world)
    quarrel(world, (8, 7), (9, 7))
    ticks(world, 1)
    fresh = brief(observe_actor(world, "ada"), [])["situation"]
    ticks(world, 200)
    later = brief(observe_actor(world, "ada"), [])["situation"]
    trigger = ("Just now: Ada broke off and turned toward a loud quarrel near the Dice table: "
               "Bea and Cid quarreled about the inn's beer.")
    assert (trigger in fresh, "broke off" in later, actor(world, "ada")["interrupted_at"]) == (
        True, False, pytest.approx(0.1))


def test_closing_call_interrupts_the_hall() -> None:
    world = hall(guest("ada", (5, 6)))
    world["closes_at"] = 0.05
    drinking(world)
    ticks(world, 1)
    assert (actor(world, "ada")["action"], events(world, "interrupted")) == (None, [
        "Ada broke off and turned toward the innkeeper's call near the Oak bar: "
        "Closing time: the innkeeper calls for every guest to head home"])


def interrupted_at(time: float | None) -> dict[str, Any]:
    """A world in which Ada was last interrupted at a time, or never."""
    world = hall(guest("ada", (5, 6)), guest("bea", (8, 7)))
    actor(world, "ada")["interrupted_at"] = time
    return world


@pytest.mark.parametrize("interrupted, asked, expected", [
    pytest.param(3.0, {}, [], id="nothing-pending"),
    pytest.param(3.0, {"ada": 2.0}, ["ada"], id="asked-before-the-interrupt"),
    pytest.param(3.0, {"ada": 3.0}, [], id="asked-on-the-tick-of-the-interrupt"),
    pytest.param(3.0, {"ada": 4.0}, [], id="asked-after-the-interrupt"),
    pytest.param(None, {"ada": 2.0}, [], id="never-interrupted"),
    pytest.param(3.0, {"ada": 2.0, "bea": 2.0}, ["ada"], id="only-the-interrupted"),
    pytest.param(3.0, {"gone": 2.0}, [], id="visitor-already-left"),
])
def test_an_interrupt_makes_an_earlier_request_stale(interrupted: float | None, asked: dict[str, float],
                                                     expected: list[str]) -> None:
    assert stale_requests(interrupted_at(interrupted), asked) == expected
