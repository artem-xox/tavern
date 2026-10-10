"""The Claude line writer speaks a guest's stock lines itself and asks the model for the rest."""

import asyncio

from tavern.mind.haiku_turns import claude_writer, turn_question
from test_haiku_turns import GOOD, asking, bea_speaks, scene_world, view_of

BOOK = {"greet": ["Well met, {name}."]}


def test_a_guest_with_a_phrasebook_greets_in_their_own_words_without_asking_the_model() -> None:
    ask = asking(GOOD)
    turn = asyncio.run(claude_writer(ask, {"ada": BOOK})(view_of(scene_world()), {}))
    assert (turn["line"], turn["act"], turn["addressee"], ask.asked) == ("Well met, Bea.", "greet", "bea", [])


def test_a_guest_with_no_phrasebook_is_asked_as_before() -> None:
    ask, world = asking(GOOD), scene_world()
    turn = asyncio.run(claude_writer(ask, {"bea": BOOK})(view_of(world), {}))
    assert (turn, ask.asked) == (GOOD, [turn_question(view_of(world))])


def test_a_moment_the_phrasebook_does_not_cover_is_asked() -> None:
    answer = {**GOOD, "line": "Dear indeed, Ada.", "addressee": "ada"}
    ask, world = asking(answer), scene_world()
    view = bea_speaks(world)
    turn = asyncio.run(claude_writer(ask, {"bea": BOOK})(view, {}))
    assert (turn, ask.asked) == (answer, [turn_question(view)])
