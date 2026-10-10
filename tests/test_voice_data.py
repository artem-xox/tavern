"""The shipped voices: every guest's stock lines load, and were written from the card the guest has now."""

import json
from pathlib import Path

import pytest

from tavern.adapters.voices import load_voices
from tavern.mind.voice_question import card_hash

DATA = Path(__file__).resolve().parents[1] / "data"
CARDS = {card["id"]: card for directory in ("characters", "staff") for path in sorted((DATA / directory).glob("*.json"))
         for card in [json.loads(path.read_text())]}


def test_the_shipped_voices_load() -> None:
    assert set(load_voices(DATA / "voices")) <= set(CARDS)


@pytest.mark.parametrize("path", sorted((DATA / "voices").glob("*.json")), ids=lambda path: path.stem)
def test_a_voice_was_written_from_the_card_the_guest_has_now(path: Path) -> None:
    # A card changed since its lines were written needs `scripts/voices.py` run again.
    assert json.loads(path.read_text())["card_hash"] == card_hash(CARDS[path.stem])
