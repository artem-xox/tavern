"""A model judges a recorded talk between two guests against a rubric; its answer is checked at the boundary."""

import asyncio
from typing import Any

import pytest

from tavern.evening.dialogue_judge import CRITERIA, judge_dialogue, judge_question, parse_verdict

LOOK_FOR = {"Vladimir Putin": "cold, denies, answers a charge with a counter-charge",
            "Volodymyr Zelenskyy": "concrete facts and demands, jokes that turn serious"}
TRANSCRIPT = ["Volodymyr Zelenskyy (complain): Your drones hit Kyiv again.",
              "Vladimir Putin (disagree): These are provocations."]
SCORES = dict.fromkeys(CRITERIA, 4)
GOOD = {"scores": SCORES, "notes": "They argue about the drones and Putin denies."}


def test_the_question_holds_the_rubric_the_characters_and_the_transcript() -> None:
    question = judge_question(TRANSCRIPT, LOOK_FOR)
    text = "\n".join([*question["system"], question["content"]])
    assert [part for part in (*CRITERIA, *LOOK_FOR.values(), *TRANSCRIPT) if part not in text] == []


@pytest.mark.parametrize("answer", [
    pytest.param(GOOD, id="every-score-and-notes"),
    pytest.param({**GOOD, "scores": dict.fromkeys(CRITERIA, 1)}, id="lowest-scores"),
    pytest.param({**GOOD, "scores": dict.fromkeys(CRITERIA, 5)}, id="highest-scores"),
])
def test_a_verdict_in_the_documented_shape_passes(answer: dict[str, Any]) -> None:
    assert parse_verdict(answer) == answer


@pytest.mark.parametrize("answer", [
    pytest.param({**GOOD, "scores": {**SCORES, CRITERIA[0]: 6}}, id="score-above-five"),
    pytest.param({**GOOD, "scores": {**SCORES, CRITERIA[0]: 0}}, id="score-below-one"),
    pytest.param({**GOOD, "scores": {**SCORES, CRITERIA[0]: 3.5}}, id="score-not-whole"),
    pytest.param({**GOOD, "scores": {**SCORES, CRITERIA[0]: True}}, id="score-a-bool"),
    pytest.param({**GOOD, "scores": {key: 3 for key in CRITERIA[1:]}}, id="a-criterion-missing"),
    pytest.param({**GOOD, "scores": {**SCORES, "charm": 3}}, id="an-unknown-criterion"),
    pytest.param({**GOOD, "notes": " "}, id="blank-notes"),
    pytest.param({"scores": SCORES}, id="no-notes"),
    pytest.param("4/5", id="not-an-object"),
])
def test_a_malformed_verdict_is_rejected(answer: Any) -> None:
    with pytest.raises(ValueError):
        parse_verdict(answer)


def test_the_judge_asks_the_port_once_and_checks_the_answer() -> None:
    asked: list[Any] = []

    async def ask(question: Any) -> dict[str, Any]:
        asked.append(question)
        return GOOD
    assert (asyncio.run(judge_dialogue(TRANSCRIPT, LOOK_FOR, ask)), len(asked)) == (GOOD, 1)


def test_an_empty_transcript_is_not_judged() -> None:
    with pytest.raises(ValueError):
        judge_question([], LOOK_FOR)
