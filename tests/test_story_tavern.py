"""The setting is The Story Tavern, a tavern between worlds, wherever a player or a model can read it."""

from pathlib import Path

import pytest

from tavern.hall.closing import LAST_CALL_LINE
from tavern.mind.turn_prompt import shared_prefix
from tavern.social.conversation import ACTS

ROOT = Path(__file__).resolve().parents[1]


def intention_prefix() -> str:
    return (ROOT / "data" / "minds" / "intention_prefix.md").read_text()


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
    pytest.param(LAST_CALL_LINE, id="closing-call"),
])
def test_text_a_player_or_model_reads_names_the_story_tavern(text: str) -> None:
    assert "Story Tavern" in text
    assert "Last Inn" not in text


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
])
def test_the_prefixes_place_the_tavern_between_worlds_and_keep_the_locals(text: str) -> None:
    assert "between worlds" in text
    assert "border" in text
