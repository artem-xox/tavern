"""A guest's portrait names every kind of tie a scenario can give them."""

import pytest

from tavern.mind.portrait import portrait
from tavern.social.ties import KINDS


@pytest.mark.parametrize("kind", [pytest.param(kind, id=kind.replace(" ", "-")) for kind in KINDS])
def test_a_tie_of_any_kind_is_told_in_the_portrait(kind: str) -> None:
    actor = {"card": None, "ties": [{"name": "Greta", "kind": kind, "note": "a note"}]}
    assert "Greta" in portrait(actor)


def test_a_famous_guest_knows_the_other_by_reputation() -> None:
    actor = {"card": None, "ties": [{"name": "Greta", "kind": "well known", "note": "By reputation."}]}
    assert portrait(actor) == "Greta is someone they know by reputation of theirs (By reputation.)."
