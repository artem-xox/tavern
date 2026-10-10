"""How the shipped guests look to strangers: short, and never the same for two."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
LOOKS = {card["id"]: card["looks"] for directory in ("characters", "staff") for path in sorted((DATA / directory).glob("*.json"))
         for card in [json.loads(path.read_text())]}


def test_no_two_guests_look_the_same_to_a_stranger() -> None:
    assert len(set(LOOKS.values())) == len(LOOKS)


def test_a_guests_looks_are_a_few_words_a_stranger_can_say_again_and_again() -> None:
    assert {guest: looks for guest, looks in LOOKS.items() if len(looks.split()) > 4} == {}
