"""Invitations: one guest invites another in a scene, the invitee answers, and the game carries it out.

An `invite` act leaves a pending `Invitation` in its scene (`scenes.Conversation.invitation`); it
lapses when either guest leaves the scene. On `accept` it becomes an `Errand` in
`world["invitations"]`, which `errands.honor_invitations` sets in motion through the ordinary action
lifecycle (`world.start_action`), so the usual rules decide whether each step is possible.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, NotRequired, TypedDict

from tavern.body.items import ITEMS
from tavern.hall.memory import record_event
from tavern.hall.room import find_object
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, World
from tavern.hall.validation import number
from tavern.social.dice import open_chairs
from tavern.social.names import called
from tavern.social.scenes import Conversation

# Each kind and how it is told: "{inviter} invited {invitee} to ...".
KINDS: Mapping[str, str] = MappingProxyType({
    "join_table": "come and sit at their table",
    "darts_together": "play darts together",
    "dice_together": "play a game of dice",
    "buy_drink": "have an ale on them",
    "leave_together": "walk home together",
    "move_together": "move to a free table together",
})
# accepted: to be set in motion; fetching: the inviter pours the ale; carrying: the inviter walks back with
# it to hand it over; following: the inviter has set off for the door and the invitee follows once it is free;
# seating: those sent are on their way to chairs at a table (`table`) and the errand lasts until they sit.
STAGES = ("accepted", "fetching", "carrying", "following", "seating")

# `from` is a Python keyword, hence the functional form.
Invitation = TypedDict("Invitation", {"kind": str, "from": str, "to": str})
# `held` is the mugs the inviter held when an errand began; `since` the game time carrying began; `unasked`
# marks an errand nobody invited (a guest bringing a drink of their own accord), which the other knows nothing of;
# `table` is the table a `seating` errand goes to.
Errand = TypedDict("Errand", {"kind": str, "from": str, "to": str, "stage": str, "held": int,
                              "since": NotRequired[float], "unasked": NotRequired[bool],
                              "table": NotRequired[str]})


def _people(world: Mapping[str, Any]) -> dict[str, Actor]:
    return {item["id"]: item for item in world["actors"]}


def known_place(actor: Mapping[str, Any], kind: str) -> str | None:
    """Pick the place of a kind a visitor knows, so that the choice is reproducible.

    Args:
        actor: Visitor with `knowledge`.
        kind: Object kind such as `tap` (a tap must still have stock when last seen).

    Returns:
        The first such place by ID, or None.
    """
    found = sorted(key for key, item in actor["knowledge"]["objects"].items() if item["kind"] == kind
                   and (kind != "tap" or item.get("stock", 0) > 0))
    return found[0] if found else None


def home_table(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    """Tell which table a guest calls theirs.

    Args:
        world: Current world.
        actor: Visitor.

    Returns:
        The table of the chair they sit on, else of their own seat, or None.
    """
    seat = find_object(world["map"], actor.get("seat_id") or actor.get("favorite_seat_id"))
    return seat.get("table_id") if seat else None


def free_chair(world: Mapping[str, Any], table_id: str | None, guest: Mapping[str, Any]) -> str | None:
    """Find a chair at a table a guest may take without wronging anyone.

    Args:
        world: Current world.
        table_id: Table, or None.
        guest: Visitor who would sit.

    Returns:
        The first chair in map order nobody sits on, reserves or calls their own seat (except
        the guest), or None.
    """
    taken = {item["seat_id"] for item in world["actors"]} | {
        item["favorite_seat_id"] for item in world["actors"] if item["id"] != guest["id"]}
    return next((item["id"] for item in world["map"]["objects"] if item["kind"] == "chair"
                 and table_id is not None and item.get("table_id") == table_id and item["id"] not in taken
                 and item["reserved_by"] in (None, guest["id"])), None)


def open_chairs_at(world: Mapping[str, Any], table_id: str, guests: Sequence[Mapping[str, Any]]) -> list[str]:
    """List the chairs at a table that the given guests may take together without wronging anyone.

    Args:
        world: Current world.
        table_id: Table.
        guests: Visitors who would sit.

    Returns:
        Chairs in map order that nobody sits on, reserves or calls their own seat (except the guests).
    """
    ours = {item["id"] for item in guests}
    taken = {item["seat_id"] for item in world["actors"]} | {
        item["favorite_seat_id"] for item in world["actors"] if item["id"] not in ours}
    return [item["id"] for item in world["map"]["objects"] if item["kind"] == "chair"
            and item.get("table_id") == table_id and item["id"] not in taken
            and item["reserved_by"] in (None, *ours)]


def free_table(world: Mapping[str, Any], host: Mapping[str, Any], guest: Mapping[str, Any]) -> str | None:
    """Find a table two guests may move to together.

    Args:
        world: Current world.
        host: Guest who invites, whose position decides which table is nearest.
        guest: Guest invited.

    Returns:
        The table that is home to neither and has two chairs they may take (see `open_chairs_at`); of several,
        the nearest to the host by cells (Manhattan distance to the table), and a tie goes to the one first in
        map order so that the choice is reproducible. None when there is no such table.
    """
    homes = {home_table(world, host), home_table(world, guest)}
    tables = [item for item in world["map"]["objects"] if item["kind"] == "table" and item["id"] not in homes]
    tables.sort(key=lambda item: abs(item["x"] - host["x"]) + abs(item["y"] - host["y"]))
    return next((item["id"] for item in tables if len(open_chairs_at(world, item["id"], (host, guest))) >= 2), None)


def offered_kinds(world: Mapping[str, Any], scene: Mapping[str, Any], speaker: Mapping[str, Any]) -> list[str]:
    """List the invitations a guest could make in their scene now.

    Args:
        world: Current world.
        scene: Their scene.
        speaker: Visitor about to speak.

    Returns:
        Kinds in `KINDS` order: `join_table` when their table has a free chair and someone in
        the scene sits elsewhere; `move_together` when a free table exists for them and someone in the scene
        (see `free_table`); the others when they know darts, a tap with ale, or a door. None
        for staff, or when everyone else in the scene is staff.
    """
    if scene["invitation"] is not None:
        return []
    table, people = home_table(world, speaker), _people(world)
    # Staff are at work behind the bar: they invite nobody, and nobody invites them away from it.
    if on_staff(speaker) or all(on_staff(people[item]) for item in scene["participants"] if item != speaker["id"]):
        return []
    outsiders = [people[item] for item in scene["participants"] if item != speaker["id"]
                 and home_table(world, people[item]) != table]
    company = [item for item in people.values() if item["id"] in scene["participants"] and item["id"] != speaker["id"]
               and not on_staff(item)]
    offered = {"join_table": bool(outsiders) and free_chair(world, table, outsiders[0]) is not None,
               "darts_together": known_place(speaker, "darts") is not None,
               "dice_together": _dice_table_free(world, speaker),
               "buy_drink": known_place(speaker, "tap") is not None,
               "leave_together": known_place(speaker, "door") is not None,
               "move_together": any(free_table(world, speaker, item) is not None for item in company)}
    return [kind for kind in KINDS if offered[kind]]


def _dice_table_free(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    table = known_place(actor, "dice_table")
    return table is not None and bool(open_chairs(world, table))


def pending_for(scene: Mapping[str, Any], actor_id: str) -> Invitation | None:
    """Find the invitation a guest in a scene is to answer.

    Args:
        scene: Their scene.
        actor_id: Visitor.

    Returns:
        The pending invitation addressed to them, or None.
    """
    invitation = scene["invitation"]
    return invitation if invitation is not None and invitation["to"] == actor_id else None


def invite(world: World, scene: Conversation, speaker: Actor,
           addressee: Actor | None) -> None:
    """Leave the invitation of the turn just spoken pending in its scene (the `invite` act).

    Args:
        world: Current world.
        scene: Scene whose last turn carries the `invitation` kind, validated by `turns.check_turn`.
        speaker: Inviter.
        addressee: Invitee.
    """
    if addressee is None:
        raise ValueError("An invitation needs an addressee")
    scene["invitation"] = {"kind": scene["turns"][-1]["invitation"], "from": speaker["id"], "to": addressee["id"]}


def accept(world: World, scene: Conversation, speaker: Actor,
           addressee: Actor | None) -> None:
    """Accept the invitation pending for the speaker (the `accept` act); it is carried out this tick.

    Args:
        world: World whose `invitations` receive the errand.
        scene: Speaker's scene.
        speaker: Invitee answering.
        addressee: Unused: the answer goes to whoever invited them.
    """
    invitation = pending_for(scene, speaker["id"])
    if invitation is None:
        return
    scene["invitation"] = None
    world["invitations"].append(Errand(**invitation, stage="accepted", held=0))
    record_event(world, speaker, "invitation_accepted", f"{speaker['name']} accepted an invitation to "
                 f"{KINDS[invitation['kind']]} from {_people(world)[invitation['from']]['name']}")


def begin_errand(world: World, host: Actor, guest: Actor, kind: str, unasked: bool = False) -> None:
    """Send a guest on an errand for another that no invitation asked for.

    Args:
        world: World whose `invitations` receive the errand, to be set in motion by `errands.honor_invitations`.
        host: Guest who goes.
        guest: Guest it is for.
        kind: One of `KINDS`.
        unasked: Whether nobody invited it, so that the guest it is for does not know of it.
    """
    errand: Errand = {"kind": kind, "from": host["id"], "to": guest["id"], "stage": "accepted", "held": 0}
    world["invitations"].append({**errand, "unasked": True} if unasked else errand)


def errand_parties(world: Mapping[str, Any]) -> list[str]:
    """List the guests who are on an errand or being served by one.

    Args:
        world: Current world.

    Returns:
        Sorted IDs of whoever an accepted invitation or an errand names, host or guest.
    """
    return sorted({who for errand in world["invitations"] for who in (errand["from"], errand["to"])})


def fetch_error(world: Mapping[str, Any], host: Mapping[str, Any], guest: Mapping[str, Any]) -> str | None:
    """Tell why a guest may not be sent to fetch another a drink, apart from where they stand.

    Args:
        world: Current world.
        host: Guest who would go, who needs a hand free for the mug.
        guest: Guest it is for.

    Returns:
        A human-readable refusal reason, or None.
    """
    if host["inventory"]["beer"] >= ITEMS["beer"].hands:
        return f"{host['name']} has no free hand for another mug"
    busy = errand_parties(world)
    return next((f"{who['name']} is already on an errand" for who in (host, guest) if who["id"] in busy), None)


def decline(world: World, scene: Conversation, speaker: Actor,
            addressee: Actor | None) -> None:
    """Decline the invitation pending for the speaker (the `decline` act); nothing else follows.

    Args:
        world: World whose log records it.
        scene: Speaker's scene.
        speaker: Invitee answering.
        addressee: Unused.
    """
    invitation = pending_for(scene, speaker["id"])
    if invitation is not None:
        scene["invitation"] = None
        record_event(world, speaker, "invitation_declined", f"{speaker['name']} declined an invitation to "
                     f"{KINDS[invitation['kind']]} from {_people(world)[invitation['from']]['name']}")


def invitations_of(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[dict[str, Any]]:
    """List the invitations a guest is part of, pending or under way, for their observation.

    Args:
        world: Current world.
        actor: Visitor.

    Returns:
        Per invitation: `kind`, `from`, `to`, `stage` ("pending" for one awaiting an answer) and
        `with`, what the guest calls the other party (see `names.called`); `unasked` for an errand
        nobody invited, which only the one who goes is told of.
    """
    people = {item["id"]: item for item in [*world["actors"], *world["departed"]]}
    pending = [{**item, "stage": "pending"} for item in (scene["invitation"] for scene in world["conversations"])
               if item is not None]
    # Whoever an unasked errand is for knows nothing of it.
    found = [item for item in [*pending, *world["invitations"]] if actor["id"] in (item["from"], item["to"])
             and not (item.get("unasked") and item["to"] == actor["id"])]
    return [{"kind": item["kind"], "from": item["from"], "to": item["to"], "stage": item["stage"],
             "with": called(actor, people[item["to"] if item["from"] == actor["id"] else item["from"]]),
             **({"unasked": True} if item.get("unasked") else {})}
            for item in found]


def invitation_note(observation: Mapping[str, Any]) -> str:
    """Tell a guest's pending and accepted invitations in words, for the briefing.

    Args:
        observation: Personal observation; one built outside the world may lack `invitations`.

    Returns:
        Sentences such as "They agreed to walk home together with Bea." or "".
    """
    me, notes = observation["actor"]["id"], []
    for item in observation.get("invitations", []):
        what, other = KINDS[item["kind"]], item["with"]
        if item.get("unasked"):
            notes.append(f"They are fetching {other} an ale.")
        elif item["stage"] == "pending":
            notes.append(f"They invited {other} to {what} and await an answer." if item["from"] == me
                         else f"{other} invited them to {what}; they have yet to answer.")
        else:
            notes.append(f"They agreed with {other} to {what}.")
    return " ".join(notes)


def check_invitations(world: Mapping[str, Any]) -> None:
    """Check a saved world's invitations: each scene's pending one and the errands under way.

    Args:
        world: Untrusted saved world with `conversations` (already checked) and `invitations`.

    Raises:
        ValueError: A pending invitation or an errand is malformed, has an unknown kind or
            stage, or names guests outside its scene or the evening.
    """
    for scene in world["conversations"]:
        item = scene["invitation"]
        if item is not None and (not isinstance(item, dict) or set(item) != {"kind", "from", "to"}
                                 or not _valid(item, scene["participants"])):
            raise ValueError(f"Invalid saved pending invitation {item!r}")
    errands, guests = world.get("invitations"), [item["id"] for item in [*world["actors"], *world["departed"]]]
    if not isinstance(errands, list):
        raise ValueError("Saved invitations must be a list")
    for item in errands:
        if not isinstance(item, dict) or not Errand.__required_keys__ <= set(item) <= set(Errand.__annotations__) \
                or not _valid(item, guests) or item["stage"] not in STAGES or type(item["held"]) is not int:
            raise ValueError(f"Invalid saved invitation {item!r}")
        number(item["held"], "Saved ale held", 0, float("inf"))
        if "unasked" in item and type(item["unasked"]) is not bool:
            raise ValueError(f"Saved invitation {item!r} must flag whether it was unasked with a boolean")
        # Only an errand on its way to chairs names the table it goes to.
        if ("table" in item) != (item["stage"] == "seating") or (
                "table" in item and item["table"] not in {obj["id"] for obj in world["map"]["objects"]
                                                          if obj["kind"] == "table"}):
            raise ValueError(f"Saved invitation {item!r} must name a table exactly while it is seating")
        # Only an errand that is carrying has a start, and it cannot lie in the future.
        if ("since" in item) != (item["stage"] == "carrying"):
            raise ValueError(f"Saved invitation {item!r} must have a start exactly while it is carrying")
        if "since" in item:
            number(item["since"], "Saved carrying start", 0, world["time"])


def _valid(item: Mapping[str, Any], guests: Sequence[str]) -> bool:
    return item["kind"] in KINDS and item["from"] in guests and item["to"] in guests and item["from"] != item["to"]
