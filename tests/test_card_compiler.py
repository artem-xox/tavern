"""The card compiler turns a player's words into range-checked params, or labeled defaults offline."""

import asyncio
from typing import Any

import pytest

from tavern.mind.card_compiler import RejectedParams, compile_card, offline_card
from tavern.mind.cards import PARAMS, CardText
from tavern.adapters.claude import ClaudeError
from tavern.mind.questions import Question


def text(**fields: str) -> CardText:
    """A player's card in words."""
    return CardText(**{"name": "Bren", "occupation": "charcoal burner", "background": "Fought in two wars.",
                       "temperament": "Quarrelsome when drinking.", "speech": "Loud.", "quirks": "Shows his scars.",
                       "secret": "Deserted.", "goal": "Win at darts.", **fields})


def params(**values: Any) -> dict[str, Any]:
    """A full answer with middling params unless given."""
    return {**dict.fromkeys(PARAMS, 0.5), **values}


class FakeClaude:
    """Answers every question with the same object and keeps the questions it was asked."""

    def __init__(self, answer: Any) -> None:
        self.answer, self.asked = answer, []

    async def __call__(self, question: Question) -> Any:
        self.asked.append(question)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def compiled(answer: Any, words: CardText | None = None) -> tuple[Any, FakeClaude]:
    """Compile a card against a fake Claude."""
    claude = FakeClaude(answer)
    return asyncio.run(compile_card(words or text(), claude)), claude


@pytest.mark.parametrize("answer, expected", [
    pytest.param(params(temper=0.9, courage=1), {**params(temper=0.9, courage=1.0)}, id="read-from-text"),
    pytest.param(params(temper=0, courage=0), {**params(temper=0.0, courage=0.0)}, id="lower-bounds"),
    pytest.param(dict.fromkeys(PARAMS, 1), dict.fromkeys(PARAMS, 1.0), id="upper-bounds"),
])
def test_valid_params_are_proposed_for_confirmation(answer: dict[str, Any], expected: dict[str, float]) -> None:
    result, _claude = compiled(answer)
    assert result == {"params": expected, "compiled": True, "source": "claude",
                      "note": "Read from the card by Claude; confirm or adjust before the evening."}


@pytest.mark.parametrize("answer", [
    pytest.param({}, id="empty-answer"),
    pytest.param(params(temper=1.2), id="above-range"),
    pytest.param(params(temper=-0.1), id="below-range"),
    pytest.param(params(temper="high"), id="malformed-number"),
    pytest.param(params(temper=True), id="boolean"),
    pytest.param(params(temper=float("nan")), id="not-a-number"),
    pytest.param(params(luck=0.5), id="unknown-param"),
    pytest.param({key: 0.5 for key in PARAMS if key != "courage"}, id="missing-param"),
])
def test_malformed_or_out_of_range_answers_are_rejected(answer: dict[str, Any]) -> None:
    with pytest.raises(RejectedParams):
        compiled(answer)


def test_model_failure_reaches_the_caller() -> None:
    with pytest.raises(ClaudeError):
        compiled(ClaudeError("Claude HTTP 529"))


def test_question_sends_the_words_after_a_stable_prefix() -> None:
    _result, first = compiled(params())
    _result, second = compiled(params(), text(name="Ysolde", goal="Buy a debt."))
    one, other = first.asked[0], second.asked[0]
    assert (one["system"] == other["system"], "Ysolde" in other["content"], "Buy a debt." in other["content"],
            "Ysolde" in " ".join(other["system"])) == (True, True, True, False)
    assert (sorted(one["schema"]["properties"]), one["schema"]["required"], one["schema"]["additionalProperties"]) == (
        sorted(PARAMS), list(PARAMS), False)


def test_offline_mode_is_labeled_and_returns_defaults() -> None:
    assert offline_card(text()) == {"params": dict.fromkeys(PARAMS, 0.5), "compiled": False, "source": "offline",
                                    "note": "Not compiled: no Claude key on the server, so these are default params."}
