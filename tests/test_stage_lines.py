"""Lines on and at the stage: what waits for a writer, and speaking what it wrote, or scripted words when it fails."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from tavern.social.speeches import PERFORM_WAIT
from tavern.social.stage_lines import HECKLE_WITHIN, deliver_stage, stage_claims, write_scripted_stage
from tavern.social.thoughts import active_thoughts
from dice_hall import advance, guest, start, table_hall, who

STAGE_SPOT = (17, 9)
CARD = {"name": "Ada", "occupation": "showman", "background": "Ada has filled halls all her life.",
        "temperament": "Loud and vain.", "speech": "Superlatives.", "quirks": "Rates everything out of ten.",
        "secret": "She once lost a crowd to a juggler.", "goal": "Be the centre of the room."}
PERFORMER = {**CARD, "persona": "A loud showman", "catchphrases": ["Tremendous!"]}
RIVAL = {**CARD, "name": "Cid", "secret": "He cannot read.", "catchphrases": ["Nonsense."]}
NUMBER = ["Friends, I have built the greatest tavern in history.", "This one. Tremendous!"]


def on_stage(seconds: float = 0.5, rival: bool = True) -> dict[str, Any]:
    """Ada climbs the stage with Cid, who loathes her, in the room; `seconds` pass."""
    world = table_hall(guest("ada", STAGE_SPOT, card=PERFORMER), *([guest("cid", (15, 7), card=RIVAL)] if rival else []))
    if rival:
        who(world, "cid")["relations"]["ada"] = {"name": "Ada", "opinion": -60.0, "familiarity": "acquaintance",
                                               "knows_name": True}
    assert start(world, "ada", "give_speech", "stage")["accepted"]
    advance(world, seconds)
    return world


def claims(world: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """The claims of a kind waiting now."""
    return [item for item in stage_claims(world) if item["kind"] == kind]


def written(lines: list[str]) -> Any:
    """An outcome that hands back the writer's lines."""
    return lambda: lines


def failed() -> Any:
    """An outcome whose request failed."""
    def outcome() -> list[str]:
        raise TimeoutError("the writer did not answer")
    return outcome


def events(world: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    """The logged events of a kind."""
    return [item for item in world["events"] if item["type"] == kind]


def performed(outcome: Any = None) -> dict[str, Any]:
    """Ada's number delivered, written or failed."""
    world = on_stage()
    [claim] = claims(world, "number")
    deliver_stage(world, claim, outcome or written(NUMBER))
    return world


@pytest.mark.parametrize("make, waiting", [
    pytest.param(on_stage, 1, id="up-and-waiting"),
    pytest.param(performed, 0, id="already-given"),
    pytest.param(lambda: on_stage(PERFORM_WAIT + 1.0), 0, id="the-scripted-ones-were-said"),
])
def test_a_performer_on_the_stage_waits_for_a_number(make: Callable[[], dict[str, Any]], waiting: int) -> None:
    assert len(claims(make(), "number")) == waiting


def test_a_number_claim_says_what_to_write_and_holds_scripted_words() -> None:
    [claim] = claims(on_stage(), "number")
    view = claim["view"]
    assert (view["kind"], view["number"]["kind"], view["speaker"]["name"], bool(view["scripted"])) == (
        "number", "pitch", "Ada", True)


@pytest.mark.parametrize("outcome, line", [
    pytest.param(written(NUMBER), " ".join(NUMBER), id="the-written-words"),
    pytest.param(failed(), None, id="scripted-words-when-the-writer-fails"),
])
def test_a_delivered_number_is_spoken_at_once(outcome: Any, line: str | None) -> None:
    [event] = events(performed(outcome), "gave_speech")
    assert event["line"] == line if line else event["line"] and "Tremendous!" in event["line"]


def test_words_for_a_performer_who_left_the_stage_are_dropped() -> None:
    world = on_stage()
    [claim] = claims(world, "number")
    who(world, "ada")["action"] = None
    deliver_stage(world, claim, written(NUMBER))
    assert events(world, "gave_speech") == []


def heckled(outcome: Any = None) -> dict[str, Any]:
    """Ada's number given and Cid's heckle delivered."""
    world = performed()
    [claim] = claims(world, "heckle")
    deliver_stage(world, claim, outcome or written(["Sit down, you fraud!"]))
    return world


@pytest.mark.parametrize("make, heckles, comebacks", [
    pytest.param(on_stage, 0, 0, id="nothing-said-yet"),
    pytest.param(performed, 1, 0, id="a-number-waits-for-its-heckle"),
    pytest.param(heckled, 0, 1, id="a-heckle-waits-for-its-comeback"),
])
def test_what_the_floor_and_the_stage_owe_each_other(make: Callable[[], dict[str, Any]], heckles: int,
                                                     comebacks: int) -> None:
    world = make()
    assert (len(claims(world, "heckle")), len(claims(world, "comeback"))) == (heckles, comebacks)


def test_a_heckle_is_shouted_by_the_heckler_and_stings_the_performer() -> None:
    world = heckled()
    [event] = events(world, "heckled")
    thoughts = [item["kind"] for item in active_thoughts(who(world, "ada")["thoughts"], world["time"])]
    assert (event["actor_id"], event["line"], event["performer_id"], "heckled" in thoughts) == (
        "cid", "Sit down, you fraud!", "ada", True)


def test_the_comeback_answers_the_heckler_and_ends_the_exchange() -> None:
    world = heckled()
    [claim] = claims(world, "comeback")
    deliver_stage(world, claim, written(["Says the man who paid for nothing tonight."]))
    [event] = events(world, "heckle_answered")
    assert (event["actor_id"], event["heckler_id"], stage_claims(world)) == ("ada", "cid", [])


def test_a_heckle_not_shouted_in_time_is_not_owed() -> None:
    world = performed()
    advance(world, HECKLE_WITHIN + 1.0)
    assert claims(world, "heckle") == []


def test_a_failed_heckle_is_shouted_in_scripted_words() -> None:
    [event] = events(heckled(failed()), "heckled")
    assert event["line"].startswith("Get off the stage")


def test_the_scripted_writer_answers_with_the_scripted_words() -> None:
    [claim] = claims(on_stage(), "number")
    assert asyncio.run(write_scripted_stage(claim["view"], {})) == claim["view"]["scripted"]
