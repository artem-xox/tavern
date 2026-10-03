"""Lines at the tap, the WC and the darts board: joining, moving up, giving up, cutting in."""

from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.evening.decisions import free_to_decide
from tavern.hall.world import create_world, start_action, step_world

HALL = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def hall(guests: Sequence[tuple[str, int, int]], **fields: Any) -> dict[str, Any]:
    """Build the shipped hall with guests placed by hand: (ID, x, y), each sharing `fields`."""
    data = {key: value for key, value in HALL.items() if key != "arrival"}
    return {**data, "actors": [{"id": guest, "name": guest.title(), "x": x, "y": y, **fields}
                               for guest, x, y in guests]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def visitor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]:
    """Return a present visitor by ID."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def place(world: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    """Return a piece of furniture by ID."""
    return next(item for item in world["map"]["objects"] if item["id"] == object_id)


def line(world: Mapping[str, Any], object_id: str) -> list[str]:
    """List who stands in an object's line, front first."""
    return [entry["actor_id"] for entry in place(world, object_id)["queue"]]


def events(world: Mapping[str, Any], kind: str) -> list[tuple[str | None, str]]:
    """List (actor ID, message) of every logged event of one kind."""
    return [(event["actor_id"], event["message"]) for event in world["events"] if event["type"] == kind]


def play(world: dict[str, Any], seconds: float, goals: Mapping[str, Callable[[dict[str, Any]], dict[str, Any] | None]],
         watch: Callable[[dict[str, Any]], None] = lambda world: None) -> None:
    """Advance in 0.1 s ticks; whenever a guest is idle, start the action their goal names, if any."""
    for _ in range(round(seconds * 10)):
        for actor in list(world["actors"]):
            goal = goals.get(actor["id"])
            action = goal(actor) if goal and actor["status"] == "idle" else None
            if action is not None:
                start_action(world, actor["id"], action)
        step_world(world, 0.1)
        watch(world)


def no_overlap(world: dict[str, Any]) -> None:
    """Fail when two visitors share a cell."""
    cells = [(actor["x"], actor["y"]) for actor in world["actors"]]
    assert len(cells) == len(set(cells)), cells


# A guest leaving the WC and one arriving for it, as seen in a live evening: the WC is a dead end
# behind a one-cell doorway, so they used to block each other for minutes.
@pytest.mark.parametrize("leaver, arriver", [
    pytest.param("ann", "bob", id="leaver-sorts-first"),
    pytest.param("zed", "bob", id="arriver-sorts-first"),
])
def test_a_guest_leaving_the_wc_is_never_trapped_by_one_waiting_for_it(leaver: str, arriver: str) -> None:
    world = create_world(hall([(leaver, 17, 3), (arriver, 12, 3)], needs={"bladder": 90}))
    assert start_action(world, leaver, command("use_toilet", "toilet"))["accepted"]
    play(world, 3, {})
    goals = {leaver: lambda actor: None if actor["seat_id"] else command("sit", "chair-1"),
             arriver: lambda actor: None if actor["needs"]["bladder"] < 50 else command("use_toilet", "toilet")}
    play(world, 30, goals, no_overlap)
    assert (visitor(world, leaver)["seat_id"], visitor(world, arriver)["needs"]["bladder"] < 50) == ("chair-1", True)
    assert [message for _, message in events(world, "action_failed")] == []


@pytest.mark.parametrize("guests, longest", [
    pytest.param(1, 0, id="single-guest-walks-straight-up"),
    pytest.param(2, 1, id="two-guests-form-a-short-line"),
    pytest.param(5, 4, id="five-guests-form-a-line"),
])
def test_guests_at_one_tap_form_a_line_without_overlaps(guests: int, longest: int) -> None:
    cells = [(9, 7), (10, 8), (8, 9), (11, 10), (12, 7)][:guests]
    world = create_world(hall([(f"g{index}", x, y) for index, (x, y) in enumerate(cells)], needs={"thirst": 80}))
    for index in range(guests):
        assert start_action(world, f"g{index}", command("take_beer", "tap"))["accepted"]
    lengths: list[int] = []
    seats = {f"g{index}": f"chair-{index + 1}" for index in range(guests)}
    goals = {guest: (lambda seat: lambda actor: command("sit", seat) if actor["inventory"]["beer"] and
                     actor["seat_id"] != seat else None)(seat) for guest, seat in seats.items()}
    play(world, 40, goals, lambda world: (no_overlap(world), lengths.append(len(line(world, "tap")))))
    poured = [visitor(world, f"g{index}")["inventory"]["beer"] for index in range(guests)]
    assert (max(lengths), poured, place(world, "tap")["reserved_by"], line(world, "tap")) == (
        longest, [1] * guests, None, [])


def test_people_in_line_stand_on_its_spots_in_order() -> None:
    world = create_world(hall([("ann", 6, 3), ("bob", 9, 7), ("cid", 10, 8)], needs={"thirst": 80}))
    assert start_action(world, "ann", command("take_beer", "tap"))["accepted"]
    for guest in ("bob", "cid"):
        assert start_action(world, guest, command("take_beer", "tap"))["accepted"]
    play(world, 0.5, {})
    play(world, 5, {})
    spots = place(world, "tap")["queue_spots"]
    assert [(guest, [visitor(world, guest)["x"], visitor(world, guest)["y"]], visitor(world, guest)["status"])
            for guest in line(world, "tap")] == [("bob", spots[0], "queued"), ("cid", spots[1], "queued")]


def test_the_line_moves_up_when_the_front_goes_in() -> None:
    world = create_world(hall([("ann", 3, 9), ("bob", 6, 10), ("cid", 7, 10)], needs={"boredom": 80}))
    for guest in ("ann", "bob", "cid"):
        assert start_action(world, guest, command("play_darts", "darts"))["accepted"]
    play(world, 9, {})
    assert (line(world, "darts"), place(world, "darts")["reserved_by"]) == (["bob", "cid"], "ann")
    play(world, 4, {"ann": lambda actor: command("sit", "chair-5")})
    spots = place(world, "darts")["queue_spots"]
    assert (place(world, "darts")["reserved_by"], line(world, "darts"),
            [visitor(world, "cid")["x"], visitor(world, "cid")["y"]]) == ("bob", ["cid"], spots[0])


def test_a_full_line_turns_newcomers_away() -> None:
    guests = [("ann", 3, 9), ("bob", 6, 10), ("cid", 7, 10), ("dan", 8, 10), ("eve", 9, 10)]
    world = create_world(hall(guests, needs={"boredom": 80}))
    results = [start_action(world, guest, command("play_darts", "darts")) for guest, _, _ in guests]
    assert [result["reason"] for result in results] == [None, None, None, None, "The line for Darts is full"]


@pytest.mark.parametrize("patience, need, waited, asks", [
    pytest.param(0.0, 0, 4.0, False, id="impatient-not-yet"),
    pytest.param(0.0, 0, 6.0, True, id="impatient-runs-out"),
    pytest.param(1.0, 0, 30.0, False, id="patient-keeps-waiting"),
    pytest.param(0.0, 100, 30.0, False, id="urgent-need-keeps-them-waiting"),
    pytest.param(1.0, 100, 76.0, True, id="everyone-runs-out-eventually"),
])
def test_patience_running_out_asks_for_a_new_decision(patience: float, need: float, waited: float,
                                                      asks: bool) -> None:
    world = create_world(hall([("ann", 3, 9), ("bob", 6, 10)], needs={"boredom": need},
                              traits={"patience": patience}))
    for guest in ("ann", "bob"):
        assert start_action(world, guest, command("play_darts", "darts"))["accepted"]
    place(world, "darts")["queue"][0]["since"] -= waited
    assert free_to_decide(world, visitor(world, "bob")) == asks


def test_staying_in_line_keeps_the_place_and_renews_patience() -> None:
    world = create_world(hall([("ann", 3, 9), ("bob", 6, 10), ("cid", 7, 10)], traits={"patience": 0.0}))
    for guest in ("ann", "bob", "cid"):
        assert start_action(world, guest, command("play_darts", "darts"))["accepted"]
    place(world, "darts")["queue"][0]["since"] -= 60
    assert start_action(world, "bob", command("play_darts", "darts"))["accepted"]
    assert (line(world, "darts"), free_to_decide(world, visitor(world, "bob"))) == (["bob", "cid"], False)


def test_giving_up_leaves_the_line_and_the_next_moves_up() -> None:
    world = create_world(hall([("ann", 3, 9), ("bob", 6, 10), ("cid", 7, 10)]))
    for guest in ("ann", "bob", "cid"):
        assert start_action(world, guest, command("play_darts", "darts"))["accepted"]
    assert start_action(world, "bob", command("sit", "chair-5"))["accepted"]
    play(world, 3, {})
    spots = place(world, "darts")["queue_spots"]
    assert (line(world, "darts"), events(world, "left_line"),
            [visitor(world, "cid")["x"], visitor(world, "cid")["y"]]) == (
        ["cid"], [("bob", "Bob left the line for Darts")], spots[0])


def test_cutting_in_line_wrongs_everyone_it_passes() -> None:
    world = create_world(hall([("ann", 3, 9), ("bob", 6, 10), ("cid", 7, 10), ("dan", 6, 12)]))
    for guest in ("ann", "bob", "cid"):
        assert start_action(world, guest, command("play_darts", "darts"))["accepted"]
    assert start_action(world, "dan", command("cut_in_line", "darts"))["accepted"]
    grievances = {guest: visitor(world, guest)["visit"]["grievances"] for guest in ("ann", "bob", "cid", "dan")}
    assert (line(world, "darts"), visitor(world, "dan")["action"]["verb"], grievances) == (
        ["dan", "bob", "cid"], "play_darts",
        {"ann": [], "bob": ["Dan cut in line ahead of me at Darts"],
         "cid": ["Dan cut in line ahead of me at Darts"], "dan": []})


def test_cutting_in_with_nobody_waiting_is_just_using_the_place() -> None:
    world = create_world(hall([("dan", 6, 12)]))
    assert start_action(world, "dan", command("cut_in_line", "darts"))["accepted"]
    assert (place(world, "darts")["reserved_by"], events(world, "line_cut")) == ("dan", [])


@pytest.mark.parametrize("verb, target, reason", [
    pytest.param("cut_in_line", "chair-1", "Target does not support this action", id="no-line-at-a-chair"),
    pytest.param("cut_in_line", None, "Target no longer exists", id="malformed-no-target"),
    pytest.param("cut_in_line", "ghost", "Target no longer exists", id="unknown-target"),
])
def test_cutting_in_needs_a_place_with_a_line(verb: str, target: str | None, reason: str) -> None:
    world = create_world(hall([("dan", 6, 12)]))
    assert start_action(world, "dan", command(verb, target)) == {"accepted": False, "reason": reason}


def test_a_guest_in_line_sees_the_line_even_when_the_place_is_out_of_sight() -> None:
    world = create_world(hall([("ann", 17, 3), ("bob", 12, 2)], needs={"bladder": 80}))
    assert start_action(world, "ann", command("use_toilet", "toilet"))["accepted"]
    assert start_action(world, "bob", command("use_toilet", "toilet"))["accepted"]
    play(world, 1.5, {})
    known = visitor(world, "bob")["knowledge"]["objects"]["toilet"]
    assert [entry["actor_id"] for entry in known["queue"]] == ["bob"]
