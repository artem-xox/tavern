"""Speeches from the stage: who may give one, who hears it, and what the room makes of it."""

from typing import Any

import pytest

from tavern.body.activities import ACTIVITIES
from tavern.body.hearing import EVENT_SOUNDS
from tavern.social.thoughts import active_thoughts
from dice_hall import advance, guest, happened, start, who
from dice_hall import table_hall as bare_hall

STAGE_SPOT = (17, 9)


def table_hall(*actors: dict[str, Any]) -> dict[str, Any]:
    """The real hall; an `intention` given in a guest's description is set on the guest (the world starts with none)."""
    world = bare_hall(*({key: value for key, value in actor.items() if key != "intention"} for actor in actors))
    for actor in actors:
        if "intention" in actor:
            who(world, actor["id"])["intention"] = actor["intention"]
    return world


PERFORMER = {"persona": "A loud showman", "catchphrases": ["Tremendous!"]}
THOUGHT = "Nobody in this room knows who is the greatest man here. I will tell them all."


def with_a_thought(goal: dict[str, Any] | None = None, obsession: int | None = 0) -> dict[str, Any]:
    """An intention of the mind: a long thought, perhaps serving an obsession, perhaps with a goal."""
    intention = {"thought": THOUGHT, "intention": "Make the room listen.", "goal": goal, "written_at": 0.0,
                 "trigger": {"kind": "arrival", "text": "Ada came in", "time": 0.0}}
    return intention if obsession is None else {**intention, "obsession": obsession}


def speaker(**fields: Any) -> dict[str, Any]:
    """Ada, a showman with a public persona, standing at the speaker's spot of the stage."""
    return guest("ada", STAGE_SPOT, card=PERFORMER, intention=with_a_thought(), **fields)


def speech(*listeners: dict[str, Any], seconds: float = 8.0, **fields: Any) -> dict[str, Any]:
    """The hall with Ada giving a speech to the listeners placed by hand, run for a few seconds."""
    world = table_hall(speaker(**fields), *listeners)
    for listener in listeners:
        if "opinion" in listener:
            who(world, listener["id"])["relations"]["ada"] = {"name": "Ada", "opinion": listener["opinion"],
                                                              "familiarity": "acquaintance", "knows_name": True}
    assert start(world, "ada", "give_speech", "stage")["accepted"]
    advance(world, seconds)
    return world


def kinds(world: dict[str, Any], actor_id: str) -> list[str]:
    """The kinds of the thoughts a guest holds now."""
    return [item["kind"] for item in active_thoughts(who(world, actor_id)["thoughts"], world["time"])]


def test_the_hall_has_a_stage_with_one_speaker_spot_on_the_stage_itself() -> None:
    world = table_hall(speaker())
    stage = next(item for item in world["map"]["objects"] if item["kind"] == "stage")
    assert stage["interaction_spots"] == [[stage["x"], stage["y"]]] and stage["walkable"] and stage["facing"] == "west"


def test_giving_a_speech_logs_it_with_the_words() -> None:
    world = speech()
    event = next(item for item in world["events"] if item["type"] == "gave_speech")
    assert event["actor_id"] == "ada" and event["line"]


def test_a_speech_is_louder_than_a_cheer_and_quieter_than_a_brawl() -> None:
    assert EVENT_SOUNDS["dice_won"].loudness < EVENT_SOUNDS["gave_speech"].loudness < EVENT_SOUNDS["fight_started"].loudness


def test_a_speech_is_fun() -> None:
    assert ACTIVITIES["give_speech"].fun == 0.8


@pytest.mark.parametrize("cell, hears", [
    pytest.param((15, 7), True, id="near-the-stage"),
    pytest.param((3, 6), True, id="across-the-hall"),
])
def test_listeners_in_range_keep_the_words(cell: tuple[int, int], hears: bool) -> None:
    world = speech(guest("bea", cell))
    assert bool([item for item in who(world, "bea")["heard"] if item["speaker_id"] == "ada"]) is hears


def test_the_speaker_keeps_their_own_words_too() -> None:
    world = speech(guest("bea", (15, 7)))
    assert who(world, "ada")["heard"]


def rival() -> dict[str, Any]:
    """Cid, who thinks ill of Ada."""
    return guest("cid", (15, 7), opinion=-40.0)


@pytest.mark.parametrize("listener, thought", [
    pytest.param(guest("bea", (15, 7), traits={"sociability": 0.9}), "speech_admired", id="a-sociable-stranger-applauds"),
    pytest.param(rival(), "speech_tiresome", id="a-rival-groans"),
])
def test_listeners_make_up_their_minds_about_the_speaker(listener: dict[str, Any], thought: str) -> None:
    assert thought in kinds(speech(listener), listener["id"])


def test_the_speaker_has_no_opinion_of_their_own_speech() -> None:
    assert kinds(speech(guest("bea", (15, 7))), "ada") == []


# --- the wish to speak: the option, its utility and its sentence ------------------------------------------------

from tavern.hall.world import observe_actor, observe_people  # noqa: E402
from tavern.mind.agents import build_candidates  # noqa: E402
from tavern.mind.local_policy import local_scores  # noqa: E402
from tavern.mind.options import option_text  # noqa: E402

SPEECH = {"id": "give_speech:stage", "verb": "give_speech", "target_id": "stage"}


def seen_by(world: dict[str, Any], actor_id: str = "ada") -> dict[str, Any]:
    """A guest's observation with the people in sight."""
    return {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}


def options_of(world: dict[str, Any]) -> list[str]:
    """The IDs of Ada's concrete options."""
    return [item["id"] for option in build_candidates(seen_by(world)) for item in option.get("members", [option])]


def utility(**fields: Any) -> float:
    """What Ada would score giving a speech, with the traits and drink given."""
    traits = {"sociability": fields.pop("sociability", 0.5), "courage": 0.5, "curiosity": 0.5, "patience": 0.5}
    world = table_hall(speaker(traits=traits, **fields), guest("bea", (15, 7)))
    who(world, "ada")["drunkenness"] = fields.get("drunk", 0.0)
    return local_scores(seen_by(world), [SPEECH])[SPEECH["id"]]


def test_a_free_stage_is_offered() -> None:
    assert SPEECH["id"] in options_of(table_hall(speaker()))


def test_a_stage_in_use_is_not_offered() -> None:
    world = table_hall(guest("ada", (14, 9), card=PERFORMER, intention=with_a_thought()), guest("bea", (15, 9)))
    assert start(world, "bea", "give_speech", "stage")["accepted"]
    advance(world, 1)
    assert SPEECH["id"] not in options_of(world)


@pytest.mark.parametrize("lower, higher", [
    pytest.param({"sociability": 0.1}, {"sociability": 0.9}, id="the-sociable"),
    pytest.param({"drunk": 0.0}, {"drunk": 0.6}, id="the-drunk"),
    pytest.param({"needs": {"boredom": 0, "social": 60}}, {"needs": {"boredom": 100, "social": 60}}, id="the-bored"),
])
def test_the_wish_to_speak_rises_with_sociability_drink_and_boredom(lower: dict[str, Any], higher: dict[str, Any]) -> None:
    assert utility(**lower) < utility(**higher)


def test_the_option_names_the_stage_and_the_whole_room() -> None:
    text = option_text(seen_by(table_hall(speaker())), SPEECH)
    assert "stage" in text and "room" in text


# --- the room cheers --------------------------------------------------------------------------------------------

from tavern.mind.fight_words import TEXTS  # noqa: E402

CHEER = {"id": "cheer", "verb": "cheer", "target_id": None}


@pytest.mark.parametrize("listener, seconds, cheers", [
    pytest.param(guest("bea", (15, 7), traits={"sociability": 0.9}), 8, True, id="the-pleased-may-cheer"),
    pytest.param(guest("bea", (15, 7), traits={"sociability": 0.9}), 100, False, id="the-moment-passed"),
    pytest.param(guest("cid", (15, 7), opinion=-40.0), 8, False, id="the-groaning-do-not"),
])
def test_those_pleased_by_a_speech_may_cheer_while_it_is_fresh(listener: dict[str, Any], seconds: float,
                                                                cheers: bool) -> None:
    world = speech(listener, seconds=seconds)
    options = [item for option in build_candidates(seen_by(world, listener["id"]))
               for item in option.get("members", [option])]
    assert (CHEER["id"] in [item["id"] for item in options]) is cheers


def test_the_cheer_is_told_as_a_cheer_for_the_speech() -> None:
    world = speech(guest("bea", (15, 7), traits={"sociability": 0.9}))
    assert "speech" in TEXTS["cheer"](seen_by(world, "bea"), CHEER)


@pytest.mark.parametrize("seconds, offered", [
    pytest.param(8, False, id="just-spoke"),
    pytest.param(200, True, id="long-ago"),
])
def test_a_speaker_does_not_climb_up_again_at_once(seconds: float, offered: bool) -> None:
    world = speech(guest("bea", (15, 7)), seconds=seconds)
    assert (SPEECH["id"] in options_of(world)) is offered


def test_a_guest_without_a_public_persona_does_not_climb_the_stage() -> None:
    world = table_hall(guest("ada", STAGE_SPOT))
    assert SPEECH["id"] not in options_of(world)


def test_the_speech_ends_with_the_speakers_catchphrase() -> None:
    event = next(item for item in speech().get("events") if item["type"] == "gave_speech")
    assert event["line"].endswith("Tremendous!")


@pytest.mark.parametrize("intention", [
    pytest.param(None, id="nothing-on-their-mind"),
    pytest.param(with_a_thought(obsession=None), id="a-thought-that-serves-no-obsession"),
])
def test_a_performer_climbs_up_only_with_something_to_say(intention: dict[str, Any] | None) -> None:
    world = table_hall(guest("ada", STAGE_SPOT, card=PERFORMER, intention=intention))
    assert SPEECH["id"] not in options_of(world)


def test_a_goal_to_address_the_room_is_something_to_say() -> None:
    goal = {"kind": "address_room", "target": None, "status": "active"}
    world = table_hall(guest("ada", STAGE_SPOT, card=PERFORMER, intention=with_a_thought(goal, obsession=None)))
    assert SPEECH["id"] in options_of(world)


def test_the_speech_voices_the_speakers_thought() -> None:
    event = next(item for item in speech().get("events") if item["type"] == "gave_speech")
    assert "Nobody in this room knows who is the greatest man here." in event["line"]


def test_the_speaker_stays_on_the_stage_a_few_seconds_after_speaking() -> None:
    world = speech(seconds=5.0)
    ada = who(world, "ada")
    assert ada["action"] is not None and ada["action"]["verb"] == "give_speech" and (ada["x"], ada["y"]) == STAGE_SPOT


def test_the_listeners_remember_the_speech_the_moment_it_is_given() -> None:
    world = speech(guest("bea", (15, 7)), seconds=0.5)
    assert any(item["type"] == "heard_speech" and "Nobody in this room" in item["message"] for item in who(world, "bea")["memory"])


def test_the_listeners_turn_to_look_at_the_speaker() -> None:
    world = speech(guest("bea", (15, 7)), seconds=0.5)
    assert who(world, "bea")["gaze"]["cell"] == list(STAGE_SPOT)
