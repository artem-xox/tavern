"""A drink errand in a headless evening, decided by a fake model the way a live evening is."""

from typing import Any

from social_hall import know
from test_lockstep import evening, preferring, seated_pair


def test_a_guest_who_chooses_to_bring_a_drink_delivers_it_in_a_headless_evening() -> None:
    world = seated_pair()
    know(world, "ada", "tap")
    # Ada's model favours bringing a drink and scores everything else zero; Bea's only waits.
    result, world = evening(preferring({"Ada": "bring_drink", "Bea": "wait"}), limit=90.0, world=world)
    kinds = [event["type"] for event in result.events if event["type"].startswith("fetch_")]
    bea = next(item for item in world["actors"] if item["id"] == "bea")
    assert (kinds, bea["inventory"]["beer"]) == (["fetch_begun", "fetch_done"], 1)
