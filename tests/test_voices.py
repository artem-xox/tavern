"""Voice files: each guest's stock lines are read from `data/voices` and checked at the boundary."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.voices import load_voices

BOOK = {"greet": ["Well met, {name}."], "accept": ["Gladly."]}


def write(directory: Path, name: str, content: Any) -> None:
    """Write a voice file."""
    (directory / name).write_text(content if isinstance(content, str) else json.dumps(content))


def test_voices_are_read_by_the_guest_whose_name_the_file_bears(tmp_path: Path) -> None:
    write(tmp_path, "brida.json", {"card_hash": "abc", "lines": BOOK})
    write(tmp_path, "edda.json", {"card_hash": "def", "lines": {"closing": ["Good night."]}})
    assert load_voices(tmp_path) == {"brida": BOOK, "edda": {"closing": ["Good night."]}}


def test_an_empty_directory_is_no_voices(tmp_path: Path) -> None:
    assert load_voices(tmp_path) == {}


def test_other_files_are_not_voices(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "Voices are made by scripts/voices.py")
    assert load_voices(tmp_path) == {}


@pytest.mark.parametrize("content", [
    pytest.param("{not json", id="not-json"),
    pytest.param([], id="not-an-object"),
    pytest.param({"lines": BOOK}, id="no-card-hash"),
    pytest.param({"card_hash": "abc"}, id="no-lines"),
    pytest.param({"card_hash": "abc", "lines": BOOK, "extra": 1}, id="an-unknown-field"),
    pytest.param({"card_hash": "", "lines": BOOK}, id="a-blank-hash"),
    pytest.param({"card_hash": "abc", "lines": {"insult": ["You fool."]}}, id="a-kind-nobody-stocks"),
    pytest.param({"card_hash": "abc", "lines": {"greet": ["*nods*"]}}, id="a-stage-direction"),
])
def test_a_malformed_voice_file_fails_loudly(tmp_path: Path, content: Any) -> None:
    write(tmp_path, "brida.json", content)
    with pytest.raises(ValueError, match="brida"):
        load_voices(tmp_path)


def test_a_missing_directory_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="voices"):
        load_voices(tmp_path / "nowhere")
