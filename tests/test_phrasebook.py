"""A character's own stock lines: what a phrasebook holds, and which turns it speaks instead of the model."""

from typing import Any

import pytest

from tavern.mind.phrasebook import STOCK_KINDS, check_phrasebook, says_from, stock_turn
from tavern.social.turns import check_turn

BOOK = {"greet": ["Well met, {name}.", "Evening, {name}. Sit if you like."],
        "accept": ["Aye, gladly, {name}."], "decline": ["Not tonight, {name}."],
        "pressed": ["Pardon me, I must step out."], "content": ["I'll leave you to it."],
        "closing": ["Good night, {name}."]}
CALM = {"thirst": 20, "fatigue": 20, "bladder": 20, "social": 70, "boredom": 20}
SAID = [{"speaker": "ada", "addressee": "bea", "line": "Evening!", "act": "greet", "time": 1.0}]


def view(turns: list[dict[str, Any]] | None = None, **speaker: Any) -> dict[str, Any]:
    """A scene view for Bea's next line in a talk with Ada; keyword arguments change Bea, `answer` the answer."""
    turns = SAID if turns is None else turns
    answer = speaker.pop("answer", None)
    known = speaker.pop("known", True)
    me = {"id": "bea", "name": "Bea", "needs": CALM, "traits": {"patience": 0.5}, "visit": {"seconds": 100.0, "beers": 0},
          "places": [], "drunkenness": 0.0, "ailing": False, "hurt": False, "just_fought": [], "aim": None,
          "earlier": [], "news": []}
    me.update(speaker)
    acts = speaker.pop("acts", ["greet", "small_talk", "joke", "complain", "leave_conversation"])
    invitation = {"kind": "darts_together", "from": "ada", "to": "bea"} if answer is not None else None
    if answer is not None:
        acts = ["accept", "decline", "invite"]
    return {"conversation": {"id": "conversation-0", "topic": "the inn's beer", "turn": len(turns), "invitation": invitation,
                             "participants": [{"id": "ada", "name": "Ada" if known else "the lean rider", "known": known},
                                              {"id": "bea", "name": "Bea", "known": True}], "turns": turns},
            "speaker": me, "acts": acts, "invitations": [], "answer": answer, "seed": 4, "closing_called": False}


@pytest.mark.parametrize("data", [
    pytest.param(BOOK, id="every-kind"),
    pytest.param({"greet": ["Well met."]}, id="one-kind"),
    pytest.param({"greet": ["Well met, {name}.", "I'm {me}, by the way."]}, id="both-placeholders"),
])
def test_a_phrasebook_is_checked_into_lines_by_kind(data: dict[str, Any]) -> None:
    assert check_phrasebook(data) == data


@pytest.mark.parametrize("data", [
    pytest.param({}, id="empty-book"),
    pytest.param([], id="not-a-mapping"),
    pytest.param({"insult": ["You fool."]}, id="a-kind-nobody-stocks"),
    pytest.param({"greet": []}, id="no-lines-of-a-kind"),
    pytest.param({"greet": "Well met."}, id="lines-not-a-list"),
    pytest.param({"greet": [7]}, id="a-line-not-text"),
    pytest.param({"greet": ["  "]}, id="a-blank-line"),
    pytest.param({"greet": ["Well met, {who}."]}, id="an-unknown-placeholder"),
    pytest.param({"greet": ["Well met, {name"]}, id="a-broken-placeholder"),
    pytest.param({"greet": ["*nods* Well met."]}, id="a-stage-direction"),
    pytest.param({"greet": ["(smiling) Well met."]}, id="a-bracketed-direction"),
    pytest.param({"greet": ["Well met.\nSit."]}, id="a-line-spanning-lines"),
    pytest.param({"greet": ["x" * 201]}, id="a-line-too-long"),
    pytest.param({"greet": ["Well met.", "Well met."]}, id="a-duplicate-line"),
])
def test_a_malformed_phrasebook_is_rejected(data: Any) -> None:
    with pytest.raises(ValueError):
        check_phrasebook(data)


def test_what_a_phrasebook_may_hold_are_the_moments_that_need_no_thought() -> None:
    assert STOCK_KINDS == ("greet", "accept", "decline", "pressed", "content", "closing")


@pytest.mark.parametrize("change, kind, said", [
    pytest.param({"turns": []}, "greet", "greet", id="the-opening-greeting"),
    pytest.param({"answer": "accept"}, "accept", "accept", id="the-decided-yes"),
    pytest.param({"answer": "decline"}, "decline", "decline", id="the-decided-no"),
    pytest.param({"needs": {**CALM, "bladder": 85}}, "pressed", "leave_conversation", id="a-need-that-presses"),
    pytest.param({"needs": {**CALM, "social": 5}, "turns": [*SAID, {**SAID[0], "speaker": "bea", "act": "small_talk"}]},
                 "content", "leave_conversation", id="company-enough"),
])
def test_a_stock_line_is_spoken_in_the_guests_own_words_for_a_moment_that_needs_no_thought(
        change: dict[str, Any], kind: str, said: str) -> None:
    given = view(**change)
    turn = stock_turn(given, BOOK)
    assert turn is not None
    assert (turn["act"] == said, turn["addressee"], turn["topic"], turn["line"] in {
        text.format(name="Ada", me="Bea") for text in BOOK[kind]}) == (True, "ada", "the inn's beer", True), turn
    assert check_turn(given, turn) == turn


@pytest.mark.parametrize("change, book", [
    pytest.param({"turns": []}, None, id="no-phrasebook"),
    pytest.param({"turns": []}, {"accept": ["Gladly."]}, id="no-lines-of-the-kind"),
    pytest.param({}, BOOK, id="small-talk-is-the-writers"),
    pytest.param({"turns": [], "drunkenness": 0.6}, BOOK, id="drink-changes-how-they-speak"),
    pytest.param({"turns": [], "ailing": True}, BOOK, id="a-fever"),
    pytest.param({"turns": [], "hurt": True}, BOOK, id="wounds"),
    pytest.param({"turns": [], "just_fought": ["ada"]}, BOOK, id="a-fight-just-ended"),
    pytest.param({"turns": [], "acts": ["greet", "invite"],
                  "aim": {"id": "invite:darts_together", "words": "play darts", "acts": ["invite"],
                          "detail": "darts_together", "done": False}}, BOOK, id="they-came-for-something"),
    pytest.param({"answer": "counter:darts_together"}, BOOK, id="a-counter-is-in-their-own-words"),
])
def test_everything_else_is_left_to_the_writer(change: dict[str, Any], book: dict[str, Any] | None) -> None:
    assert stock_turn(view(**change), book) is None


@pytest.mark.parametrize("aim", [
    pytest.param({"id": "pass_time", "words": "pass the time", "acts": ["small_talk"], "detail": None, "done": False},
                 id="passing-the-time"),
    pytest.param({"id": "invite:darts_together", "words": "play darts", "acts": ["invite"], "detail": "darts_together",
                  "done": True}, id="already-done"),
    pytest.param({"id": "tell_news:fever", "words": "tell news", "acts": ["share_news"], "detail": "fever",
                  "done": False}, id="an-aim-whose-acts-are-not-offered-now"),
])
def test_an_aim_that_asks_nothing_of_the_greeting_leaves_it_stock(aim: dict[str, Any]) -> None:
    assert stock_turn(view(turns=[], aim=aim), BOOK) is not None


def test_a_stranger_is_greeted_as_a_friend_would_be() -> None:
    turn = stock_turn(view(turns=[], known=False), {"greet": ["Well met, {name}."]})
    assert turn is not None and turn["line"] == "Well met, friend."


@pytest.mark.parametrize("earlier, expected", [
    pytest.param([], {"Well met, Ada.", "Evening, Ada. Sit if you like."}, id="nothing-said-yet"),
    pytest.param([{"speaker": "Bea", "line": "Well met, Cid."}], {"Evening, Ada. Sit if you like."},
                 id="not-the-same-greeting-twice"),
    pytest.param([{"speaker": "Cid", "line": "Well met, Bea."}], {"Well met, Ada.", "Evening, Ada. Sit if you like."},
                 id="what-others-said-is-not-theirs"),
])
def test_a_guest_does_not_say_the_same_stock_line_twice(earlier: list[dict[str, str]], expected: set[str]) -> None:
    turn = stock_turn(view(turns=[], earlier=[{"scene_id": "c-9", "with": ["Cid"], "lines": earlier}]), BOOK)
    assert turn is not None and turn["line"] in expected


def test_a_guest_with_every_stock_line_used_is_left_to_the_writer() -> None:
    earlier = [{"scene_id": "c-9", "with": ["Cid"], "lines": [{"speaker": "Bea", "line": "Well met, Cid."},
                                                              {"speaker": "Bea", "line": "Evening, Cid. Sit if you like."}]}]
    assert stock_turn(view(turns=[], earlier=earlier), BOOK) is None


def test_the_same_moment_gets_the_same_line() -> None:
    assert [stock_turn(view(turns=[]), BOOK) for _ in range(3)] == [stock_turn(view(turns=[]), BOOK)] * 3


@pytest.mark.parametrize("line, expected", [
    pytest.param("Well met, Cid.", True, id="a-stock-line-to-anyone"),
    pytest.param("Aye, gladly, Ada.", True, id="a-line-of-another-kind"),
    pytest.param("I'll leave you to it.", True, id="a-line-without-a-name"),
    pytest.param("Well met.", False, id="a-line-that-only-resembles-one"),
    pytest.param("", False, id="no-line"),
])
def test_a_line_may_be_told_to_be_one_of_a_phrasebook(line: str, expected: bool) -> None:
    assert says_from(BOOK, line) is expected
