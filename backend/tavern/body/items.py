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
        held: How a briefing says someone holds one in their hand, or None for something carried out
            of sight (a remedy in a sleeve).
        hands: Most a visitor can carry at once.
        received: The `THOUGHTS` kind a receiver keeps about whoever gave it to them.
    """

    kind: str
    one: str
    many: str
    held: str | None
    hands: int
    received: str

    @property
    def visible(self) -> bool:
        """Whether others see it in the carrier's hands: a mug yes, a remedy in a sleeve no."""
        return self.held is not None


ITEMS: Mapping[str, Item] = MappingProxyType({
    "beer": Item("beer", "a mug of ale", "mugs of ale", held="a full mug of ale", hands=2, received="treated"),
    "remedy": Item("remedy", "a herbal remedy", "herbal remedies", held=None, hands=3, received="cared_for"),
    "keepsake": Item("keepsake", "a keepsake", "keepsakes", held=None, hands=3, received="gifted"),
})


def empty_inventory() -> dict[str, int]:
    """Start an inventory with every kind at zero.

    Returns:
        A count of zero for each kind in `ITEMS`.
    """
    return {kind: 0 for kind in ITEMS}


def check_inventory(inventory: Mapping[str, Any]) -> None:
    """Refuse an inventory that is not exactly one whole count per kind, from 0 to what a visitor can carry.

    Args:
        inventory: Counts by item kind, as built, saved or observed.
    Raises:
        ValueError: A kind is missing, a count is not an integer from 0 to the kind's `hands`, or a kind is unknown.
    """
    for kind, item in ITEMS.items():
        count = inventory.get(kind)
        if type(count) is not int or not 0 <= count <= item.hands:
            raise ValueError(f"Inventory {kind} must be a whole number from 0 to {item.hands}")
    unknown = sorted(set(inventory) - set(ITEMS))
    if unknown:
        raise ValueError(f"Unknown inventory kind {unknown[0]!r}")


def held_words(inventory: Mapping[str, int]) -> str | None:
    """Say what a visitor holds the way a briefing does.

    Args:
        inventory: Counts by item kind.
    Returns:
        What is in the hands, joined by "and", or None when they are empty (or all that is carried is out of
        sight). A count is not said yet: two mugs read as one.
    """
    held = [item.held for kind, item in ITEMS.items() if inventory.get(kind) and item.held]
    return " and ".join(held) or None


def client_items() -> dict[str, dict[str, str]]:
    """Describe the kinds of item for the browser client.

    Returns:
        Per kind: the wording for one and for several.
    """
    return {kind: {"one": item.one, "many": item.many} for kind, item in ITEMS.items()}


def parse_carries(data: Any) -> dict[str, int]:
    """Validate what a scenario guest carries in with them.

    Args:
        data: Counts by item kind, from 0 to the kind's `hands`; kinds left out are zero.
    Returns:
        The counts as given.
    Raises:
        ValueError: It is not a mapping, names an unknown kind, or holds a count out of range.
    """
    if not isinstance(data, Mapping):
        raise ValueError("A guest's carries must map item kinds to counts")
    for kind, count in data.items():
        if kind not in ITEMS:
            raise ValueError(f"A guest cannot carry unknown item {kind!r}")
        if type(count) is not int or not 0 <= count <= ITEMS[kind].hands:
            raise ValueError(f"A guest's carried {kind} must be a whole number from 0 to {ITEMS[kind].hands}")
    return dict(data)


_COUNT_WORDS = {2: "two", 3: "three"}


def carried_words(inventory: Mapping[str, int]) -> str | None:
    """Say what a visitor carries out of sight, counted, the way a briefing does.

    Args:
        inventory: Counts by item kind.
    Returns:
        The kinds that are not held in the hand, such as "two herbal remedies and a keepsake", or None
        when there are none.
    """
    carried = [item.one if count == 1 else f"{_COUNT_WORDS.get(count, count)} {item.many}"
               for kind, item in ITEMS.items() if not item.visible and (count := inventory.get(kind, 0))]
    return " and ".join(carried) or None
