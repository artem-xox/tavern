"""Speech acts: only an act changes the world, never the words; what each act does; which are offered."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from tavern.conversation import ACTS
from tavern.scripted import scripted_turn
from tavern.thoughts import THOUGHTS, familiarity_of, opinion_of, think, thought_mood
from tavern.turns import check_turn, turn_view
from social_hall import actor, advance, know, say, scene_of, seated_talk

NEW_ACTS = ("remark", "introduce", "compliment", "boast", "insult", "apologize", "agree", "disagree", "invite",
            "accept", "decline")


def test_every_act_tells_the_writer_what_it_means() -> None:
    assert all(name in ACTS and len(ACTS[name].meaning) > 30 for name in NEW_ACTS)


def mind(world: dict[str, Any]) -> list[Any]:
    """Everything an act could change: needs, thoughts, opinions, knowledge, purses and actions."""
    keys = ("needs", "thoughts", "relations", "knowledge", "inventory", "action", "visit")
    return [{key: deepcopy(item[key]) for key in keys} for item in world["actors"]] + [
        world.get("invitations"), [scene.get("invitation") for scene in world["conversations"]]]


@pytest.mark.parametrize("line", [
    pytest.param("Hm.", id="single-word"),
    pytest.param("You are a lying, cheating fool, Bea.", id="insulting-words"),
    pytest.param("I'm Ada, by the way. Lovely shawl!", id="introduction-and-praise"),
    pytest.param("Come sit with me, I'll buy you an ale, then we walk home.", id="invitation-words"),
    pytest.param("Sorry. Sorry. Sorry.", id="duplicate-apologies"),
])
def test_words_without_an_act_change_nothing(line: str) -> None:
    worlds = [seated_talk(cards=True), seated_talk(cards=True)]
    for world in worlds:
        know(world, "ada", "tap", "darts", "door")
        actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -40.0, "familiarity": "acquaintance",
                                                   "knows_name": True}
    say(worlds[0], "remark", line)
    say(worlds[1], "remark", "Hm.")
    assert mind(worlds[0]) == mind(worlds[1])


def opinions(world: dict[str, Any]) -> tuple[list[str], float, float]:
    """Bea's thoughts about Ada, her opinion of Ada, and the mood of her thoughts."""
    bea, now = actor(world, "bea"), world["time"]
    return ([item["kind"] for item in bea["thoughts"] if item["about"] == "ada"], opinion_of(bea, "ada", now),
            thought_mood(bea, now))


def patient(value: float) -> Callable[[dict[str, Any]], None]:
    """Give Bea a patience."""
    return lambda world: actor(world, "bea")["traits"].update(patience=value)


def hated(world: dict[str, Any]) -> None:
    """Ada dislikes Bea, so an insult is hers to make."""
    actor(world, "ada")["relations"]["bea"] = {"name": "Bea", "opinion": -40.0, "familiarity": "acquaintance"}


def wronged(world: dict[str, Any]) -> None:
    """Bea quarreled with Ada earlier."""
    think(actor(world, "bea"), "quarrel", world["time"], "Quarreled with Ada", "quarrel", about=actor(world, "ada"))


def nothing(world: dict[str, Any]) -> None:
    """Leave the scene as it is."""


Q = THOUGHTS["quarrel"]


@pytest.mark.parametrize("prepare, act, expected", [
    pytest.param(nothing, "greet", ([], 0.0, 0.0), id="greeting-changes-no-mind"),
    pytest.param(nothing, "compliment", (["compliment"], 8.0, 4.0), id="compliment-warms"),
    pytest.param(patient(0.8), "boast", (["boast_admired"], 3.0, 1.0), id="patient-listener-admires-a-boast"),
    pytest.param(patient(0.1), "boast", (["boast_tiresome"], -4.0, -1.0), id="impatient-listener-tires-of-it"),
    pytest.param(hated, "insult", (["insulted"], -20.0, -6.0), id="insult-hurts"),
    pytest.param(nothing, "agree", (["agreed"], 3.0, 0.0), id="agreement-pleases-a-little"),
    pytest.param(nothing, "disagree", (["disagreed"], -3.0, 0.0), id="disagreement-annoys-a-little"),
    pytest.param(wronged, "apologize", (["quarrel"], Q.opinion / 2, Q.mood / 2), id="apology-halves-a-grudge"),
])
def test_acts_change_what_the_listener_thinks_of_the_speaker(prepare: Callable[[dict[str, Any]], None], act: str,
                                                             expected: tuple[list[str], float, float]) -> None:
    world = seated_talk()
    prepare(world)
    say(world, act)
    kinds, opinion, feeling = opinions(world)
    assert (kinds, opinion, feeling) == (expected[0], pytest.approx(expected[1]), pytest.approx(expected[2]))


def test_a_repeated_apology_softens_only_once_per_grudge() -> None:
    world = seated_talk()
    wronged(world)
    say(world, "apologize")
    say(world, "small_talk")
    say(world, "apologize")
    assert opinions(world)[1] == pytest.approx(Q.opinion / 2)


def test_tipsy_insult_may_end_in_a_quarrel() -> None:
    world = seated_talk()
    hated(world)
    world["rules"].update(quarrel_per_beer=1.0, quarrel_max=1.0)
    for item in world["actors"]:
        item["visit"]["beers"], item["traits"]["patience"] = 3, 0.0
    say(world, "insult", "You drunken sot.")
    assert (scene_of(world), sorted(item["kind"] for item in actor(world, "bea")["thoughts"])) == (
        None, ["insulted", "quarrel"])


def test_introduction_makes_strangers_acquaintances_known_by_name() -> None:
    world = seated_talk(cards=True, cid_joins=True)
    before = [item["name"] for item in turn_view(world, scene_of(world))["conversation"]["participants"]]
    say(world, "introduce", "I'm Ada.", addressee=None)
    bea, cid = actor(world, "bea"), actor(world, "cid")
    assert before == ["Ada", "the stout woman with a pipe", "the grey-bearded man in a green cloak"]
    assert [(item["relations"]["ada"]["name"], item["relations"]["ada"]["knows_name"], familiarity_of(item, "ada"))
            for item in (bea, cid)] == [("Ada", True, "acquaintance")] * 2


def offered(world: dict[str, Any]) -> set[str]:
    """The acts offered to the next speaker in Ada's scene."""
    return set(turn_view(world, scene_of(world))["acts"])


def invited(world: dict[str, Any]) -> None:
    """Ada invites Bea to play darts."""
    know(world, "ada", "darts")
    say(world, "invite", "Darts?", invitation="darts_together")


@pytest.mark.parametrize("prepare, cards, present, absent", [
    pytest.param(nothing, False, {"greet", "remark", "compliment", "boast", "agree", "disagree"},
                 {"insult", "apologize", "introduce", "accept", "decline"}, id="sober-friendly-pair"),
    pytest.param(hated, False, {"insult"}, set(), id="insult-for-someone-disliked"),
    pytest.param(wronged, False, {"apologize"}, set(), id="apology-for-someone-holding-a-grudge"),
    pytest.param(nothing, True, {"introduce"}, set(), id="introduction-among-strangers"),
    pytest.param(lambda world: know(world, "ada", "tap"), False, {"invite"}, set(), id="invitation-with-a-place"),
    pytest.param(invited, False, {"accept", "decline"}, {"invite"}, id="answer-to-a-pending-invitation"),
])
def test_acts_are_offered_by_the_situation(prepare: Callable[[dict[str, Any]], None], cards: bool,
                                           present: set[str], absent: set[str]) -> None:
    world = seated_talk(cards=cards)
    prepare(world)
    acts = offered(world)
    assert (present - acts, absent & acts) == (set(), set())


def view() -> dict[str, Any]:
    """Bea's view of her turn after Ada invited her somewhere, with darts known to Ada."""
    world = seated_talk()
    know(world, "ada", "darts", "tap", "door")
    return turn_view(world, scene_of(world))


@pytest.mark.parametrize("result", [
    pytest.param({"line": "Darts?", "act": "invite", "addressee": "bea", "topic": "darts"}, id="invite-without-kind"),
    pytest.param({"line": "Darts?", "act": "invite", "addressee": "bea", "topic": "darts", "invitation": "dance"},
                 id="unknown-invitation-kind"),
    pytest.param({"line": "Darts?", "act": "invite", "addressee": None, "topic": "darts",
                  "invitation": "darts_together"}, id="invitation-to-nobody-in-particular"),
    pytest.param({"line": "Hi", "act": "greet", "addressee": "bea", "topic": "ale", "invitation": "buy_drink"},
                 id="invitation-on-another-act"),
    pytest.param({"line": "Yes!", "act": "accept", "addressee": "bea", "topic": "ale"}, id="accepting-nothing"),
])
def test_invalid_invitations_are_rejected(result: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        check_turn(view(), result)


def test_a_valid_invitation_passes() -> None:
    result = {"line": "Darts?", "act": "invite", "addressee": "bea", "topic": "darts", "invitation": "darts_together"}
    assert check_turn(view(), result) == result


def pending(kind: str, **needs: float) -> dict[str, Any]:
    """Bea's view of an invitation from Ada, with some of her needs set."""
    world = seated_talk()
    know(world, "ada", "darts", "tap", "door")
    say(world, "invite", "Come along?", invitation=kind)
    seen = turn_view(world, scene_of(world))
    seen["speaker"]["needs"].update(needs)
    return seen


@pytest.mark.parametrize("kind, needs, act", [
    pytest.param("buy_drink", {}, "accept", id="a-free-drink-is-welcome"),
    pytest.param("darts_together", {"boredom": 60}, "accept", id="bored-guest-plays"),
    pytest.param("darts_together", {"boredom": 5}, "decline", id="content-guest-declines-darts"),
    pytest.param("leave_together", {}, "decline", id="just-arrived-guest-stays"),
])
def test_scripted_invitee_answers_a_pending_invitation(kind: str, needs: dict[str, float], act: str) -> None:
    turn = scripted_turn(pending(kind, **needs))
    assert (turn["act"], turn["addressee"]) == (act, "ada")


def test_scripted_stranger_introduces_themselves_after_greeting() -> None:
    world = seated_talk(cards=True)
    say(world, "greet")
    assert scripted_turn(turn_view(world, scene_of(world)))["act"] == "introduce"
