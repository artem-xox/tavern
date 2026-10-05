"""Commitments: a promise made in talk, kept or broken by what the world shows, and what it costs."""

from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world
from tavern.mind.goals import serving
from tavern.social.commitments import PROMISE_LASTS, promise, settle_commitments
from tavern.social.conversation import offered_acts
from tavern.social.thoughts import THOUGHTS, active_thoughts, opinion_of


def chair(chair_id: str, table: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at a table."""
    return {"id": chair_id, "kind": "chair", "name": f"{table} · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": table, "interaction_spots": [[x, y]]}


def hall() -> dict[str, Any]:
    """Two tables, two chairs each: Bea will sit at the first, Ada stands apart."""
    return {"width": 14, "height": 6, "blocked": [], "objects": [
        {"id": "t1", "kind": "table", "name": "West table", "x": 2, "y": 2, "width": 2, "height": 1},
        {"id": "t2", "kind": "table", "name": "East table", "x": 9, "y": 2, "width": 2, "height": 1},
        chair("w1", "t1", 1, 2), chair("w2", "t1", 4, 2), chair("e1", "t2", 8, 2), chair("e2", "t2", 11, 2)],
        "actors": [{"id": "ada", "name": "Ada", "x": 6, "y": 4}, {"id": "bea", "name": "Bea", "x": 1, "y": 2}]}


def guest(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """A guest in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def run(world: dict[str, Any], seconds: float) -> None:
    """Let the evening run."""
    for _ in range(int(seconds * 10)):
        step_world(world, 0.1)


def sit(world: dict[str, Any], actor_id: str, seat: str) -> None:
    """Seat a guest and let them get there."""
    assert start_action(world, actor_id, {"id": f"sit:{seat}", "verb": "sit", "target_id": seat})["accepted"]
    run(world, 30)


def promised() -> dict[str, Any]:
    """Bea sits at the west table; Ada has just promised to come and sit with her."""
    world = create_world(hall())
    sit(world, "bea", "w1")
    promise(world, {"participants": ["ada", "bea"]}, guest(world, "ada"), guest(world, "bea"))  # type: ignore[arg-type]
    return world


def test_a_promise_is_a_commitment_to_come_and_sit_with_the_addressee() -> None:
    world = promised()
    made = world["time"]
    assert world["commitments"] == [{"kind": "sit_with", "from": "ada", "to": "bea", "made_at": made,
                                     "by": made + PROMISE_LASTS}]
    assert [item["kind"] for item in active_thoughts(guest(world, "bea")["thoughts"], made)] == ["promised"]


def test_a_promise_to_nobody_fails_loudly() -> None:
    world = create_world(hall())
    with pytest.raises(ValueError):
        promise(world, {"participants": ["ada"]}, guest(world, "ada"), None)  # type: ignore[arg-type]


def settled(world: dict[str, Any]) -> list[str]:
    """Settle the commitments and list how promises ended, as the world logged it."""
    settle_commitments(world)
    return [event["type"] for event in world["events"] if event["type"].startswith("promise_") and event["type"] != "promise_made"]


def test_a_promise_stays_open_until_it_is_kept_or_due() -> None:
    world = promised()
    run(world, 30)
    assert (settled(world), len(world["commitments"])) == ([], 1)


def test_a_promise_is_kept_when_both_sit_at_one_table() -> None:
    world = promised()
    sit(world, "ada", "w2")
    bea = guest(world, "bea")
    assert (settled(world), world["commitments"]) == (["promise_kept"], [])
    assert opinion_of(bea, "ada", world["time"]) > 0
    assert "kept_word" in [item["kind"] for item in active_thoughts(bea["thoughts"], world["time"])]


def test_a_promise_is_broken_when_it_falls_due_unkept() -> None:
    world = promised()
    run(world, PROMISE_LASTS + 1)
    bea = guest(world, "bea")
    assert (settled(world), world["commitments"]) == (["promise_broken"], [])
    assert opinion_of(bea, "ada", world["time"]) < 0
    assert "let_down" in [item["kind"] for item in active_thoughts(bea["thoughts"], world["time"])]


@pytest.mark.parametrize("leaver, left_alone", [
    pytest.param("ada", "bea", id="the-promiser-goes-home"),
    pytest.param("bea", "ada", id="the-addressee-goes-home"),
])
def test_a_promise_ends_when_either_guest_has_gone(leaver: str, left_alone: str) -> None:
    world = promised()
    world["departed"].append(world["actors"].pop(next(i for i, a in enumerate(world["actors"]) if a["id"] == leaver)))
    result = settled(world)
    stayed = guest(world, left_alone)
    # A promiser who leaves breaks the word; an addressee who leaves voids it, with nobody to let down.
    assert (world["commitments"], result.count("promise_kept")) == ([], 0)
    assert ("let_down" in [item["kind"] for item in active_thoughts(stayed["thoughts"], world["time"])]) == (
        leaver == "ada")


def seen(world: dict[str, Any]) -> dict[str, Any]:
    """Ada's observation."""
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}


@pytest.mark.parametrize("act, expected", [
    pytest.param({"id": "sit:w2", "verb": "sit", "target_id": "w2"}, True, id="a-chair-at-their-table"),
    pytest.param({"id": "sit:e1", "verb": "sit", "target_id": "e1"}, False, id="a-chair-elsewhere"),
    pytest.param({"id": "wait", "verb": "wait", "target_id": None}, False, id="waiting"),
])
def test_an_option_that_keeps_a_promise_serves_it(act: dict[str, Any], expected: bool) -> None:
    assert serving(seen(promised()), act) is expected


def test_the_briefing_tells_a_guest_what_they_promised() -> None:
    from tavern.mind.briefing import brief
    text = brief(seen(promised()), [])["situation"]
    assert "promised Bea" in text


def scene_of(world: dict[str, Any]) -> Any:
    """A scene in which Ada and Bea talk."""
    from tavern.social.scenes import start_conversation
    start_conversation(world, guest(world, "ada"), guest(world, "bea"))
    return world["conversations"][0]


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda world: sit(world, "bea", "w1"), True, id="addressee-seated-elsewhere"),
    pytest.param(lambda world: (sit(world, "bea", "w1"), sit(world, "ada", "w2")), False, id="already-together"),
    pytest.param(lambda world: None, False, id="addressee-with-no-table"),
    pytest.param(lambda world: (sit(world, "bea", "w1"), guest(world, "bea").update(seat_id=None)), True,
                 id="addressee-on-their-feet-with-a-table-of-their-own"),
    pytest.param(lambda world: (sit(world, "bea", "w1"), promise(
        world, {"participants": ["ada", "bea"]}, guest(world, "ada"), guest(world, "bea"))), False,  # type: ignore[arg-type]
                 id="already-promised"),
])
def test_a_promise_is_offered_only_when_there_is_something_to_promise(prepare: Any, expected: bool) -> None:
    world = create_world(hall())
    prepare(world)
    scene = scene_of(world)
    assert ("promise" in offered_acts(world, scene, guest(world, "ada"))) is expected


def test_promised_and_the_two_that_follow_are_thoughts() -> None:
    assert {"promised", "kept_word", "let_down"} <= set(THOUGHTS)


def test_commitments_survive_save_and_load(tmp_path: Path) -> None:
    world = promised()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


@pytest.mark.parametrize("corrupt", [
    pytest.param({"kind": "dance", "from": "ada", "to": "bea", "made_at": 1.0, "by": 91.0}, id="unknown-kind"),
    pytest.param({"kind": "sit_with", "from": "ada", "to": "zed", "made_at": 1.0, "by": 91.0}, id="unknown-guest"),
    pytest.param({"kind": "sit_with", "from": "ada", "to": "ada", "made_at": 1.0, "by": 91.0}, id="to-oneself"),
    pytest.param({"kind": "sit_with", "from": "ada", "to": "bea", "made_at": 91.0, "by": 1.0}, id="due-before-made"),
    pytest.param({"kind": "sit_with", "from": "ada", "to": "bea", "made_at": 1.0}, id="missing-field"),
    pytest.param("sit_with", id="not-an-object"),
])
def test_a_corrupt_saved_commitment_is_refused(corrupt: Any, tmp_path: Path) -> None:
    world = promised()
    world["commitments"][0] = corrupt
    save_world(world, tmp_path / "evening.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "evening.json")
