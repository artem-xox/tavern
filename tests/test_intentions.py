"""Intentions: when a guest's mind takes stock, what it is asked, what it may answer, and where it lands."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from tavern.mind.intentions import (IntentionRules, check_intention, deliver_intention, intention_due,
                               intention_question, intention_requests, intention_view, intention_writer,
                               stale_intentions)
from tavern.evening.repetition import repetition_counts
from tavern.hall.memory import record_event
from tavern.social.thoughts import think
from tavern.hall.world import create_world

RULES = IntentionRules(interval=180.0, min_gap=3.0)
CARD = {"id": "edda", "name": "Edda", "sprite": "edda", "occupation": "healer", "background": "Walks the border.",
        "temperament": "Sharp with fools.", "speech": "Brisk.", "quirks": "Sniffs every mug.",
        "secret": "Let a deserter die.", "goal": "Rest by the fire and hear news of the fever.",
        "params": dict.fromkeys(("patience", "temper", "sociability", "courage", "strength", "brawling",
                                 "tolerance", "comfort", "curiosity"), 0.5)}


def hall() -> dict[str, Any]:
    """Build a 10×6 hall with a door and two guests, Ada and Bea."""
    return {"width": 10, "height": 6, "blocked": [], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 5, "interaction_spots": [[0, 4]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 5, "y": 2}]}


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a guest in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def intended(world: dict[str, Any], actor_id: str = "ada", at: float = 10.0) -> dict[str, Any]:
    """Give a guest an intention written at a game time, after their arrival."""
    actor(world, actor_id)["intention"] = {"thought": "A quiet night.", "intention": "Stay for an ale.",
                                           "written_at": at, "trigger": {"kind": "arrival", "text": "Came in",
                                                                         "time": at}}
    return world


def at(world: dict[str, Any], time: float) -> dict[str, Any]:
    """Move the clock to a game time."""
    world["time"] = time
    return world


def heard(world: dict[str, Any], kind: str, time: float) -> dict[str, Any]:
    """Let Ada remember an event of a kind at a game time."""
    world["time"] = time
    record_event(world, actor(world, "ada"), kind, f"Ada: {kind}")
    return world


def thought(world: dict[str, Any], kind: str, time: float) -> dict[str, Any]:
    """Give Ada a thought about Bea at a game time."""
    world["time"] = time
    think(actor(world, "ada"), kind, time, f"{kind} with Bea", f"{kind} event", about=actor(world, "bea"))
    return world


def closing(world: dict[str, Any], closes_at: float, time: float) -> dict[str, Any]:
    """Set a closing time and the clock."""
    world["closes_at"], world["time"] = closes_at, time
    return world


def fresh() -> dict[str, Any]:
    """A hall at 20 s where Ada took stock at 10 s."""
    return at(intended(create_world(hall())), 20.0)


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda: create_world(hall()), "arrival", id="no-intention-yet-is-an-arrival"),
    pytest.param(fresh, None, id="nothing-new-since-written"),
    pytest.param(lambda: heard(fresh(), "interrupted", 15.0), "interrupted", id="interrupt-after-writing"),
    pytest.param(lambda: heard(fresh(), "alerted", 15.0), "alerted", id="alert-after-writing"),
    pytest.param(lambda: heard(at(intended(create_world(hall()), at=10.0), 5.0), "interrupted", 5.0), None,
                 id="interrupt-before-writing-is-old-news"),
    pytest.param(lambda: thought(fresh(), "quarrel", 15.0), "quarrel", id="quarrel-thought"),
    pytest.param(lambda: thought(fresh(), "seat_taken", 15.0), "seat_taken", id="taken-seat-thought"),
    pytest.param(lambda: thought(fresh(), "chat", 15.0), None, id="pleasant-chat-is-not-salient"),
    pytest.param(lambda: heard(fresh(), "conversation", 15.0), None, id="scene-ended-alone-is-not-salient"),
    pytest.param(lambda: heard(fresh(), "left_conversation", 15.0), None, id="left-a-scene-alone-is-not-salient"),
    pytest.param(lambda: heard(heard(fresh(), "interrupted", 12.0), "conversation", 15.0), "interrupted",
                 id="a-scene-ending-after-an-interrupt-changes-nothing"),
    pytest.param(lambda: closing(intended(create_world(hall())), 15.0, 15.0), "closing", id="closing-time"),
    pytest.param(lambda: closing(intended(create_world(hall())), 200.0, 15.0), None, id="closing-still-ahead"),
    pytest.param(lambda: at(intended(create_world(hall())), 190.0), "interval", id="interval-elapsed"),
    pytest.param(lambda: at(intended(create_world(hall())), 189.0), None, id="interval-not-yet"),
])
def test_a_guest_takes_stock_on_arrival_after_salient_events_and_every_interval(
        prepare: Callable[[], dict[str, Any]], expected: str | None) -> None:
    world = prepare()
    trigger = intention_due(world, actor(world, "ada"), RULES)
    assert (trigger and trigger["kind"]) == expected


@pytest.mark.parametrize("interval, min_gap", [
    pytest.param(0.0, 3.0, id="zero-interval"),
    pytest.param(180.0, -1.0, id="negative-gap"),
    pytest.param(float("nan"), 3.0, id="malformed-nan-interval"),
])
def test_invalid_rules_fail_loudly(interval: float, min_gap: float) -> None:
    with pytest.raises(ValueError):
        IntentionRules(interval=interval, min_gap=min_gap)


@pytest.mark.parametrize("pending, next_allowed, expected", [
    pytest.param((), {}, ["ada", "bea"], id="everyone-arrives"),
    pytest.param(("ada",), {}, ["bea"], id="one-request-per-guest"),
    pytest.param(("ada", "ada"), {}, ["bea"], id="duplicates-in-pending"),
    pytest.param((), {"ada": 5.0}, ["bea"], id="ada-waits-for-the-gap"),
    pytest.param((), {"ada": 0.0, "bea": 0.0}, ["ada", "bea"], id="gap-passed"),
])
def test_requests_go_to_guests_due_free_and_past_their_gap(
        pending: tuple[str, ...], next_allowed: dict[str, float], expected: list[str]) -> None:
    world = create_world(hall())
    assert [actor_id for actor_id, _view in intention_requests(world, pending, next_allowed, RULES)] == expected


@pytest.mark.parametrize("change, expected", [
    pytest.param(lambda world: None, [], id="nothing-happened"),
    pytest.param(lambda world: heard(world, "interrupted", 25.0), ["ada"], id="interrupt-overtakes-the-request"),
    pytest.param(lambda world: thought(world, "quarrel", 25.0), ["ada"], id="quarrel-overtakes-the-request"),
    pytest.param(lambda world: at(world, 400.0), [], id="interval-alone-does-not-overtake"),
    pytest.param(lambda world: world["actors"].remove(actor(world, "ada")), ["ada"], id="guest-went-home"),
])
def test_requests_overtaken_by_a_salient_event_are_stale(
        change: Callable[[dict[str, Any]], None], expected: list[str]) -> None:
    world = fresh()
    change(world)
    assert stale_intentions(world, {"ada": 20.0}) == expected


def card_world() -> dict[str, Any]:
    """Ada cast from Edda's card, with a quarrel thought, at 20 s."""
    world = thought(fresh(), "quarrel", 15.0)
    actor(world, "ada")["card"] = CARD
    return at(world, 20.0)


def test_the_question_puts_the_shared_prefix_then_the_card_then_the_moment() -> None:
    world = card_world()
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    question = intention_question("SHARED PREFIX", view)
    assert question["system"][0] == "SHARED PREFIX"
    assert [phrase in question["system"][1] for phrase in ("Edda", "healer", "hear news of the fever")] == [True] * 3
    assert [phrase in question["content"] for phrase in (
        "quarrel with Bea", "Stay for an ale.", "A quiet night.", "sober", "Needs")] == [True] * 5
    assert "Their intention" not in question["content"]
    assert question["schema"]["required"] == ["thought", "intention", "goal", "target"]


@pytest.mark.parametrize("prefix", [
    pytest.param("", id="empty-prefix"),
    pytest.param("   ", id="blank-prefix"),
])
def test_a_question_without_a_shared_prefix_fails_loudly(prefix: str) -> None:
    world = card_world()
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    with pytest.raises(ValueError):
        intention_question(prefix, view)


@pytest.mark.parametrize("answer", [
    pytest.param({"thought": "Bea is a fool.", "intention": "Finish my ale and go home."}, id="plain"),
    pytest.param({"thought": "Bea is a fool.", "intention": "Bea is a fool."}, id="duplicate-texts"),
])
def test_valid_intentions_pass(answer: dict[str, str]) -> None:
    assert check_intention(answer) == answer


@pytest.mark.parametrize("answer", [
    pytest.param({}, id="empty"),
    pytest.param({"thought": "Hm."}, id="single-field"),
    pytest.param({"thought": "Hm.", "intention": "  "}, id="blank-intention"),
    pytest.param({"thought": 3, "intention": "Go."}, id="malformed-thought"),
    pytest.param({"thought": "Hm.", "intention": "Go.", "mood": "sour"}, id="extra-field"),
    pytest.param({"thought": "Hm.", "intention": "x" * 401}, id="too-long"),
    pytest.param(["Hm.", "Go."], id="not-an-object"),
])
def test_invalid_intentions_are_rejected(answer: Any) -> None:
    with pytest.raises(ValueError):
        check_intention(answer)


def ready() -> tuple[dict[str, Any], dict[str, Any]]:
    """Ada's quarrel prompted a request at 20 s; the world has moved on to 22 s."""
    world = card_world()
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    return at(world, 22.0), view


def answer() -> dict[str, str]:
    """A written intention."""
    return {"thought": "Bea crossed me.", "intention": "Drink up and go home."}


def test_a_delivered_intention_is_kept_with_when_it_was_asked_and_why() -> None:
    world, view = ready()
    assert deliver_intention(world, "ada", view, answer, RULES) == 25.0
    assert actor(world, "ada")["intention"] == {**answer(), "goal": None, "written_at": 20.0,
                                                 "trigger": view["trigger"]}
    assert world["events"][-1]["type"] == "intention" and "Drink up and go home." in world["events"][-1]["message"]


def fails() -> dict[str, str]:
    """A writer failure."""
    raise RuntimeError("Claude timed out")


@pytest.mark.parametrize("outcome", [
    pytest.param(fails, id="writer-failed"),
    pytest.param(lambda: {"thought": "Hm."}, id="malformed-answer"),
])
def test_a_failed_intention_keeps_the_old_one_and_waits_an_interval(outcome: Callable[[], Any]) -> None:
    world, view = ready()
    assert deliver_intention(world, "ada", view, outcome, RULES) == 202.0
    assert (actor(world, "ada")["intention"]["intention"], world["events"][-1]["type"]) == (
        "Stay for an ale.", "intention_failed")


def test_an_intention_for_a_guest_who_left_is_dropped() -> None:
    world, view = ready()
    world["actors"].remove(actor(world, "ada"))
    events = list(world["events"])
    deliver_intention(world, "ada", view, answer, RULES)
    assert world["events"] == events


def test_the_writer_asks_the_port_and_checks_the_answer() -> None:
    questions = []

    async def ask(question: Any) -> dict[str, Any]:
        questions.append(question)
        return {**answer(), "goal": "none", "target": None}
    world = card_world()
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    assert asyncio.run(intention_writer("SHARED PREFIX", ask)(view)) == answer()
    assert questions == [intention_question("SHARED PREFIX", view)]


def test_the_card_block_carries_the_persona() -> None:
    world = card_world()
    actor(world, "ada")["card"] = {**CARD, "persona": "Loud and proud.", "catchphrases": ["Tremendous!"],
                                   "obsessions": ["get someone else to pay"], "inspired_by": "A tycoon"}
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    block = intention_question("SHARED PREFIX", view)["system"][1]
    assert all(phrase in block for phrase in ("Loud and proud.", "Tremendous!", "get someone else to pay", "A tycoon"))


@pytest.mark.parametrize("obsession, count, kept", [
    pytest.param(0, 3, 0, id="the-first-obsession"),
    pytest.param(2, 3, 2, id="the-last-obsession"),
    pytest.param(None, 3, None, id="none-of-them"),
    pytest.param(None, 0, None, id="none-for-a-guest-without-any"),
])
def test_an_intention_may_name_the_obsession_it_serves(obsession: int | None, count: int, kept: int | None) -> None:
    assert check_intention({**answer(), "obsession": obsession}, count).get("obsession") == kept


@pytest.mark.parametrize("obsession, count", [
    pytest.param(3, 3, id="index-past-the-end"),
    pytest.param(-1, 3, id="negative-index"),
    pytest.param(0, 0, id="index-for-a-guest-without-obsessions"),
    pytest.param(True, 3, id="a-bool"),
    pytest.param("0", 3, id="a-string"),
    pytest.param(1.5, 3, id="a-fraction"),
])
def test_an_obsession_outside_the_card_is_rejected(obsession: Any, count: int) -> None:
    with pytest.raises(ValueError):
        check_intention({**answer(), "obsession": obsession}, count)


def obsessed() -> dict[str, Any]:
    """Ada's view, from a card with two obsessions."""
    world = card_world()
    actor(world, "ada")["card"] = {**CARD, "obsessions": ["get someone else to pay", "have an audience"]}
    return intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))


def test_the_question_lists_the_obsessions_by_number_and_the_schema_allows_naming_one() -> None:
    question = intention_question("SHARED PREFIX", obsessed())
    assert "0: get someone else to pay" in question["content"] and "1: have an audience" in question["content"]
    assert question["schema"]["properties"]["obsession"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]


def test_a_guest_without_obsessions_is_not_asked_for_one() -> None:
    world = card_world()
    view = intention_view(world, actor(world, "ada"), intention_due(world, actor(world, "ada"), RULES))
    assert "obsession" not in intention_question("SHARED PREFIX", view)["content"].lower()


def test_a_delivered_intention_keeps_the_obsession_it_serves() -> None:
    world, view = ready()
    view["obsessions"] = ["get someone else to pay", "have an audience"]
    deliver_intention(world, "ada", view, lambda: {**answer(), "obsession": 1}, RULES)
    assert actor(world, "ada")["intention"]["obsession"] == 1


def test_the_writer_passes_the_obsession_through_the_boundary() -> None:
    async def ask(question: Any) -> dict[str, Any]:
        return {**answer(), "goal": "none", "target": None, "obsession": 0}
    assert asyncio.run(intention_writer("SHARED PREFIX", ask)(obsessed())) == {**answer(), "obsession": 0}


def test_the_writer_rejects_an_obsession_the_card_does_not_have() -> None:
    async def ask(question: Any) -> dict[str, Any]:
        return {**answer(), "goal": "none", "target": None, "obsession": 2}
    with pytest.raises(ValueError):
        asyncio.run(intention_writer("SHARED PREFIX", ask)(obsessed()))


def pursuing(status: str = "active", obsession: int | None = 0) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ada, who set out to talk to Bea for her first obsession at 10 s, takes stock again at 20 s."""
    world, view = ready()
    view["obsessions"] = ["get someone else to pay", "have an audience"]
    previous = actor(world, "ada")["intention"]
    previous["goal"] = {"kind": "talk_to", "target": "bea", "status": status}
    if obsession is not None:
        previous["obsession"] = obsession
    return world, view


def restated(obsession: int | None) -> Callable[[], dict[str, Any]]:
    """A new answer that sets a different goal for an obsession."""
    goal = {"kind": "sit_with", "target": "bea", "status": "active"}
    return lambda: {**answer(), "goal": goal, **({} if obsession is None else {"obsession": obsession})}


@pytest.mark.parametrize("status, before, after, kept", [
    pytest.param("active", 0, 0, "talk_to", id="the-same-obsession-keeps-the-goal"),
    pytest.param("active", 0, 1, "sit_with", id="another-obsession-sets-a-new-goal"),
    pytest.param("active", 0, None, "sit_with", id="no-obsession-sets-a-new-goal"),
    pytest.param("active", None, None, "sit_with", id="a-goal-without-an-obsession-is-replaced"),
    pytest.param("done", 0, 0, "sit_with", id="a-reached-goal-is-replaced"),
    pytest.param("expired", 0, 0, "sit_with", id="a-lapsed-goal-is-replaced"),
])
def test_a_guest_keeps_an_unreached_goal_while_the_mind_names_the_same_obsession(
        status: str, before: int | None, after: int | None, kept: str) -> None:
    world, view = pursuing(status, before)
    deliver_intention(world, "ada", view, restated(after), RULES)
    assert actor(world, "ada")["intention"]["goal"]["kind"] == kept


def test_the_log_says_which_obsession_an_intention_serves() -> None:
    world, view = ready()
    view["obsessions"] = ["get someone else to pay", "have an audience"]
    deliver_intention(world, "ada", view, lambda: {**answer(), "obsession": 1}, RULES)
    assert world["events"][-1]["message"].endswith("(after: " + view["trigger"]["text"] + "; chasing: have an audience)")


def test_the_evening_metrics_can_still_read_an_intention_that_chases_an_obsession() -> None:
    world, view = ready()
    view["obsessions"] = ["get someone else to pay", "have an audience"]
    deliver_intention(world, "ada", view, lambda: {**answer(), "obsession": 0}, RULES)
    assert repetition_counts(world["events"], 0.8) == {"restated": 0, "repeated": 0}


def talked(lines: int, since: float = 12.0) -> dict[str, Any]:
    """Ada and Bea in a scene of a number of lines, one a second from a game time; Ada took stock at 10 s."""
    world = fresh()
    world["conversations"].append({"id": "conversation-0", "participants": ["ada", "bea"], "topic": "the war",
                                   "turns": [{"speaker": ("ada", "bea")[index % 2], "addressee": None, "line": "Well.",
                                              "act": "remark", "time": since + index} for index in range(lines)]})
    return world


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda: talked(5), "talk", id="five-lines-since-taking-stock"),
    pytest.param(lambda: talked(4), None, id="four-lines-are-not-yet-enough"),
    pytest.param(lambda: talked(5, since=7.0), None, id="lines-before-taking-stock-do-not-count"),
    pytest.param(lambda: talked(0), None, id="a-scene-with-no-lines"),
    # A quarrel inside the talk is part of the stretch: it does not make them take stock line by line.
    pytest.param(lambda: thought(talked(2), "quarrel", 15.0), None, id="a-quarrel-with-the-one-they-talk-to-waits"),
    pytest.param(lambda: thought(talked(5), "insulted", 15.0), "talk", id="an-insult-is-weighed-with-the-talk"),
])
def test_a_guest_takes_stock_again_after_a_stretch_of_talk(prepare: Callable[[], dict[str, Any]],
                                                           expected: str | None) -> None:
    world = prepare()
    trigger = intention_due(world, actor(world, "ada"), RULES)
    assert (trigger and trigger["kind"]) == expected


def test_a_stretch_of_talk_names_who_they_talked_with() -> None:
    world = talked(5)
    assert "Bea" in intention_due(world, actor(world, "ada"), RULES)["text"]
