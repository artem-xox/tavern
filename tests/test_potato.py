"""Lukashenko's potatoes: an ordinary gift that its owner presses on everyone near."""

from typing import Any

import pytest

from tavern.body.items import ITEMS
from tavern.mind.candidates import build_candidates
from tavern.mind.local_policy import local_scores
from test_gift_options import carrying


def score_of_gift(kind: str, opinion: float) -> float:
    """How much a guest who holds one of this kind and holds Bea in this regard feels like handing it to her."""
    view: dict[str, Any] = carrying({kind: 1}, opinion=opinion)
    options = build_candidates(view)
    gifts = [member for option in options for member in option.get("members", [option])
             if member["verb"] == "give"]
    return local_scores(view, gifts)[gifts[0]["id"]]


def test_a_potato_is_an_ordinary_gift_not_a_signature_item() -> None:
    potato = ITEMS["potato"]
    assert (potato.giftable, potato.offers, potato.hands) == (True, (), 5)


@pytest.mark.parametrize("opinion", [
    pytest.param(-20.0, id="someone-they-dislike"),
    pytest.param(0.0, id="a-stranger"),
    pytest.param(40.0, id="a-friend"),
])
def test_a_guest_is_keener_to_hand_out_a_potato_than_any_other_keepsake(opinion: float) -> None:
    assert score_of_gift("potato", opinion) > score_of_gift("keepsake", opinion)
