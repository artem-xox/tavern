"""Turns in a scene: timing, the turn writer port, its scripted offline writer, and both runners."""

import asyncio
from collections.abc import Callable, Mapping
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import Evaluators
from tavern.server.runtime import TavernRuntime
from tavern.evening.lockstep import Pace, run_evening
from tavern.social.scenes import conversation_of
from tavern.mind.scripted import scripted_turn
from tavern.social.turns import check_turn, claim_turns, deliver_turn, reading_time, turn_view
from tavern.hall.world import create_world, start_action, step_world

RULES = {"min_gap": 2.5, "chars_per_second": 15.0}


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def hall() -> dict[str, Any]:
    """Build a 10×6 hall with a three-chair table, a tap Ada knows and Bea cannot see, and three guests."""
    return {"width": 10, "height": 6, "blocked": [[7, y] for y in range(6)], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2, "width": 2, "height": 1},
        chair("west", 2, 2), chair("east", 5, 2), chair("north", 3, 1),
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 9, "y": 0, "interaction_spots": [[8, 0]], "stock": 9},
        {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 5, "interaction_spots": [[0, 4]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 5, "y": 2},
                  {"id": "cid", "name": "Cid", "x": 3, "y": 1}]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks, without anyone deciding."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a guest in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def talking(*joiners: str, social: float = 90.0) -> dict[str, Any]:
    """Seat everyone, let Ada start talking to Bea and the joiners join in."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "west"), ("bea", "east"), ("cid", "north")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
        actor(world, actor_id)["needs"]["social"] = social
    actor(world, "ada")["knowledge"]["objects"]["tap"] = {
        **world["map"]["objects"][4], "last_seen": 0.0}
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    for joiner in joiners:
        assert start_action(world, joiner, command("join_conversation", "ada"))["accepted"]
    return world


@pytest.mark.parametrize("line, seconds", [
    pytest.param("", 2.5, id="empty-line"),
    pytest.param("Aye.", 2.5, id="single-word-reads-at-the-minimum"),
    pytest.param("x" * 60, 4.0, id="long-line-reads-longer"),
    pytest.param("ab" * 75, 10.0, id="repeated-letters-count-each"),
])
def test_reading_time_sets_the_gap_to_the_next_turn(line: str, seconds: float) -> None:
    assert reading_time(line, RULES) == pytest.approx(seconds)


@pytest.mark.parametrize("joiners, speakers", [
    pytest.param((), ["ada", "bea", "ada", "bea"], id="pair-takes-turns"),
    pytest.param(("cid",), ["ada", "bea", "cid", "ada"], id="three-speak-in-turn"),
])
def test_speakers_take_turns_after_each_lines_reading_time(joiners: tuple[str, ...], speakers: list[str]) -> None:
    world = talking(*joiners, social=100.0)
    scene = conversation_of(world, "ada")
    advance(world, 9)
    turns = scene["turns"][:4]
    gaps = [later["time"] - earlier["time"] for earlier, later in zip(turns, turns[1:])]
    assert [turn["speaker"] for turn in turns] == speakers
    assert gaps == pytest.approx([reading_time(turn["line"], world["rules"]["conversation"]) for turn in turns[:3]],
                                 abs=0.11)


def view(**speaker: Any) -> dict[str, Any]:
    """Build a scene view for Bea's second turn in a talk with Ada; keyword arguments change Bea."""
    turns = speaker.pop("turns", [{"speaker": "ada", "addressee": "bea", "line": "Evening!", "act": "greet",
                                    "time": 1.0}])
    me = {"id": "bea", "name": "Bea", "needs": {"thirst": 20, "fatigue": 20, "bladder": 20, "social": 70,
                                               "boredom": 20},
          "traits": {"patience": 0.5}, "visit": {"seconds": 100.0, "beers": 0}, "places": []}
    me.update(speaker)
    return {"conversation": {"id": "conversation-0", "topic": "the inn's beer", "turn": len(turns),
                             "participants": [{"id": "ada", "name": "Ada"}, {"id": "bea", "name": "Bea"}],
                             "turns": turns},
            "speaker": me, "acts": ["greet", "small_talk", "share_place", "joke", "complain", "leave_conversation"],
            "seed": 4}


TAP = {"id": "tap", "kind": "tap", "name": "Tap"}
SHARED = [{"speaker": "bea", "addressee": "ada", "line": "The tap is by the bar.", "act": "share_place", "time": 2.0},
          {"speaker": "ada", "addressee": "bea", "line": "Good to know.", "act": "small_talk", "time": 4.0}]
COMPLAINED = [{"speaker": "bea", "addressee": "ada", "line": "This ale is sour.", "act": "complain", "time": 2.0},
              {"speaker": "ada", "addressee": "bea", "line": "Is it?", "act": "small_talk", "time": 4.0}]


@pytest.mark.parametrize("change, acts", [
    pytest.param({"turns": []}, {"greet"}, id="empty-scene-opens-with-a-greeting"),
    pytest.param({}, {"small_talk", "joke"}, id="single-greeting-gets-small-talk"),
    pytest.param({"needs": {"thirst": 20, "fatigue": 20, "bladder": 85, "social": 70, "boredom": 20}},
                 {"leave_conversation"}, id="pressing-need-takes-them-away"),
    pytest.param({"needs": {"thirst": 20, "fatigue": 86, "bladder": 20, "social": 70, "boredom": 20}, "ailing": True},
                 {"small_talk", "joke"}, id="a-fever-is-no-pressing-need"),
    pytest.param({"needs": {"thirst": 20, "fatigue": 20, "bladder": 20, "social": 5, "boredom": 20}},
                 {"small_talk", "joke"}, id="content-guest-still-answers-once"),
    pytest.param({"needs": {"thirst": 20, "fatigue": 20, "bladder": 20, "social": 5, "boredom": 20},
                  "turns": SHARED}, {"leave_conversation"}, id="had-enough-company"),
    pytest.param({"traits": {"patience": 0.0}, "visit": {"seconds": 900.0, "beers": 3}},
                 {"complain"}, id="tipsy-and-impatient-complains"),
    pytest.param({"traits": {"patience": 0.0}, "visit": {"seconds": 900.0, "beers": 3},
                  "turns": COMPLAINED}, {"small_talk", "joke"}, id="complains-only-once"),
    pytest.param({"places": [TAP]}, {"share_place"}, id="tells-where-places-are"),
    pytest.param({"places": [TAP, TAP], "turns": SHARED}, {"small_talk", "joke"}, id="duplicate-places-told-once"),
])
def test_scripted_writer_chooses_an_act_by_a_seeded_rule(change: dict[str, Any], acts: set[str]) -> None:
    turn = scripted_turn(view(**change))
    assert (turn["act"] in acts, turn["addressee"], turn["topic"], bool(turn["line"])) == (
        True, "ada", "the inn's beer", True), turn


def test_scripted_writer_is_deterministic() -> None:
    assert [scripted_turn(view(turns=SHARED * count)) for count in range(5)] == [
        scripted_turn(view(turns=SHARED * count)) for count in range(5)]


def test_malformed_view_fails_loudly() -> None:
    broken = view()
    del broken["speaker"]["needs"]
    with pytest.raises(KeyError):
        scripted_turn(broken)


@pytest.mark.parametrize("result", [
    pytest.param("Evening!", id="not-a-mapping"),
    pytest.param({}, id="empty-result"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "ada"}, id="missing-topic"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "ada", "topic": "ale", "mood": 1}, id="unknown-field"),
    pytest.param({"line": "", "act": "greet", "addressee": "ada", "topic": "ale"}, id="empty-line"),
    pytest.param({"line": "Hi", "act": "insult", "addressee": "ada", "topic": "ale"}, id="unknown-act"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "bea", "topic": "ale"}, id="talking-to-oneself"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "zed", "topic": "ale"}, id="addressee-not-present"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "ada", "topic": 7}, id="malformed-topic"),
])
def test_invalid_turns_are_rejected(result: Any) -> None:
    with pytest.raises(ValueError):
        check_turn(view(), result)


@pytest.mark.parametrize("result", [
    pytest.param({"line": "Hi", "act": "greet", "addressee": "ada", "topic": "ale"}, id="addressed"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": None, "topic": "ale"}, id="to-everyone"),
])
def test_valid_turns_pass(result: dict[str, Any]) -> None:
    assert check_turn(view(), result) == result


def written(act: str, line: str = "A written line.", addressee: str | None = "bea") -> Callable[[], dict[str, Any]]:
    """Answer a claimed turn with a line by act."""
    return lambda: {"line": line, "act": act, "addressee": addressee, "topic": "the road"}


def test_claimed_turn_waits_for_the_writer_and_its_line_is_spoken() -> None:
    world = talking()
    [(scene_id, turn, seen)] = claim_turns(world)
    advance(world, 1)
    assert (turn, seen["speaker"]["id"], conversation_of(world, "ada")["turns"]) == (0, "ada", [])
    deliver_turn(world, scene_id, turn, written("greet"))
    advance(world, 0.1)
    scene = conversation_of(world, "ada")
    assert [(item["speaker"], item["line"], item["act"]) for item in scene["turns"]] == [
        ("ada", "A written line.", "greet")]
    assert (scene["topic"], claim_turns(world)[0][1]) == ("the road", 1)


def cid_joins(world: dict[str, Any]) -> None:
    """Cid joins after the turn was claimed."""
    assert start_action(world, "cid", command("join_conversation", "ada"))["accepted"]


def bea_leaves(world: dict[str, Any]) -> None:
    """Bea turns to something else after the turn was claimed: the scene ends."""
    assert start_action(world, "bea", command("wait"))["accepted"]


@pytest.mark.parametrize("change", [
    pytest.param(cid_joins, id="someone-joined"),
    pytest.param(bea_leaves, id="scene-ended"),
])
def test_stale_turns_are_dropped(change: Callable[[dict[str, Any]], None]) -> None:
    world = talking()
    [(scene_id, turn, _view)] = claim_turns(world)
    change(world)
    deliver_turn(world, scene_id, turn, written("greet", "A stale line."))
    advance(world, 0.6)
    assert "A stale line." not in [item["line"] for scene in world["conversations"] for item in scene["turns"]]


@pytest.mark.parametrize("outcome", [
    pytest.param(written("insult"), id="invalid-act"),
    pytest.param(lambda: (_ for _ in ()).throw(TimeoutError("slow")), id="writer-failed"),
])
def test_failed_turn_falls_back_to_a_scripted_line(outcome: Callable[[], Any]) -> None:
    world = talking()
    [(scene_id, turn, _view)] = claim_turns(world)
    deliver_turn(world, scene_id, turn, outcome)
    advance(world, 0.6)
    assert [item["act"] for item in conversation_of(world, "ada")["turns"]] == ["greet"]
    assert any(event["type"] == "turn_failed" for event in world["events"])


def test_unanswered_turn_is_scripted_after_a_timeout() -> None:
    world = talking()
    claim_turns(world)
    timeout = world["rules"]["conversation"]["turn_timeout"]
    advance(world, timeout)
    held = list(conversation_of(world, "ada")["turns"])
    advance(world, 0.7)
    assert (held, [item["act"] for item in conversation_of(world, "ada")["turns"]]) == ([], ["greet"])


def spoken(world: dict[str, Any], act: str, line: str = "A written line.") -> None:
    """Let Ada's claimed first turn be a given act, and speak it."""
    [(scene_id, turn, _view)] = claim_turns(world)
    deliver_turn(world, scene_id, turn, written(act, line))
    advance(world, 0.6)


def test_sharing_a_place_teaches_the_listeners() -> None:
    world = talking("cid")
    spoken(world, "share_place", "The tap is past the wall.")
    assert [actor(world, name)["knowledge"]["objects"]["tap"]["heard_from"] for name in ("bea", "cid")] == [
        "ada", "ada"]


@pytest.mark.parametrize("act, relieved", [
    pytest.param("greet", False, id="greeting-is-only-a-start"),
    pytest.param("small_talk", True, id="small-talk-eases-loneliness"),
    pytest.param("joke", True, id="joke-eases-loneliness"),
    pytest.param("share_place", True, id="news-eases-loneliness"),
])
def test_friendly_acts_ease_everyones_wish_for_company(act: str, relieved: bool) -> None:
    world = talking("cid")
    spoken(world, act)
    assert [actor(world, name)["needs"]["social"] < 90 for name in ("ada", "bea", "cid")] == [relieved] * 3


@pytest.mark.parametrize("opinion", [
    pytest.param(0.0, id="tipsy-and-impatient"),
    pytest.param(-40.0, id="tipsy-impatient-and-disliked"),
])
def test_a_complaint_never_ends_in_a_quarrel(opinion: float) -> None:
    world = talking()
    for item in world["actors"]:
        item["visit"]["beers"], item["traits"]["patience"] = 3, 0.0
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": opinion, "familiarity": "acquaintance"}
    spoken(world, "complain", "This ale is piss.")
    assert (len(world["conversations"]), [actor(world, name)["thoughts"] for name in ("ada", "bea")]) == (1, [[], []])


def test_saying_goodbye_leaves_a_bigger_scene_running() -> None:
    world = talking("cid")
    spoken(world, "leave_conversation", "I must be off.")
    advance(world, 2.0)  # the goodbye is heard out first
    assert (conversation_of(world, "ada"), conversation_of(world, "bea")["participants"]) == (
        None, ["bea", "cid"])


@pytest.mark.parametrize("seconds, still_talking", [
    pytest.param(0.5, True, id="just-said-goodbye"),
    pytest.param(2.0, False, id="after-the-last-words-were-heard"),
])
def test_a_guest_finishes_saying_goodbye_before_leaving(seconds: float, still_talking: bool) -> None:
    world = talking("cid")
    spoken(world, "leave_conversation", "I must be off.")
    advance(world, seconds)
    assert (conversation_of(world, "ada") is not None, actor(world, "ada")["action"] is not None) == (
        still_talking, still_talking)


@pytest.mark.parametrize("seconds, scenes", [
    pytest.param(1.5, 1, id="last-line-still-being-heard"),
    pytest.param(2.5, 0, id="last-line-heard"),
])
def test_a_scene_that_has_had_enough_ends_after_its_last_line_is_heard(seconds: float, scenes: int) -> None:
    world = talking()
    scene = world["conversations"][0]
    scene["turns"] += [{"speaker": "ada", "addressee": "bea", "line": "Aye.", "act": "remark", "time": world["time"]}] * 2
    scene["next_turn_at"] = world["time"] + 100
    for item in world["actors"]:
        item["needs"]["social"] = 0.0
    advance(world, seconds)
    assert len(world["conversations"]) == scenes


def exchanged(world: dict[str, Any], lines: int, social: Mapping[str, float]) -> None:
    """Give Ada's scene some lines already spoken, and each guest the given wish for company (the rest 0)."""
    scene = world["conversations"][0]
    scene["turns"] += [{"speaker": "ada", "addressee": "bea", "line": "Aye.", "act": "remark",
                        "time": world["time"]}] * lines
    for item in world["actors"]:
        item["needs"]["social"] = social.get(item["id"], 0.0)


@pytest.mark.parametrize("lines, social, asked", [
    pytest.param(2, {}, 0, id="two-lines-and-everyone-content-asks-no-line-that-would-never-be-spoken"),
    pytest.param(1, {}, 1, id="one-line-is-too-few-to-end-a-scene"),
    pytest.param(2, {"bea": 90.0}, 1, id="someone-still-lonely"),
    pytest.param(2, {"ada": 25.0, "bea": 25.0}, 1, id="wish-at-the-threshold-wants-more"),
    pytest.param(5, {}, 0, id="a-long-scene-is-no-different"),
])
def test_a_scene_about_to_end_asks_the_writer_for_no_further_line(lines: int, social: dict[str, float],
                                                                  asked: int) -> None:
    world = talking()
    exchanged(world, lines, social)
    assert len(claim_turns(world)) == asked


def test_a_scene_whose_guest_is_lonely_again_asks_for_its_line_after_all() -> None:
    world = talking()
    exchanged(world, 2, {})
    assert claim_turns(world) == []
    actor(world, "bea")["needs"]["social"] = 90.0
    assert len(claim_turns(world)) == 1


def test_a_goodbye_being_seen_off_asks_for_no_line_for_the_company_that_is_about_to_change() -> None:
    world = talking("cid")
    spoken(world, "leave_conversation", "I must be off.")
    assert claim_turns(world) == []
    advance(world, 2.0)
    assert [item for item in conversation_of(world, "bea")["participants"]] == ["bea", "cid"]
    assert len(claim_turns(world)) == 1


def keyed_writer(calls: list[float], clock: Callable[[], float]) -> Callable[..., Any]:
    """A fake turn writer: scripted lines marked as written, noting the game time of each request."""
    async def write(seen: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(clock())
        turn = scripted_turn(seen)
        return {**turn, "line": f"~{turn['line']}"}
    return write


async def waiting(view: Any, candidates: Any, config: Any) -> dict[str, float]:
    """Score waiting highest."""
    return {action["id"]: float(action["verb"] == "wait") for action in candidates}


def lockstep_evening() -> tuple[list[dict[str, Any]], list[float], dict[str, Any]]:
    """Play 12 s of a seated pair talking, in lockstep with a one-second virtual writer latency."""
    world, calls = talking(social=100.0), []
    result = asyncio.run(run_evening(world, {"temperature": 0.0}, Random(4), Evaluators(waiting, waiting),
                                     Pace(step=0.1, model_latency=1.0, time_limit=12.0),
                                     keyed_writer(calls, lambda: world["time"])))
    return result.events, calls, world


def test_lockstep_asks_the_writer_and_speaks_after_the_virtual_latency() -> None:
    events, calls, _world = lockstep_evening()
    turns = [event for event in events if event["type"] == "turn"]
    assert turns and all("~" in event["message"] for event in turns)
    # Claimed on the first tick, answered a second later, spoken on the tick after.
    assert (calls[0], turns[0]["time"]) == (pytest.approx(0.1), pytest.approx(1.2))


def test_lockstep_turns_replay_identically() -> None:
    assert lockstep_evening()[0] == lockstep_evening()[0]


def test_live_runtime_asks_the_writer_without_blocking(tmp_path: Path) -> None:
    async def run() -> list[str]:
        calls: list[float] = []
        runtime = TavernRuntime(hall(), tmp_path / "save.json", {"temperature": 0.0},
                                writer=keyed_writer(calls, lambda: runtime.world["time"]))
        runtime.world = talking()
        for _ in range(6):
            runtime.advance(0.1)
            for _ in range(3):
                await asyncio.sleep(0)
        lines = [item["line"] for item in conversation_of(runtime.world, "ada")["turns"]]
        await runtime.close()
        return lines
    lines = asyncio.run(run())
    assert len(lines) == 1 and lines[0].startswith("~")


def failing_writer(error: Exception) -> Callable[..., Any]:
    """A turn writer whose every answer fails with the given error."""
    async def write(seen: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        raise error
    return write


@pytest.mark.parametrize("error", [
    pytest.param(ValueError("not someone else in the conversation"), id="rejected-answer"),
    pytest.param(RuntimeError("model unavailable"), id="writer-failure"),
])
def test_lockstep_falls_back_to_scripted_lines_when_the_writer_fails(error: Exception) -> None:
    world = talking(social=100.0)
    result = asyncio.run(run_evening(world, {"temperature": 0.0}, Random(4), Evaluators(waiting, waiting),
                                     Pace(step=0.1, model_latency=1.0, time_limit=12.0), failing_writer(error)))
    kinds = [event["type"] for event in result.events]
    assert ("turn_failed" in kinds, "turn" in kinds) == (True, True)
