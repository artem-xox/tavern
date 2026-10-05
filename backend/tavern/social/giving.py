"""Handing something one visitor carries to another: what may be given, whether it is taken, and what both keep."""

from collections.abc import Mapping
from typing import Any

from tavern.body.expression import show_emote
from tavern.body.items import ITEMS
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social.names import called
from tavern.social.thoughts import THOUGHTS, opinion_of, think


def gift_error(world: Mapping[str, Any], giver: Mapping[str, Any], receiver: Mapping[str, Any],
               kind: Any) -> str | None:
    """Tell why a visitor may not hand something to another, apart from where they stand.

    Args:
        world: Current world, with the time and `rules.giving`.
        giver: Visitor who would give.
        receiver: Guest who would be given it.
        kind: The `ITEMS` kind named by the action.

    Returns:
        A human-readable refusal reason, or None when it may be given. A receiver may still refuse it
        when it is handed over (`hand_over`).
    """
    if kind is None:
        return "Choose something to give"
    item = ITEMS.get(kind) if isinstance(kind, str) else None
    if item is None:
        return f"Unknown item {kind!r}"
    if giver["inventory"][kind] <= 0:
        return f"No {kind} in inventory"
    if receiver["inventory"][kind] >= item.hands:
        return f"{receiver['name']} has no free hand for {item.one}"
    window, now = world["rules"]["giving"]["again_after"], world["time"]
    if _gifts_since(giver, receiver["id"], tuple(thing.received for thing in ITEMS.values()), now - window):
        return f"{receiver['name']} gave {giver['name']} something a moment ago"
    if _gifts_since(receiver, giver["id"], (item.received,), now - window):
        return f"{giver['name']} just gave {receiver['name']} {item.one}"
    return None


def _gifts_since(holder: Mapping[str, Any], from_id: str, received: tuple[str, ...], since: float) -> bool:
    # A gift is remembered as the thought it left, which lasts longer than the wait between gifts,
    # so a thought's age (its expiry less how long it lasts) says when the gift was made.
    return any(thought["about"] == from_id and thought["kind"] in received
               and thought["expires_at"] - THOUGHTS[thought["kind"]].seconds > since for thought in holder["thoughts"])


def hand_over(world: World, giver: Actor, receiver: Actor, kind: str) -> None:
    """Hand one item over; the receiver takes it unless they think too ill of the giver.

    Args:
        world: Current world; both visitors are updated in place.
        giver: Visitor handing it over, who holds the item.
        receiver: Guest with a free hand for it.
        kind: The `ITEMS` kind given.
    """
    item, now = ITEMS[kind], world["time"]
    if opinion_of(receiver, giver["id"], now) < world["rules"]["giving"]["refuse_below"]:
        message = f"{receiver['name']} would not take {item.one} from {giver['name']}"
        for member in (giver, receiver):
            record_event(world, member, "gift_refused", message)
        think(giver, "rebuffed", now, f"{called(giver, receiver)} would not take what I offered", message,
              about=receiver)
        return
    giver["inventory"][kind] -= 1
    receiver["inventory"][kind] += 1
    message = f"{giver['name']} gave {receiver['name']} {item.one}"
    for member in (giver, receiver):
        record_event(world, member, "gave", message)
    think(receiver, item.received, now, f"{called(receiver, giver)} gave me {item.one}", message, about=giver)
    show_emote(receiver, "affection", now + world["rules"]["emote_seconds"]["affection"])
