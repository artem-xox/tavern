"""The item table: what an inventory holds, how it reads, and which inventories are refused."""

from typing import Any

import pytest

from tavern.body.items import ITEMS, check_inventory, client_items, empty_inventory, held_words, parse_carries


def stocked(**counts: int) -> dict[str, int]:
    """An inventory with the given counts and every other kind at zero."""
    return {**empty_inventory(), **counts}


def test_an_empty_inventory_has_every_kind_at_zero() -> None:
    assert empty_inventory() == {"beer": 0, "remedy": 0, "keepsake": 0}


@pytest.mark.parametrize("inventory", [
    pytest.param(stocked(), id="empty-handed"),
    pytest.param(stocked(beer=1), id="one-mug"),
    pytest.param(stocked(beer=2), id="two-mugs-fill-the-hands"),
    pytest.param(stocked(remedy=3, keepsake=3), id="pockets-full"),
])
def test_a_whole_inventory_passes(inventory: dict[str, int]) -> None:
    assert check_inventory(inventory) is None


@pytest.mark.parametrize("inventory,message", [
    pytest.param({}, "Inventory beer", id="empty-mapping-misses-a-kind"),
    pytest.param({"beer": 0, "remedy": 0}, "Inventory keepsake", id="one-kind-missing"),
    pytest.param(stocked(beer=-1), "Inventory beer", id="negative"),
    pytest.param(stocked(beer=True), "Inventory beer", id="boolean-is-not-a-count"),
    pytest.param(stocked(beer=1.0), "Inventory beer", id="float"),
    pytest.param(stocked(beer="1"), "Inventory beer", id="text"),
    pytest.param(stocked(beer=3), "Inventory beer", id="more-mugs-than-hands"),
    pytest.param(stocked(remedy=4), "Inventory remedy", id="more-remedies-than-pockets"),
    pytest.param({**stocked(), "wine": 1}, "wine", id="unknown-kind"),
])
def test_a_malformed_inventory_is_refused_by_name(inventory: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_inventory(inventory)


@pytest.mark.parametrize("inventory,words", [
    pytest.param(stocked(), None, id="empty-handed"),
    pytest.param(stocked(beer=1), "a full mug of ale", id="one-mug"),
    # Two mugs read as one until the briefing counts what is carried (H2).
    pytest.param(stocked(beer=2), "a full mug of ale", id="two-mugs"),
    # Things in a pocket do not fill the hands; the briefing says what is carried in H2.
    pytest.param(stocked(remedy=2, keepsake=1), None, id="carried-out-of-sight"),
    pytest.param(stocked(beer=1, remedy=1), "a full mug of ale", id="mug-and-remedy"),
])
def test_what_a_visitor_holds_reads_for_a_briefing(inventory: dict[str, int], words: str | None) -> None:
    assert held_words(inventory) == words


def test_the_client_gets_the_wording_of_every_kind() -> None:
    assert client_items() == {
        "beer": {"one": "a mug of ale", "many": "mugs of ale"},
        "remedy": {"one": "a herbal remedy", "many": "herbal remedies"},
        "keepsake": {"one": "a keepsake", "many": "keepsakes"},
    }


def test_every_kind_is_received_with_a_thought_of_its_own() -> None:
    assert {kind: item.received for kind, item in ITEMS.items()} == {
        "beer": "treated", "remedy": "cared_for", "keepsake": "gifted"}


@pytest.mark.parametrize("carries,expected", [
    pytest.param({}, {}, id="nothing"),
    pytest.param({"remedy": 2}, {"remedy": 2}, id="two-remedies"),
    pytest.param({"keepsake": 3, "beer": 1}, {"keepsake": 3, "beer": 1}, id="several-kinds"),
    pytest.param({"remedy": 0}, {"remedy": 0}, id="zero-is-allowed"),
])
def test_what_a_scenario_guest_carries_is_kept(carries: dict[str, int], expected: dict[str, int]) -> None:
    assert parse_carries(carries) == expected


@pytest.mark.parametrize("carries,message", [
    pytest.param(["remedy"], "carries", id="not-a-mapping"),
    pytest.param({"wine": 1}, "wine", id="unknown-kind"),
    pytest.param({"remedy": -1}, "remedy", id="negative"),
    pytest.param({"remedy": 4}, "remedy", id="more-than-hands"),
    pytest.param({"remedy": True}, "remedy", id="boolean"),
    pytest.param({"remedy": "2"}, "remedy", id="text"),
])
def test_a_malformed_carries_is_refused_by_name(carries: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_carries(carries)
