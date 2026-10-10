"""The question that has a model write a guest's phrasebook, and what is accepted of its answer."""

from typing import Any

import pytest

from tavern.mind.phrasebook import STOCK_KINDS
from tavern.mind.voice_question import card_hash, voice_lines, voice_question

CARD = {"id": "brida", "name": "Brida", "occupation": "cook at the manor kitchen", "background": "Fed the manor for years.",
        "temperament": "Unflappable and patient.", "speech": "Plain country speech, blunt opinions on food.",
        "quirks": "Judges the bread aloud.", "secret": "She feeds a runaway kitchen boy.",
        "goal": "Sit somewhere warm and hear the gossip.", "sex": "female", "params": {}}
PROMPT = "You write the stock lines of one guest."
LINES = {kind: [f"{kind} one", f"{kind} two", f"{kind} three"] for kind in STOCK_KINDS}


def test_the_model_is_told_who_the_guest_is_and_never_their_secret() -> None:
    question = voice_question(PROMPT, CARD)
    assert question["system"] == [PROMPT]
    assert all(CARD[key] in question["content"] for key in ("name", "occupation", "background", "temperament",
                                                            "speech", "quirks"))
    assert CARD["secret"] not in question["content"] and CARD["goal"] not in question["content"]


def test_the_answer_must_hold_lines_for_every_moment_and_nothing_else() -> None:
    schema = voice_question(PROMPT, CARD)["schema"]
    assert (schema["type"], set(schema["required"]), set(schema["properties"]), schema["additionalProperties"]) == (
        "object", set(STOCK_KINDS), set(STOCK_KINDS), False)


@pytest.mark.parametrize("other", [
    pytest.param({"speech": "Slow and sparing."}, id="a-different-way-of-speaking"),
    pytest.param({"name": "Bridie"}, id="a-different-name"),
])
def test_a_hash_names_what_the_lines_were_written_from(other: dict[str, str]) -> None:
    assert card_hash({**CARD, **other}) != card_hash(CARD)


@pytest.mark.parametrize("other", [
    pytest.param({"secret": "Nothing at all."}, id="the-secret-is-not-in-the-lines"),
    pytest.param({"goal": "Go home early."}, id="nor-is-the-goal"),
])
def test_a_hash_ignores_what_the_lines_never_read(other: dict[str, str]) -> None:
    assert card_hash({**CARD, **other}) == card_hash(CARD)


def test_an_answer_with_enough_lines_of_every_moment_is_the_phrasebook() -> None:
    assert voice_lines(LINES, 3) == (LINES, [])


@pytest.mark.parametrize("kind, line", [
    pytest.param("accept", "Fetch the darts, {name}.", id="a-yes-naming-a-game"),
    pytest.param("decline", "Not tonight, {name}, my luck is spent.", id="a-no-naming-luck"),
    pytest.param("pressed", "Pardon me, I need the yard.", id="a-goodbye-naming-the-need"),
    pytest.param("greet", "Back again, {name}?", id="a-greeting-that-assumes-the-person-is-known"),
    pytest.param("closing", "Good night, my wife is waiting.", id="a-family-nobody-gave-the-guest"),
])
def test_a_line_that_names_what_it_must_not_is_left_out_and_reported(kind: str, line: str) -> None:
    answer = {**LINES, kind: [*LINES[kind], line]}
    assert voice_lines(answer, 3) == (LINES, [line])


@pytest.mark.parametrize("answer", [
    pytest.param({**LINES, "greet": ["greet one", "greet two"]}, id="too-few-lines-of-a-moment"),
    pytest.param({key: value for key, value in LINES.items() if key != "closing"}, id="a-moment-missing"),
    pytest.param({**LINES, "greet": ["*bows*", "greet two", "greet three"]}, id="a-stage-direction"),
    pytest.param("greet: Well met", id="not-an-object"),
    pytest.param({**LINES, "accept": ["Fetch the darts, {name}.", "accept two", "accept three"]},
                 id="a-yes-that-names-what-was-offered"),
    pytest.param({**LINES, "decline": ["accept one", "No game for me, {name}.", "accept three"]},
                 id="a-no-that-names-what-was-offered"),
    pytest.param({**LINES, "pressed": ["pressed one", "Pardon me, I need the yard.", "pressed three"]},
                 id="a-goodbye-that-names-the-need"),
])
def test_a_poor_answer_is_rejected(answer: Any) -> None:
    with pytest.raises(ValueError):
        voice_lines(answer, 3)
