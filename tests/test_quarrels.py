"""How hot a quarrel has run: the length of the insult run that ends a scene."""

from typing import Any

import pytest

from tavern.social.quarrels import heat


def turn(speaker: str, act: str, addressee: str | None) -> dict[str, Any]:
    """Build a spoken turn; the words and the time do not matter to the heat."""
    return {"speaker": speaker, "addressee": addressee, "line": "Well now.", "act": act, "time": 0.0}


def scene_of(*turns: dict[str, Any]) -> dict[str, Any]:
    """Build a scene holding only the turns."""
    return {"turns": list(turns)}


@pytest.mark.parametrize("turns, expected", [
    pytest.param([], 0, id="no-turns"),
    pytest.param([turn("ada", "insult", "bea")], 1, id="one-insult"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada")], 2, id="two-traded"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("ada", "insult", "bea"),
                  turn("bea", "insult", "ada")], 4, id="four-traded"),
    pytest.param([turn("ada", "greet", "bea"), turn("bea", "insult", "ada")], 1, id="insult-after-a-greeting"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("ada", "remark", "bea")], 0,
                 id="other-act-last"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "remark", "ada"), turn("ada", "insult", "bea"),
                  turn("bea", "insult", "ada")], 2, id="other-act-breaks-the-run"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("cid", "insult", "ada")], 1,
                 id="third-speaker-starts-a-new-run"),
    pytest.param([turn("ada", "insult", "bea"), turn("ada", "insult", "bea")], 1, id="same-speaker-twice"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", None)], 0, id="insult-to-everyone-last"),
    pytest.param([turn("ada", "insult", None), turn("bea", "insult", "ada")], 1, id="insult-to-everyone-breaks-the-run"),
])
def test_heat_is_the_insult_run_ending_the_scene(turns: list[dict[str, Any]], expected: int) -> None:
    assert heat(scene_of(*turns)) == expected
