"""Errands: what accepted invitations set in motion, carried out one step a tick through the ordinary action lifecycle.

`honor_invitations` runs every errand in `world["invitations"]` (see `tavern.social.invitations`) through
`world.start_action`, so the usual rules decide whether each step is possible.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from tavern.body.actions import action_error
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social.dice import PLAY, open_chairs
from tavern.social.invitations import KINDS, Errand, free_chair, home_table, known_place
from tavern.social.names import called
from tavern.social.thoughts import think

# Starts an action the way `world.start_action` does: world, visitor ID, action; returns acceptance.
Start = Callable[[World, str, Mapping[str, Any]], Mapping[str, Any]]


def _people(world: Mapping[str, Any]) -> dict[str, Actor]:
    return {item["id"]: item for item in world["actors"]}


def honor_invitations(world: World, start: Start) -> None:
    """Carry every accepted invitation one step further.

    `join_table` seats the invitee on a free chair at the inviter's table; `darts_together` sends
    both to the darts the inviter knows; `buy_drink` sends the inviter to pour an ale, which goes
    to the invitee once poured (costing nothing until the economy exists); `leave_together` sends
    the inviter home and the invitee after them once the door is free. A step the world refuses
    ends the errand with an `invitation_failed` event.

    Args:
        world: World whose `invitations` and visitors are updated in place.
        start: Starts an action through the ordinary lifecycle (`world.start_action`).
    """
    for errand in list(world["invitations"]):
        if not _step(world, errand, start):
            world["invitations"].remove(errand)


def _step(world: World, errand: Errand, start: Start) -> bool:
    # Returns whether the errand goes on.
    people = _people(world)
    host, guest = people.get(errand["from"]), people.get(errand["to"])
    if errand["stage"] == "fetching":
        return _fetched(world, errand, host, guest)
    if errand["stage"] == "following":
        return _follow(world, errand, guest, start)
    if host is None or guest is None:
        return False
    steps = _first_steps(world, errand, host, guest)
    if steps is None or not all(start(world, actor_id, action)["accepted"] for actor_id, action in steps):
        record_event(world, guest, "invitation_failed",
                     f"{host['name']} and {guest['name']} could not {KINDS[errand['kind']]}")
        return False
    if errand["kind"] == "buy_drink":
        errand.update({"stage": "fetching", "held": host["inventory"]["beer"]})
    elif errand["kind"] == "leave_together":
        errand["stage"] = "following"
    return errand["kind"] in ("buy_drink", "leave_together")


def _command(verb: str, target: str | None) -> dict[str, Any]:
    return {"id": f"{verb}:{target}", "verb": verb, "target_id": target}


def _first_steps(world: Mapping[str, Any], errand: Errand, host: Mapping[str, Any],
                 guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    # Who starts what when the invitation is accepted, or None when it cannot be done.
    return _FIRST_STEPS[errand["kind"]](world, host, guest)


def _seat_guest(world: Mapping[str, Any], host: Mapping[str, Any],
                guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    chair = free_chair(world, home_table(world, host), guest)
    return [(guest["id"], _command("sit", chair))] if chair else None


def _both_play_darts(world: Mapping[str, Any], host: Mapping[str, Any],
                     guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    board = known_place(host, "darts")
    return None if board is None else [(who["id"], _command("play_darts", board)) for who in (host, guest)]


def _both_play_dice(world: Mapping[str, Any], host: Mapping[str, Any],
                    guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    table = known_place(host, "dice_table")
    chairs = open_chairs(world, table) if table else []
    return [(who["id"], _command(PLAY, chair)) for who, chair in zip((host, guest), chairs)] if chairs else None


def _host_pours(world: Mapping[str, Any], host: Mapping[str, Any],
                guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    tap = known_place(host, "tap")
    return None if tap is None else [(host["id"], _command("take_beer", tap))]


def _host_heads_home(world: Mapping[str, Any], host: Mapping[str, Any],
                     guest: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]] | None:
    door = known_place(host, "door")
    return None if door is None else [(host["id"], _command("leave", door))]


# What accepting each kind sets in motion first: who starts which action, or None when it cannot be done.
_FIRST_STEPS: Mapping[str, Callable[..., list[tuple[str, dict[str, Any]]] | None]] = MappingProxyType({
    "join_table": _seat_guest, "darts_together": _both_play_darts, "dice_together": _both_play_dice,
    "buy_drink": _host_pours,
    "leave_together": _host_heads_home})


def _fetched(world: World, errand: Errand, host: Actor | None,
             guest: Actor | None) -> bool:
    if host is None or guest is None:
        return False
    if (host["action"] or {}).get("verb") == "take_beer":
        return True
    if host["inventory"]["beer"] > errand["held"]:
        host["inventory"]["beer"] -= 1
        guest["inventory"]["beer"] += 1
        message = f"{host['name']} bought {guest['name']} an ale"
        record_event(world, guest, "treated", message)
        think(guest, "treated", world["time"], f"{called(guest, host)} bought me an ale", message, about=host)
    return False


def _follow(world: World, errand: Errand, guest: Actor | None, start: Start) -> bool:
    # The invitee waits for the door the inviter holds, then follows them out through it.
    if guest is None or (guest["action"] or {}).get("verb") == "leave":
        return False
    host = next(item for item in [*world["actors"], *world["departed"]] if item["id"] == errand["from"])
    door = known_place(host, "door")
    if action_error(world, guest, _command("leave", door)) is None:
        start(world, guest["id"], _command("leave", door))
    return True
