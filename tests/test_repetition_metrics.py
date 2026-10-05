"""Repetition in the evening metrics: intentions a guest's mind restates and lines a speaker says again."""

from typing import Any

import pytest

from tavern.evening.repetition import ALIKE, repetition_counts


def intention(actor_id: str, intends: str, time: float = 1.0) -> dict[str, Any]:
    """A logged intention, worded as `intentions.deliver_intention` logs it."""
    return {"time": time, "actor_id": actor_id, "type": "intention",
            "message": f"{actor_id} thinks: Hm. Intends: {intends} (after: {actor_id} has just come in)"}


def turn(actor_id: str, line: str, time: float = 1.0) -> dict[str, Any]:
    """A logged conversation line, worded as `turns` logs it."""
    return {"time": time, "actor_id": actor_id, "type": "turn", "message": f"{actor_id} to Bea (small_talk): {line}"}


FETCH = "Pour an ale at the tap and bring it back to Edda at this table."
FETCH_AGAIN = "Pour an ale at the tap and bring it straight back to Edda at this table."
ASK = "Ask Brida what remedy the margrave's healers are using."
DARTS = "Come on then, Edda. Forget the feet for a moment, let's have a round at the darts."


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"restated": 0, "repeated": 0}, id="empty"),
    pytest.param([intention("ada", FETCH)], {"restated": 0, "repeated": 0}, id="single-intention"),
    pytest.param([intention("ada", FETCH), intention("ada", FETCH)], {"restated": 1, "repeated": 0},
                 id="duplicate-intention"),
    pytest.param([intention("ada", FETCH), intention("ada", FETCH_AGAIN)], {"restated": 1, "repeated": 0},
                 id="near-verbatim-intention"),
    pytest.param([intention("ada", FETCH), intention("ada", ASK)], {"restated": 0, "repeated": 0},
                 id="new-intention"),
    pytest.param([intention("ada", FETCH), intention("bea", FETCH)], {"restated": 0, "repeated": 0},
                 id="same-intention-of-two-guests"),
    pytest.param([intention("ada", FETCH), intention("ada", ASK), intention("ada", FETCH)],
                 {"restated": 0, "repeated": 0}, id="intention-compared-with-the-previous-only"),
    pytest.param([turn("ada", DARTS)], {"restated": 0, "repeated": 0}, id="single-line"),
    pytest.param([turn("ada", DARTS), turn("ada", "My feet are screaming."), turn("ada", DARTS.lower())],
                 {"restated": 0, "repeated": 1}, id="line-said-again-later"),
    pytest.param([turn("ada", DARTS), turn("bea", DARTS)], {"restated": 0, "repeated": 0},
                 id="same-line-of-two-speakers"),
    pytest.param([turn("ada", "Ha!"), turn("ada", "Ha!")], {"restated": 0, "repeated": 0},
                 id="lines-too-short-to-judge"),
    pytest.param([intention("ada", FETCH), {"time": 2.0, "actor_id": "ada", "type": "action_started",
                                            "message": "ada started sit"}, intention("ada", FETCH)],
                 {"restated": 1, "repeated": 0}, id="other-events-ignored"),
])
def test_repetitions_are_counted(events: list[dict[str, Any]], expected: dict[str, int]) -> None:
    assert repetition_counts(events, ALIKE) == expected


@pytest.mark.parametrize("events, threshold", [
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "intention", "message": "ada thinks: Hm."}], ALIKE,
                 id="intention-without-intends"),
    pytest.param([{"time": 1.0, "actor_id": "ada", "type": "turn", "message": "ada says hello"}], ALIKE,
                 id="line-without-act"),
    pytest.param([], 0.0, id="threshold-zero"),
    pytest.param([], 1.5, id="threshold-above-one"),
    pytest.param([], float("nan"), id="threshold-nan"),
])
def test_malformed_input_fails_loudly(events: list[dict[str, Any]], threshold: float) -> None:
    with pytest.raises(ValueError):
        repetition_counts(events, threshold)
