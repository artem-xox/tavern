"""Heckles: who shouts back at a stage number from the floor, the heckle itself, and the performer's comeback."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.hall.memory import record_event
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, World
from tavern.social.names import called
from tavern.social.thoughts import opinion_of, think

# A listener heckles a performer they think this little of, as a guest insults one they dislike (`conversation.DISLIKED`,
# which cannot be imported here: its acts import the activity table, which gives the speeches).
HECKLES_AT = -10.0


def heckler_of(performer: Mapping[str, Any], target_id: str | None, listeners: Sequence[Mapping[str, Any]],
               now: float) -> str | None:
    """Choose who shouts back at a number from the floor.

    Args:
        performer: Guest on the stage.
        target_id: The one the number was aimed at, or None.
        listeners: Guests who heard it, the performer excepted.
        now: Game time, for opinions.

    Returns:
        The target's ID when they heard it; otherwise the guest who thinks least of the performer, at `HECKLES_AT` or
        below (the lower ID on a tie); None when nobody minds. Staff at work never heckle.
    """
    guests = [item for item in listeners if item["id"] != performer["id"] and not on_staff(item)]
    if target_id is not None and any(item["id"] == target_id for item in guests):
        return target_id
    hostile = sorted((opinion_of(item, performer["id"], now), item["id"]) for item in guests)
    return hostile[0][1] if hostile and hostile[0][0] <= HECKLES_AT else None


def heckle(world: World, heckler: Actor, performer: Actor, line: str) -> None:
    """Let a guest shout at a performer from the floor: the room hears it, and the performer takes it badly.

    Args:
        world: World whose log, sounds and thoughts are updated in place.
        heckler: Guest shouting.
        performer: Guest on the stage, who keeps a `heckled` thought about the heckler.
        line: The words shouted.
    """
    message = f'{heckler["name"]} heckled {performer["name"]}: "{line}"'
    record_event(world, heckler, "heckled", message)
    world["events"][-1].update(line=line, performer_id=performer["id"])
    think(performer, "heckled", world["time"], f"{called(performer, heckler)} heckled my speech: “{line}”", message,
          about=heckler)


def answer_heckle(world: World, performer: Actor, heckler: Actor, line: str) -> None:
    """Let a performer answer a heckle: the room hears the comeback.

    Args:
        world: World whose log and sounds are updated in place.
        performer: Guest answering.
        heckler: Guest who heckled them.
        line: The comeback.
    """
    record_event(world, performer, "heckle_answered", f'{performer["name"]} answered {heckler["name"]}: "{line}"')
    world["events"][-1].update(line=line, heckler_id=heckler["id"])


def scripted_heckle(heckler: Mapping[str, Any], performer: Mapping[str, Any]) -> str:
    """Write a heckle without a writer.

    Args:
        heckler: Guest shouting; their card's first catchphrase follows the jeer.
        performer: Guest on the stage, named as the heckler knows them.

    Returns:
        One short shout.
    """
    catchphrases = (heckler.get("card") or {}).get("catchphrases") or []
    tail = f" {catchphrases[0]}" if catchphrases else ""
    return f"Get off the stage, {called(heckler, performer)}!{tail}"


def scripted_comeback(performer: Mapping[str, Any], heckler: Mapping[str, Any]) -> str:
    """Write a performer's comeback without a writer.

    Args:
        performer: Guest on the stage.
        heckler: Guest who heckled them, named as the performer knows them.

    Returns:
        One short answer.
    """
    return f"Sit down, {called(performer, heckler)}. Nobody bought a ticket to hear you."
