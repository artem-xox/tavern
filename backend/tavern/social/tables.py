"""Whose table is whose, who is welcome at it, and what sitting down there uninvited does."""

from collections.abc import Mapping, MutableSequence
from typing import Any

from tavern.hall.memory import record_event
from tavern.hall.room import find_object
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, World
from tavern.social.invitations import home_table
from tavern.social.names import called
from tavern.social.social_acts import LIKED
from tavern.social.thoughts import familiarity_of, opinion_of, think


def liked(actor: Mapping[str, Any], other_id: str, now: float) -> bool:
    """Tell whether a guest is glad of someone's company at their own table.

    Args:
        actor: Visitor with `relations` and `thoughts` (a hand-made one may lack either).
        other_id: Person they think of.
        now: Current game time.

    Returns:
        True when they count the other a friend, or think at least `social_acts.LIKED` of them.
    """
    return familiarity_of(actor, other_id) == "friend" or opinion_of(actor, other_id, now) >= LIKED


def table_hosts(world: Mapping[str, Any], table_id: str, newcomer: Mapping[str, Any]) -> list[Actor]:
    """List the guests whose table a table is.

    Args:
        world: Current world.
        table_id: Table.
        newcomer: Visitor who is not counted, as they are the one wondering about the table.

    Returns:
        In the order of the hall, the guests (not staff) who sit at a chair of that table or whose own seat
        is one, each once.
    """
    chairs = {item["id"] for item in world["map"]["objects"]
              if item["kind"] == "chair" and item.get("table_id") == table_id}
    return [item for item in world["actors"] if item["id"] != newcomer["id"] and not on_staff(item)
            and (item.get("seat_id") in chairs or item.get("favorite_seat_id") in chairs)]


def welcome(world: Mapping[str, Any], host: Mapping[str, Any], guest: Mapping[str, Any]) -> bool:
    """Tell whether a host is glad to see a guest sit down at their table.

    Args:
        world: Current world.
        host: Guest whose table it is.
        guest: Guest who sits down there.

    Returns:
        True when the host likes the guest (see `liked`), the guest promised the host to come and sit with them,
        or an errand between the two is under way (an invitation to sit, or a drink brought over).
    """
    promised = any(item["kind"] == "sit_with" and item["from"] == guest["id"] and item["to"] == host["id"]
                   for item in world["commitments"])
    asked = any({item["from"], item["to"]} == {host["id"], guest["id"]} for item in world["invitations"])
    return liked(host, guest["id"], world["time"]) or promised or asked


def mark_ownership(world: Mapping[str, Any], viewer: Mapping[str, Any],
                   objects: MutableSequence[dict[str, Any]]) -> None:
    """Show on known chairs and tables whose they are, as anyone in the hall can see (a coat, a mug).

    Args:
        world: Current world.
        viewer: Visitor looking.
        objects: Their known object records, updated in place: a chair gets `owner`, who calls it their own seat
            (`{"id", "name"}` as the viewer calls them, or None; the viewer's own chair has none), and a table gets
            `hosts`, the list of `table_hosts` in the same form (none for the viewer's own table, which they share).
    """
    own_table = home_table(world, viewer)
    for item in objects:
        if item["kind"] == "chair" and item.get("table_id"):
            owner = next((who for who in world["actors"] if who["id"] != viewer["id"]
                          and who["favorite_seat_id"] == item["id"]), None)
            item["owner"] = None if owner is None else {"id": owner["id"], "name": called(viewer, owner)}
        elif item["kind"] == "table":
            hosts = [] if item["id"] == own_table else table_hosts(world, item["id"], viewer)
            item["hosts"] = [{"id": who["id"], "name": called(viewer, who)} for who in hosts]


def intrude(world: World, newcomer: Actor, chair: Mapping[str, Any]) -> None:
    """Let the hosts of a table take it ill that somebody sat down there without being welcome.

    Args:
        world: World whose events and the hosts' thoughts are updated in place.
        newcomer: Visitor who is sitting down on the chair (before it becomes their own seat).
        chair: The chair. Nothing happens in a hall without table manners (`rules.manners`), when the newcomer already calls a chair at its table theirs, or for a
            host whose own seat it is (that wrong is `seat_taken`).
    """
    if not world["rules"]["manners"]["table_intrusion"]:
        return
    own = find_object(world["map"], newcomer["favorite_seat_id"])
    if own is not None and own.get("table_id") == chair["table_id"]:
        return
    table = find_object(world["map"], chair["table_id"])
    for host in table_hosts(world, chair["table_id"], newcomer):
        if host["favorite_seat_id"] == chair["id"] or welcome(world, host, newcomer):
            continue
        message = f"{newcomer['name']} sat down at {host['name']}'s table uninvited ({table['name'] if table else 'a table'})"
        record_event(world, host, "table_intruded", message)
        record_event(world, newcomer, "sat_uninvited", message)
        think(host, "table_intruded", world["time"], f"{called(host, newcomer)} sat down at my table uninvited",
              message, about=newcomer)
