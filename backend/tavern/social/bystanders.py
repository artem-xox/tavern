"""The room's part in a fight: who saw it begin, and what a guest who sees one or someone on the floor may do about it."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from tavern.body.fights import fight_of, opponent_of
from tavern.hall.memory import record_event
from tavern.hall.sight import line_visible
from tavern.hall.staff import on_staff
from tavern.hall.state import World, find_actor
from tavern.social.names import called
from tavern.social.thoughts import opinion_of, think

# How hard a guest must dislike a fighter, or how well like the other one, to wait a turn against them.
GRUDGE = -20.0
LOYALTY = 40.0
# What a guest's opinion of someone must be short of for the friend of the one they fight to be fought for.
FOE_CEILING = 10.0


def note_started(world: World) -> None:
    """Let everyone who can see a fight begin hold it against whoever started it.

    Args:
        world: World whose witnesses' thoughts and memories are updated in place, once for each fight under way.
    """
    walls = {(cell[0], cell[1]) for cell in world["map"]["blocked"]}
    for fight in world["fights"]:
        if fight["witnessed"] or fight["outcome"] is not None:
            continue
        fight["witnessed"] = True
        attacker, victim = find_actor(world, fight["a"]), find_actor(world, fight["b"])
        if attacker is None or victim is None:
            continue
        message = f"{attacker['name']} attacked {victim['name']}"
        for witness in world["actors"]:
            if witness["id"] in (attacker["id"], victim["id"]) or on_staff(witness) or not line_visible(
                    (witness["x"], witness["y"]), (attacker["x"], attacker["y"]), walls):
                continue
            record_event(world, witness, "saw_fight", f"{witness['name']} saw {message}")
            think(witness, "saw_fight", world["time"], f"{called(witness, attacker)} started a brawl in front of me",
                  message, about=attacker)


def fighters_in_sight(observation: Mapping[str, Any]) -> dict[str, str]:
    """Tell who in sight is fighting whom.

    Args:
        observation: The guest's observation, with `people` carrying each one's `fighting` (the opponent's ID).

    Returns:
        Fighter ID to opponent ID, for every fighter in sight; an empty mapping when nobody fights.
    """
    return {person["id"]: person["fighting"] for person in observation.get("people", [])
            if person.get("fighting") and person["id"] != observation["actor"]["id"]}


def reactions(observation: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    """List what a guest may do about a fight in sight or about someone lying on the floor.

    Args:
        observation: The guest's observation: `people` (each with `fighting`, `condition`, `beside`, `seat_id`,
            `table_id`) and `time`.

    Returns:
        `(verb, target_id)` pairs in stable order. A fight in sight can be watched and cheered. Each fighter within
        reach, or sitting at a table the guest could walk to, can be stepped in against (`intervene`) and, where the
        guest has a grudge against them or is a friend of the one they fight, waited a turn for (`join_fight`).
        Anyone lying on the floor, who is not a fighter, can be helped up.
    """
    actor, people = observation["actor"], {item["id"]: item for item in observation.get("people", [])}
    now = observation.get("time", -math.inf)
    fights = fighters_in_sight(observation)
    options: list[tuple[str, str | None]] = []
    if fights:
        options += [("watch_fight", None), ("cheer", None)]
    for fighter_id in sorted(fights):
        if not _reachable(people[fighter_id]):
            continue
        options.append(("intervene", fighter_id))
        if _grudge(actor, fighter_id, fights[fighter_id], now):
            options.append(("join_fight", fighter_id))
    for person_id in sorted(people):
        person = people[person_id]
        if person.get("condition") in ("down", "out") and not person.get("fighting") and _reachable(person):
            options.append(("help_up", person_id))
    return options


def _reachable(person: Mapping[str, Any]) -> bool:
    # Within reach where they are, or somewhere the guest can walk to: a table they sit at.
    return bool(person.get("beside")) or bool(person.get("seat_id") and person.get("table_id"))


def _grudge(actor: Mapping[str, Any], fighter_id: str, opponent_id: str, now: float) -> bool:
    # Against someone they hold ill of, or against the one who is beating a friend of theirs.
    if opinion_of(actor, fighter_id, now) <= GRUDGE:
        return True
    return opinion_of(actor, opponent_id, now) >= LOYALTY and opinion_of(actor, fighter_id, now) < FOE_CEILING


def friends_of_fighters(actor: Mapping[str, Any], fights: Sequence[str], now: float) -> bool:
    """Tell whether a guest likes one of the fighters in sight.

    Args:
        actor: The guest, with their relations and thoughts.
        fights: IDs of the fighters in sight.
        now: Game time.

    Returns:
        True when their opinion of one of them is `LOYALTY` or more.
    """
    return any(opinion_of(actor, fighter, now) >= LOYALTY for fighter in fights)
