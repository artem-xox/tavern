"""Handing something one visitor carries to another: what may be given, whether it is taken, and what both keep."""

from collections.abc import Mapping
from typing import Any

from tavern.body.ailment import relieve
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
    if formed_since(giver, receiver["id"], RECEIVED, now - window):
        return f"{receiver['name']} gave {giver['name']} something a moment ago"
    if formed_since(receiver, giver["id"], (item.received,), now - window):
        return f"{giver['name']} just gave {receiver['name']} {item.one}"
    return None


# What a guest keeps when someone gave them something, whatever it was.
RECEIVED = (*(item.received for item in ITEMS.values()), "cured")


def formed_since(holder: Mapping[str, Any], about_id: str, kinds: tuple[str, ...], since: float) -> bool:
    """Tell whether a visitor formed a thought of these kinds about someone after a game time.

    Args:
        holder: Visitor with `thoughts`.
        about_id: Person the thought is about.
        kinds: The `THOUGHTS` kinds that count.
        since: Game time; a thought formed at or before it does not count.

    Returns:
        True when one is held. A gift is remembered as the thoughts it left, which last longer than the wait
        between gifts, so a thought's age (its expiry less how long it lasts) says when the gift was made.
    """
    return any(thought["about"] == about_id and thought["kind"] in kinds
               and thought["expires_at"] - THOUGHTS[thought["kind"]].seconds > since for thought in holder["thoughts"])


def gift_targets(observation: Mapping[str, Any], kind: str) -> list[str]:
    """List the people a guest could hand an item to, as far as they can tell.

    Args:
        observation: The guest's observation, with `people` in sight, `time` and the world's `giving` rules.
            Without a clock or the rules no gift can be called recent, so nobody is a target.
        kind: The `ITEMS` kind to give.

    Returns:
        IDs, sorted, of those who sit at the guest's table or stand beside them, are not staff, are awake, do not
        visibly hold as many of the kind as their hands carry, and have not exchanged a gift or a
        refusal with the guest within `again_after`. That is stricter than `gift_error`, which the guest
        cannot see into: the guest remembers a gift of any kind to the same person, not only of this kind.
    """
    now, rules, actor = observation.get("time"), observation.get("giving"), observation["actor"]
    if now is None or rules is None:
        return []
    since = now - rules["again_after"]
    return sorted(person["id"] for person in observation.get("people", [])
                  if person["id"] != actor["id"] and not person.get("post") and not person.get("asleep")
                  and _near(observation, person) and person.get("holding", {}).get(kind, 0) < ITEMS[kind].hands
                  and not formed_since(actor, person["id"], (*RECEIVED, "generous", "rebuffed"), since))


def empty_handed_company(observation: Mapping[str, Any]) -> list[str]:
    """List the people near a guest who visibly hold no mug of ale and are free to be served one.

    Args:
        observation: The guest's observation, with `people` in sight and `on_errands`, the guests already
            on an errand or being served by one.

    Returns:
        IDs, sorted, of those who sit at the guest's table or stand beside them, are not staff, are awake, hold no
        mug in their hands, and are not on an errand. Without `on_errands` nobody can be called free.
    """
    busy, actor = observation.get("on_errands"), observation["actor"]
    if busy is None:
        return []
    return sorted(person["id"] for person in observation.get("people", [])
                  if person["id"] != actor["id"] and not person.get("post") and not person.get("asleep")
                  and _near(observation, person)
                  and not person.get("holding", {}).get("beer", 0) and person["id"] not in busy)


def _near(observation: Mapping[str, Any], person: Mapping[str, Any]) -> bool:
    # The reach of a chat: the same table, or standing side by side (a second copy of `hostility._near`).
    seat = next((item for item in observation["objects"] if item["id"] == observation["actor"].get("seat_id")), None)
    table = seat.get("table_id") if seat else None
    return bool(person.get("beside")) or bool(table and person.get("seat_id") and person.get("table_id") == table)


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
    # A remedy given to a guest who came in unwell is used on the spot, so they never hold it.
    cured = item.cures and receiver["ailing"]
    if cured:
        relieve(receiver)
    else:
        receiver["inventory"][kind] += 1
    message = (f"{receiver['name']} took {giver['name']}'s {item.one.removeprefix('a ')} and looks better already" if cured
               else f"{giver['name']} gave {receiver['name']} {item.one}")
    for member in (giver, receiver):
        record_event(world, member, "cured" if cured else "gave", message)
    think(receiver, "cured" if cured else item.received, now, f"{called(receiver, giver)} gave me {item.one}", message,
          about=giver)
    think(giver, "generous", now, f"I gave {called(giver, receiver)} {item.one}", message, about=receiver)
    show_emote(receiver, "affection", now + world["rules"]["emote_seconds"]["affection"])
