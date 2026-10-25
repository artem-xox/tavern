"""The setting is The Story Tavern, a tavern between worlds, wherever a player or a model can read it."""

import json
from pathlib import Path
import re

import pytest

from tavern.hall.closing import LAST_CALL_LINE
from tavern.mind.turn_prompt import shared_prefix
from tavern.mind.world_now import WORLD_NOW
from tavern.social.conversation import ACTS
from tavern.social.scenes import TOPICS

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


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
])
def test_the_prefixes_let_famous_guests_talk_about_their_own_public_life(text: str) -> None:
    assert "their real public" in text
    assert "not a tavern story" in text


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
])
def test_the_prefixes_say_famous_guests_know_one_another(text: str) -> None:
    assert "know one another perfectly well" in text


@pytest.mark.parametrize("text", [
    pytest.param(shared_prefix(ACTS), id="line-writer-prefix"),
    pytest.param(intention_prefix(), id="intention-prefix"),
])
def test_the_prefixes_give_famous_guests_the_news_of_the_day(text: str) -> None:
    assert WORLD_NOW in text


@pytest.mark.parametrize("phrase", [
    pytest.param("Russia", id="the-war-in-ukraine"),
    pytest.param("Iran", id="the-gulf"),
    pytest.param("Gaza", id="gaza"),
    pytest.param("tariff", id="trade-wars"),
    pytest.param("OCTOBER 2026", id="dated"),
])
def test_the_news_of_the_day_names_the_wars_and_the_date(phrase: str) -> None:
    assert phrase in WORLD_NOW


def test_a_new_scene_never_opens_on_the_road() -> None:
    assert not [topic for topic in TOPICS if "road" in topic or "journey" in topic]


def test_the_line_writer_may_discuss_the_news_of_the_day() -> None:
    assert "do not invent news" not in shared_prefix(ACTS)
    assert "the news of the day" in shared_prefix(ACTS)


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


@pytest.mark.parametrize("phrase", [
    pytest.param("satire with no brakes", id="the-tone-of-docs-design"),
    pytest.param("The counter-charge", id="a-charge-answered-with-a-worse-one"),
    pytest.param("The nickname", id="a-name-hung-on-a-rival"),
    pytest.param("The receipt", id="a-fact-from-the-record-as-a-weapon"),
    pytest.param("The callback", id="something-from-earlier-tonight"),
])
def test_the_line_writer_plays_famous_guests_for_laughs(phrase: str) -> None:
    assert phrase in shared_prefix(ACTS)
