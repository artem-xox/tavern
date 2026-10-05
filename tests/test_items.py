"""The item table: what an inventory holds, how it reads, and which inventories are refused."""

from typing import Any

import pytest

from tavern.body.items import ITEMS, check_inventory, client_items, empty_inventory, held_words


def test_an_empty_inventory_has_every_kind_at_zero() -> None:
    assert empty_inventory() == {kind: 0 for kind in ITEMS}


@pytest.mark.parametrize("inventory", [
    pytest.param({"beer": 0}, id="empty-handed"),
    pytest.param({"beer": 1}, id="one-mug"),
    pytest.param({"beer": 2}, id="two-mugs"),
])
def test_a_whole_inventory_passes(inventory: dict[str, int]) -> None:
    assert check_inventory(inventory) is None


@pytest.mark.parametrize("inventory,message", [
    pytest.param({}, "Inventory beer", id="empty-mapping-misses-a-kind"),
    pytest.param({"beer": -1}, "Inventory beer", id="negative"),
    pytest.param({"beer": True}, "Inventory beer", id="boolean-is-not-a-count"),
    pytest.param({"beer": 1.0}, "Inventory beer", id="float"),
    pytest.param({"beer": "1"}, "Inventory beer", id="text"),
    pytest.param({"beer": 0, "wine": 1}, "wine", id="unknown-kind"),
])
def test_a_malformed_inventory_is_refused_by_name(inventory: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_inventory(inventory)


@pytest.mark.parametrize("inventory,words", [
    pytest.param({"beer": 0}, None, id="empty-handed"),
    pytest.param({"beer": 1}, "a full mug of ale", id="one-mug"),
    # Two mugs read as one until the briefing counts what is carried (H2).
    pytest.param({"beer": 2}, "a full mug of ale", id="two-mugs"),
])
def test_what_a_visitor_holds_reads_for_a_briefing(inventory: dict[str, int], words: str | None) -> None:
    assert held_words(inventory) == words


def test_the_client_gets_the_wording_of_every_kind() -> None:
    assert client_items() == {"beer": {"one": "a mug of ale", "many": "mugs of ale"}}
