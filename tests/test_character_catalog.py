"""Catalog profiles are complete, role-safe source data for an evening."""

from typing import Any

import pytest

from tavern.mind.cards import PARAMS
from tavern.mind.characters import parse_catalog


def profile(character_id: str, role: str = "guest", **changes: Any) -> dict[str, Any]:
    """Build one valid catalog profile with no default inventory or relationships."""
    return {
        "id": character_id,
        "role": role,
        "name": character_id.title(),
        "color": "#a08060",
        "looks": f"the traveler named {character_id.title()}",
        "occupation": "drover",
        "background": "Drives cattle across the border.",
        "temperament": "Even-tempered until cheated.",
        "speech": "Slow and plain.",
        "quirks": "Counts the mugs on the table.",
        "secret": "Once lost a herd at dice.",
        "goal": "Find a warm seat and a drink.",
        "sex": "male",
        "params": dict.fromkeys(PARAMS, 0.5),
        "carries": {},
        "relationships": [],
        "visuals": {"size": 68, "lift": -16},
        **changes,
    }


def test_catalog_resolves_defaults_and_hides_a_secret_from_public_data() -> None:
    catalog = parse_catalog([
        profile("ada", relationships=[{"with": "bea", "kind": "old friends", "note": "They shared a winter camp."}]),
        profile("bea"),
    ])
    ada = catalog.character("ada")
    assert (ada["card"]["id"], ada["carries"], catalog.ties) == (
        "ada", {}, ({"a": "ada", "b": "bea", "kind": "old friends", "note": "They shared a winter camp."},))
    assert catalog.public()["characters"][0] == {
        "id": "ada", "role": "guest", "name": "Ada", "color": "#a08060", "sprite": "ada",
        "visuals": {"size": 68, "lift": -16, "poses": [
            "Idle", "Seated", "Darts", "Bathroom", "Drinking", "DrinkingSeated", "TalkingSeated",
            "TakeBeer", "Walking", "Talking", "Giving", "GivingSeated", "Receiving", "ReceivingSeated",
            "SleepingSeated", "Fighting", "KnockedOut", "Hurt", "HurtSeated", "Shoving", "HelpingUp",
        ]},
    }
    assert "secret" not in str(catalog.public())


@pytest.mark.parametrize("records, message", [
    pytest.param([profile("ada"), profile("ada")], "Duplicate character", id="duplicate-id"),
    pytest.param([profile("ada", role="bouncer")], "role", id="unknown-role"),
    pytest.param([profile("ada", carries={"sword": 1})], "unknown item", id="unknown-item"),
    pytest.param([profile("ada", relationships=[{"with": "nobody", "kind": "old friends", "note": "Met once."}])],
                 "unknown character", id="unknown-relationship-target"),
    pytest.param([profile("ada", relationships=[{"with": "bea", "kind": "old friends", "note": "Met once."}]),
                  profile("bea", relationships=[{"with": "ada", "kind": "rivals", "note": "Met again."}])],
                 "Duplicate character relationship", id="duplicate-relationship-pair"),
])
def test_catalog_rejects_invalid_profiles(records: list[dict[str, Any]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_catalog(records)


def test_catalog_rejects_a_bartender_as_a_guest_card() -> None:
    catalog = parse_catalog([profile("hob", role="bartender")])
    with pytest.raises(ValueError, match="guest"):
        catalog.guest("hob")
