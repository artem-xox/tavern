"""How guests answer the barkeep's call: what they are told, how it weighs against what they are doing, and their goodbyes."""

from typing import Any

import pytest

from tavern.evening.closing_metrics import closing_counts
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.briefing import brief
from tavern.mind.haiku_turns import turn_question
from tavern.mind.intentions import UNMETERED, IntentionRules, intention_due
from tavern.mind.local_policy import local_scores
from tavern.mind.scripted import scripted_turn
from tavern.social.scenes import conversation_of
from tavern.social.turns import turn_view
from hostile_view import view
from social_hall import actor as guest_of, command, seated_talk
from staff_hall import HOB, advance, opened

RULES = IntentionRules(interval=1000.0, min_gap=3.0)


def called_evening(**fields: Any) -> dict[str, Any]:
    """The repository's hall with Hob, a call at 60 s and the close at 100 s."""
    return opened(HOB, closes_at=100.0, last_call_at=60.0, **fields)


def situation(world: dict[str, Any]) -> str:
    """What Ada is told of her situation."""
    return brief({**observe_actor(world, "ada"), "people": observe_people(world, "ada")}, [])["situation"]


@pytest.mark.parametrize("seconds, said, unsaid", [
    pytest.param(30.0, "", "called closing time", id="before-the-call"),
    pytest.param(65.0, "The barkeep called closing time 5 seconds ago: the inn is about to shut for the night",
                 "The inn has closed for the night", id="after-the-call"),
    pytest.param(105.0, "The inn has closed for the night", "called closing time", id="after-the-close"),
])
def test_the_briefing_tells_where_the_evening_stands(seconds: float, said: str, unsaid: str) -> None:
    world = called_evening()
    advance(world, seconds)
    text = situation(world)
    assert (said in text, unsaid in text) == (True, False)


def weigh(called: float | None, **needs: float) -> dict[str, float]:
    """Local scores for a guest 400 s in with one beer, a half-drunk mug and a tablemate, `called` seconds after the call."""
    observation = view(None, [], called_closing=called)
    observation["actor"].update(visit={"seconds": 400.0, "beers": 1}, inventory={"beer": 1})
    observation["actor"]["needs"].update(thirst=55.0, **needs)
    observation["objects"].append({"id": "door", "kind": "door", "x": 0, "y": 7, "reserved_by": None,
                                   "interaction_spots": [[0, 6]]})
    actions = [command("drink"), command("sit", "w"), command("leave", "door"), command("use_toilet", "wc")]
    observation["objects"].append({"id": "wc", "kind": "toilet", "x": 3, "y": 7, "reserved_by": None,
                                   "interaction_spots": [[3, 6]]})
    scores = local_scores(observation, actions)
    return {action["verb"]: scores[action["id"]] for action in actions}


@pytest.mark.parametrize("called, needs, best", [
    pytest.param(None, {}, "drink", id="before-the-call-they-finish-their-mug"),
    pytest.param(0.0, {}, "drink", id="at-the-call-they-finish-their-mug-first"),
    pytest.param(40.0, {}, "leave", id="forty-seconds-on-they-go-home"),
    pytest.param(100.0, {}, "leave", id="later-still-they-go-home"),
    pytest.param(40.0, {"bladder": 100.0}, "use_toilet", id="a-full-bladder-comes-before-the-door"),
])
def test_after_the_call_guests_finish_what_is_in_hand_and_go_home(called: float | None, needs: dict[str, float],
                                                                  best: str) -> None:
    scores = weigh(called, **needs)
    assert max(scores, key=lambda verb: scores[verb]) == best


def test_the_wish_to_go_home_grows_with_time_since_the_call_and_never_falls() -> None:
    scores = [weigh(called)["leave"] for called in (0.0, 5.0, 10.0, 20.0, 40.0, 80.0)]
    assert scores == sorted(scores) and scores[-1] > scores[0] and scores[-1] <= 0.95


def test_the_call_does_not_change_what_guests_want_before_it() -> None:
    assert weigh(None)["leave"] == weigh(None, social=10.0)["leave"] < 0.4


def taking_stock(world: dict[str, Any]) -> Any:
    """What makes Ada take stock, having written her intention at 10 s."""
    ada = guest_of(world, "ada")
    ada["intention"] = {"thought": "A quiet night.", "intention": "Stay for an ale.", "written_at": 10.0,
                        "trigger": {"kind": "arrival", "text": "Came in", "time": 10.0}}
    trigger = intention_due(world, ada, RULES)
    return trigger and trigger["kind"]


@pytest.mark.parametrize("time, closes_at, last_call_at, expected", [
    pytest.param(20.0, 200.0, 40.0, None, id="before-the-call"),
    pytest.param(45.0, 200.0, 40.0, "last_call", id="after-the-call"),
    pytest.param(45.0, 200.0, None, None, id="an-evening-without-a-call"),
    pytest.param(210.0, 200.0, 40.0, "closing", id="after-the-close-the-close-is-the-news"),
])
def test_a_guest_takes_stock_when_the_barkeep_calls(time: float, closes_at: float, last_call_at: float | None,
                                                    expected: str | None) -> None:
    world = seated_talk()
    world.update(time=time, closes_at=closes_at, last_call_at=last_call_at)
    assert taking_stock(world) == expected


def test_the_call_is_asked_about_whatever_the_budget() -> None:
    assert "last_call" in UNMETERED


def talk_after_call(called: bool, speaker_is_barkeep: bool = False) -> dict[str, Any]:
    """The view of the next turn of Ada and Bea's scene, with or without the call having been made."""
    world = seated_talk()
    world.update(time=70.0, closes_at=120.0, last_call_at=60.0 if called else None)
    return turn_view(world, conversation_of(world, "ada"))


@pytest.mark.parametrize("called", [pytest.param(True, id="called"), pytest.param(False, id="not-yet")])
def test_a_scenes_view_says_whether_closing_time_was_called(called: bool) -> None:
    assert talk_after_call(called)["closing_called"] is called


@pytest.mark.parametrize("called, said", [pytest.param(True, True, id="called"), pytest.param(False, False, id="not-yet")])
def test_the_writers_moment_mentions_the_call_only_after_it(called: bool, said: bool) -> None:
    content = turn_question(talk_after_call(called))["content"]
    assert ("The barkeep has just called closing time" in content) is said


def said_something_before(called: bool) -> dict[str, Any]:
    """A view in which the speaker has already spoken once besides greeting."""
    view_of_turn = talk_after_call(called)
    speaker = view_of_turn["speaker"]["id"]
    view_of_turn["conversation"]["turns"] = [
        {"speaker": speaker, "addressee": None, "act": "greet", "line": "Evening!", "time": 1.0},
        {"speaker": speaker, "addressee": None, "act": "small_talk", "line": "Cold tonight.", "time": 2.0}]
    view_of_turn["speaker"]["needs"]["social"] = 80.0
    view_of_turn["acts"] = {"small_talk": "talk", "leave_conversation": "say goodbye and leave"}
    return view_of_turn


@pytest.mark.parametrize("called, leaves", [
    pytest.param(True, True, id="after-the-call-they-say-goodbye"),
    pytest.param(False, False, id="before-it-they-chat-on"),
])
def test_a_scripted_speaker_says_goodbye_once_the_barkeep_has_called(called: bool, leaves: bool) -> None:
    assert (scripted_turn(said_something_before(called))["act"] == "leave_conversation") is leaves


def test_a_barkeep_on_duty_does_not_say_goodbye_at_his_own_call() -> None:
    view_of_turn = said_something_before(True)
    view_of_turn["speaker"]["on_duty"] = "Oak bar"
    assert scripted_turn(view_of_turn)["act"] != "leave_conversation"


def guest_left(guest_id: str, arrived: float, left: float) -> dict[str, Any]:
    """A guest who went home: arrived and left at game times."""
    return {"id": guest_id, "visit": {"seconds": left - arrived, "beers": 1, "left_at": left}}


@pytest.mark.parametrize("departed, last_call_at, closes_at, expected", [
    pytest.param([], 540.0, 600.0, (0, 0, 0, None), id="nobody-came"),
    pytest.param([guest_left("ada", 0, 545), guest_left("bea", 10, 580), guest_left("cid", 20, 602)], 540.0, 600.0,
                 (3, 2, 1, 602.0), id="two-went-after-the-call-one-was-sent-home"),
    pytest.param([guest_left("ada", 0, 300)], 540.0, 600.0, (0, 0, 0, 300.0), id="gone-before-the-call"),
    pytest.param([guest_left("ada", 0, 540)], 540.0, 600.0, (1, 1, 0, 540.0), id="left-on-the-tick-of-the-call"),
    pytest.param([guest_left("ada", 0, 300), guest_left("bea", 0, 605)], None, 600.0, (0, 0, 1, 605.0),
                 id="an-evening-without-a-call"),
    pytest.param([guest_left("ada", 0, 300), guest_left("bea", 0, 605)], None, None, (0, 0, 0, 605.0),
                 id="an-evening-that-never-closes"),
])
def test_the_call_and_the_close_are_counted(departed: list[dict[str, Any]], last_call_at: float | None,
                                            closes_at: float | None, expected: tuple[Any, ...]) -> None:
    found = closing_counts(departed, last_call_at, closes_at)
    assert (found["present_at_call"], found["left_after_call"], found["sent_home"], found["last_out"]) == expected
    assert (found["last_call_at"], found["closes_at"]) == (last_call_at, closes_at)
