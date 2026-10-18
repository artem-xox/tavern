"""Every famous guest's card carries a public persona to play: without one a model has nothing to say but tavern talk."""

from pathlib import Path

import pytest

from tavern.adapters.characters import load_catalog

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "characters")
GUESTS = sorted(item["id"] for item in CATALOG.characters.values() if item["cast"] == "guests")


@pytest.mark.parametrize("guest", [pytest.param(guest, id=guest) for guest in GUESTS])
def test_a_famous_guest_has_a_persona_catchphrases_and_obsessions(guest: str) -> None:
    card = CATALOG.characters[guest]["card"]
    assert [field for field in ("inspired_by", "persona", "catchphrases", "obsessions") if not card.get(field)] == []
