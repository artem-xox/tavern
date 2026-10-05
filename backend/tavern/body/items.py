"""The kinds of things a visitor can carry: wording and the rules for an inventory of them."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Item:
    """One kind of thing a visitor carries.

    Attributes:
        kind: Inventory key, saved with the world.
        one: Wording for a single one in events and the inspector.
        many: Wording for several.
        held: How a briefing says someone holds one.
    """

    kind: str
    one: str
    many: str
    held: str


ITEMS: Mapping[str, Item] = MappingProxyType({
    "beer": Item("beer", "a mug of ale", "mugs of ale", held="a full mug of ale"),
})


def empty_inventory() -> dict[str, int]:
    """Start an inventory with every kind at zero.

    Returns:
        A count of zero for each kind in `ITEMS`.
    """
    return {kind: 0 for kind in ITEMS}


def check_inventory(inventory: Mapping[str, Any]) -> None:
    """Refuse an inventory that is not exactly one nonnegative whole count per kind.

    Args:
        inventory: Counts by item kind, as built, saved or observed.
    Raises:
        ValueError: A kind is missing, a count is not a nonnegative integer, or a kind is unknown.
    """
    for kind in ITEMS:
        count = inventory.get(kind)
        if type(count) is not int or count < 0:
            raise ValueError(f"Inventory {kind} must be a nonnegative integer")
    unknown = sorted(set(inventory) - set(ITEMS))
    if unknown:
        raise ValueError(f"Unknown inventory kind {unknown[0]!r}")


def held_words(inventory: Mapping[str, int]) -> str | None:
    """Say what a visitor holds the way a briefing does.

    Args:
        inventory: Counts by item kind.
    Returns:
        The kinds held, joined by "and", or None when the hands are empty. A count is not said yet:
        two mugs read as one.
    """
    held = [item.held for kind, item in ITEMS.items() if inventory[kind]]
    return " and ".join(held) or None


def client_items() -> dict[str, dict[str, str]]:
    """Describe the kinds of item for the browser client.

    Returns:
        Per kind: the wording for one and for several.
    """
    return {kind: {"one": item.one, "many": item.many} for kind, item in ITEMS.items()}
