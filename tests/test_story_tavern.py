"""The setting is The Story Tavern, a tavern between worlds, wherever a player or a model can read it."""

import json
from pathlib import Path
import re

import pytest

from tavern.mind.turn_prompt import shared_prefix
from tavern.mind.world_now import WORLD_NOW
from tavern.social.conversation import ACTS

ROOT = Path(__file__).resolve().parents[1]


def intention_prefix() -> str:
    return (ROOT / "data" / "minds" / "intention_prefix.md").read_text()


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
])
def test_the_prefixes_give_famous_guests_the_news_of_the_day(text: str) -> None:
    assert WORLD_NOW in text


def guest_names() -> list[str]:
    """The last word of every famous guest's name, as the line writer's examples would name them."""
    return [json.loads(path.read_text())["name"].split()[-1] for path in (ROOT / "characters" / "guests").glob(
        "*/character.json")]


def test_most_line_examples_voice_famous_guests() -> None:
    # Haiku copies its examples more than its rules: with 25 of 27 about the border folk, famous guests talked about
    # carts, ale and the road (live seed 5, 2026-10-25).
    examples = re.findall(r"\nExample \d+\..*?(?=\nExample \d+\.|\Z)", shared_prefix(ACTS), re.S)
    famous = [text for text in examples if any(name in text for name in guest_names())]
    assert len(famous) * 2 > len(examples)
