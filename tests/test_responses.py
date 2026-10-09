"""Answers to what was just done to a guest: which fresh thoughts call for one, and which options give it."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.body.activities import ACTIVITIES
from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.social.responses import RESPONSES, answering, calling
from tavern.social.thoughts import THOUGHTS, think
from social_hall import actor, advance, command, know, spotted_hall


def thought(kind: str, about: str | None = "bea", age: float = 10.0, now: float = 100.0,
            **fields: Any) -> dict[str, Any]:
    """A thought of a kind that began `age` seconds before `now`."""
    rule = THOUGHTS[kind]
    return {"kind": kind, "about": about, "text": "x", "mood": rule.mood, "opinion": rule.opinion,
            "expires_at": now - age + rule.seconds, "source_event": "x", **fields}


def guest(*thoughts: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """A guest with thoughts, a temper and a taste for company."""
    return {"id": "ada", "name": "Ada", "thoughts": list(thoughts), "relations": {},
            "traits": {"temper": 0.5, "sociability": 0.5}, **fields}


def test_the_table_names_only_known_kinds_and_verbs() -> None:
    reasons = [THOUGHTS[kind].reason for kind in RESPONSES]
    assert (set(RESPONSES) <= set(THOUGHTS), all(set(item.verbs) <= set(ACTIVITIES) for item in RESPONSES.values()),
            len(set(reasons)) == len(reasons)) == (True, True, True)


@pytest.mark.parametrize("thoughts, verb, target, now, expected", [
    pytest.param([], "talk", "bea", 100.0, None, id="no-thoughts"),
    pytest.param([thought("lost_at_dice")], "talk", "bea", 100.0, "lost_at_dice", id="a-fresh-thought-and-a-matching-verb"),
    pytest.param([thought("lost_at_dice", age=91.0)], "talk", "bea", 100.0, None, id="past-its-window"),
    pytest.param([thought("lost_at_dice", age=90.0)], "talk", "bea", 100.0, "lost_at_dice", id="at-the-edge-of-its-window"),
    pytest.param([thought("lost_at_dice")], "talk", "cid", 100.0, None, id="the-other-person"),
    pytest.param([thought("lost_at_dice", about=None)], "talk", "bea", 100.0, None, id="a-thought-about-nobody"),
    pytest.param([thought("lost_at_dice")], "drink", "bea", 100.0, None, id="a-verb-that-does-not-answer"),
    pytest.param([thought("lost_at_dice", answered=True)], "talk", "bea", 100.0, None, id="already-answered"),
    pytest.param([thought("lost_at_dice", age=10.0, now=100.0)], "talk", "bea", 1000.0, None, id="expired"),
    pytest.param([thought("chat")], "talk", "bea", 100.0, None, id="a-thought-that-calls-for-no-answer"),
    pytest.param([thought("seat_taken", age=40.0), thought("insulted", age=5.0)], "talk", "bea", 100.0, "insulted",
                 id="two-thoughts-about-one-person-the-latest-first"),
    pytest.param([thought("insulted", age=5.0), thought("seat_taken", age=40.0)], "talk", "bea", 100.0, "insulted",
                 id="the-latest-whatever-the-order"),
    pytest.param([thought("seat_taken", age=40.0), thought("treated", age=5.0)], "give", "bea", 100.0, "treated",
                 id="a-verb-only-one-of-them-answers"),
    pytest.param([thought("treated", age=40.0), thought("seat_taken", age=5.0)], "give", "bea", 100.0, "treated",
                 id="the-latest-that-this-verb-answers"),
    pytest.param([thought("insulted")], "shove", "bea", 100.0, None, id="a-blow-answers-nothing"),
    pytest.param([thought("insulted")], "start_fight", "bea", 100.0, None, id="a-fight-answers-nothing"),
])
def test_a_fresh_thought_is_answered_by_a_matching_action(
        thoughts: list[dict[str, Any]], verb: str, target: str, now: float, expected: str | None) -> None:
    found = answering(guest(*thoughts), now, {"id": f"{verb}:{target}", "verb": verb, "target_id": target})
    assert (found["kind"] if found else None) == expected


def test_a_family_answers_when_any_member_does() -> None:
    family = {"id": "company", "verb": "company", "target_id": None,
              "members": [{"id": "talk:cid", "verb": "talk", "target_id": "cid"},
                          {"id": "talk:bea", "verb": "talk", "target_id": "bea"}]}
    found = answering(guest(thought("lost_at_dice")), 100.0, family)
    assert found is not None and found["about"] == "bea"


def test_calling_lists_the_fresh_thoughts_still_unanswered() -> None:
    thoughts = [thought("lost_at_dice", age=30.0), thought("insulted", age=500.0), thought("chat"),
                thought("seat_taken", about="cid", answered=True), thought("treated", about="cid", age=5.0)]
    assert [item["kind"] for item in calling(guest(*thoughts), 100.0)] == ["lost_at_dice", "treated"]


def table_of_two() -> dict[str, Any]:
    """Ada and Bea sit at the near table, each knowing the places."""
    world = create_world({**spotted_hall(), "table_manners": True}, 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 10)
    for item in world["actors"]:
        know(world, item["id"], "near", "w", "e", "n", "far", "fw", "fe")
    return world


def wronged(world: dict[str, Any], kind: str = "lost_at_dice") -> None:
    """Ada has just had a fresh thought about Bea."""
    think(actor(world, "ada"), kind, world["time"], "Bea beat me", "dice", actor(world, "bea"))


def lost(world: dict[str, Any], who: str = "ada") -> dict[str, Any]:
    """The guest's thought of losing at dice."""
    return next(item for item in actor(world, who)["thoughts"] if item["kind"] == "lost_at_dice")


def test_starting_an_answer_marks_the_thought_answered_and_logs_it() -> None:
    world = table_of_two()
    wronged(world)
    advance(world, 30)
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    found = [item for item in world["events"] if item["type"] == "answered"]
    assert (lost(world)["answered"], [(item["actor_id"], item["message"]) for item in found]) == (
        True, [("ada", "Ada went to answer Bea, who beat them at dice (30 s later)")])


def test_a_thought_is_answered_once() -> None:
    world = table_of_two()
    wronged(world)
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    advance(world, 20)
    start_action(world, "ada", command("wait"))
    start_action(world, "ada", command("talk", "bea"))
    assert len([item for item in world["events"] if item["type"] == "answered" and "at dice" in item["message"]]) == 1


@pytest.mark.parametrize("verb, target", [
    pytest.param("wait", None, id="an-action-that-answers-nothing"),
    pytest.param("sit", "n", id="a-chair"),
])
def test_other_actions_leave_the_thought_unanswered(verb: str, target: str | None) -> None:
    world = table_of_two()
    wronged(world)
    start_action(world, "ada", command(verb, target))
    assert (lost(world).get("answered"), [item for item in world["events"] if item["type"] == "answered"]) == (
        None, [])


def seen_by_ada() -> dict[str, Any]:
    """Ada's observation after Bea beat her at dice 40 s ago."""
    world = table_of_two()
    wronged(world)
    advance(world, 40)
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}


def test_the_briefing_marks_what_answers_and_tells_what_is_unanswered() -> None:
    observation = seen_by_ada()
    told = brief(observation, build_candidates(observation))
    assert ("Unanswered: " in told["situation"] and "Bea, who beat them at dice (40 s ago)" in told["situation"],
            "this answers Bea, who beat them at dice 40 s ago" in told["options"]["talk:bea"]) == (True, True)


def test_nothing_is_said_when_nothing_calls_for_an_answer() -> None:
    world = table_of_two()
    actor(world, "ada")["thoughts"] = []
    observation = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
    told = brief(observation, build_candidates(observation))
    assert ("Unanswered" in told["situation"], any("this answers" in text for text in told["options"].values())) == (
        False, False)


@pytest.mark.parametrize("kind, trait, value, extra", [
    pytest.param("lost_at_dice", "temper", 1.0, 0.4, id="a-wrong-and-a-hot-temper"),
    pytest.param("lost_at_dice", "temper", 0.0, 0.1, id="a-wrong-and-a-cool-temper"),
    pytest.param("treated", "sociability", 1.0, 0.4, id="a-kindness-and-a-sociable-guest"),
    pytest.param("treated", "sociability", 0.0, 0.1, id="a-kindness-and-a-shy-guest"),
])
def test_an_answer_scores_higher_by_temper_for_a_wrong_and_by_sociability_for_a_kindness(
        kind: str, trait: str, value: float, extra: float) -> None:
    world = table_of_two()
    wronged(world, kind)
    mine = actor(world, "ada")
    mine["traits"].update({"temper": 0.5, "sociability": 0.5, trait: value})
    mine["needs"]["social"] = 0.0
    observation = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
    plain = {**observation, "actor": {**observation["actor"], "thoughts": []}}
    talk = [{"id": "talk:bea", "verb": "talk", "target_id": "bea"}]
    assert local_scores(observation, talk)["talk:bea"] - local_scores(plain, talk)["talk:bea"] == pytest.approx(extra)


def test_an_answered_thought_survives_a_save(tmp_path: Any) -> None:
    world = table_of_two()
    wronged(world)
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    path = tmp_path / "world.json"
    save_world(world, path)
    assert lost(load_world(path))["answered"] is True


def test_a_save_without_the_field_still_loads(tmp_path: Any) -> None:
    world = table_of_two()
    wronged(world)
    path = tmp_path / "world.json"
    save_world(world, path)
    assert "answered" not in lost(load_world(path))


@pytest.mark.parametrize("bad", [
    pytest.param("yes", id="answered-is-a-string"),
    pytest.param(1, id="answered-is-a-number"),
])
def test_a_saved_answered_that_is_not_a_bool_is_rejected(tmp_path: Any, bad: Any) -> None:
    world = table_of_two()
    wronged(world)
    path = tmp_path / "world.json"
    save_world(world, path)
    data = json.loads(path.read_text())
    next(item for item in next(who for who in data["actors"] if who["id"] == "ada")["thoughts"]
         if item["kind"] == "lost_at_dice")["answered"] = bad
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_world(path)
