"""Signature acts: what a famous guest's own item lets them do (film, protest, interview), and what the room makes of it."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from tavern.body.fights import running
from tavern.body.hearing import Sound, emit, heard_loudness
from tavern.hall.memory import record_event
from tavern.hall.sightlines import line_visible
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, World
from tavern.social.names import called
from tavern.social.quarrels import heat
from tavern.social.scenes import conversation_of
from tavern.social.speeches import HEARD_FROM
from tavern.social.thoughts import opinion_of, think

Guest = TypeVar("Guest", bound=Mapping[str, Any])

# Game seconds after raising a protest sign during which the holder does not raise it again; the room has got the message.
RAISES_AGAIN_AFTER = 180.0
# The insults two guests have traded (see `quarrels.heat`) from which a scene is a quarrel worth filming, not a single remark.
FILMABLE_HEAT = 2
# The shout of a raised protest sign: heard across the hall, loud enough to turn heads but not to break anything off.
PROTEST = Sound("protest", 0.6, 30.0, "a protest shouted across the hall")


def log_act(world: World, actor: Actor, verb: str, item: str, subjects: Sequence[str], message: str) -> None:
    """Log one use of a signature item: the event, with the verb, the item and whom it concerned.

    Args:
        world: World whose log is appended to.
        actor: Guest using the item; they remember it.
        verb: The act (`Activity.verb`).
        item: The `ITEMS` kind used.
        subjects: IDs of the guests it was done to or about; empty for none.
        message: What happened, in words.
    """
    record_event(world, actor, "signature_act", message)
    for entry in (world["events"][-1], actor["memory"][-1]):
        entry.update(verb=verb, item=item, subject=list(subjects))


def in_sight(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[Actor]:
    """List the guests a guest sees from where they stand: anyone not behind a wall, staff left out.

    Args:
        world: Current world; only walls hide people.
        actor: The viewer.

    Returns:
        The other guests in sight, in actor order.
    """
    walls = set(map(tuple, world["map"]["blocked"]))
    return [other for other in world["actors"] if other["id"] != actor["id"] and not on_staff(other)
            and line_visible((actor["x"], actor["y"]), (other["x"], other["y"]), walls)]


def accused_of(actor: Mapping[str, Any], candidates: Sequence[Guest], now: float) -> Guest | None:
    """Pick whom a protest is aimed at: the guest the protester thinks worst of.

    Args:
        actor: The protester, with their relations and thoughts.
        candidates: The guests present, each with an `id`.
        now: Current game time.

    Returns:
        The one with the lowest opinion; a tie goes to the lower ID, so the choice does not depend on the order of the
        room. None when nobody is present.
    """
    return min(candidates, key=lambda other: (opinion_of(actor, other["id"], now), other["id"]), default=None)


def raised_lately(observation: Mapping[str, Any]) -> bool:
    """Tell whether a guest raised their protest sign so recently that they would not raise it again.

    Args:
        observation: The guest's observation, with their memory and the game `time`.

    Returns:
        True when a `raise_sign` act in their memory is under `RAISES_AGAIN_AFTER` seconds old.
    """
    now = observation.get("time")
    return now is not None and any(item["type"] == "signature_act" and item.get("verb") == "raise_sign"
                                   and now - item["time"] < RAISES_AGAIN_AFTER
                                   for item in observation["actor"].get("memory", []))


def _footage(world: Mapping[str, Any], seen: Sequence[Actor]) -> list[str]:
    # The loudest thing in sight: a fight, else a quarrel, else a speech; nothing is a selfie.
    ids = {other["id"] for other in seen}
    for fight in running(world):
        if ids & {fight["a"], fight["b"]}:
            return [fight["a"], fight["b"]]
    for scene in world["conversations"]:
        if ids & set(scene["participants"]) and heat(scene) >= FILMABLE_HEAT:
            return list(scene["participants"])
    return [other["id"] for other in seen
            if other["action"] and other["action"]["verb"] == "give_speech" and other["status"] == "interacting"][:1]


def film_room(world: World, actor: Actor, target: Any) -> None:
    """Finish filming: those caught on camera think ill of it, and the event is logged.

    Args:
        world: World whose guests, thoughts and log are updated in place.
        actor: Guest filming.
        target: Unused: filming has no target.
    """
    seen = in_sight(world, actor)
    subjects = [other for other in world["actors"] if other["id"] in _footage(world, seen)]
    for subject in subjects:
        message = f"{actor['name']} filmed {subject['name']}"
        think(subject, "filmed", world["time"], f"{called(subject, actor)} filmed me on a phone", message, about=actor)
    names = " and ".join(subject["name"] for subject in subjects)
    log_act(world, actor, "livestream", "phone", [subject["id"] for subject in subjects],
            f"{actor['name']} films {names} for the followers" if subjects else f"{actor['name']} films a selfie")


def raise_sign(world: World, actor: Actor, target: Any) -> None:
    """Raise a protest sign at the guest the holder thinks worst of: the hall hears it, the accused is shamed.

    Args:
        world: World whose sounds, guests, thoughts and log are updated in place.
        actor: Guest with the sign.
        target: Unused: the world, not the choice, picks the accused.

    Raises:
        ValueError: Nobody else is in sight to protest at.
    """
    accused = accused_of(actor, in_sight(world, actor), world["time"])
    if accused is None:
        raise ValueError(f"{actor['name']} has nobody to raise a protest sign at")
    message = f"{actor['name']} raises a protest sign at {accused['name']} and shouts"
    log_act(world, actor, "raise_sign", "protest_sign", [accused["id"]], message)
    stimulus = emit(world, PROTEST, [actor["id"]], [actor["x"], actor["y"]], [accused["id"]], message, "signature_act")
    think(accused, "shamed", world["time"], f"{called(accused, actor)} shamed me with a protest sign", message, about=actor)
    damping = world["rules"]["attention"]["wall_damping"]
    for listener in world["actors"]:
        heard = heard_loudness(world["map"], stimulus, (listener["x"], listener["y"]), damping) >= HEARD_FROM
        if listener["id"] not in (actor["id"], accused["id"]) and heard and \
                opinion_of(listener, accused["id"], world["time"]) < 0:
            think(listener, "protest_cheered", world["time"], f"{called(listener, actor)} stood up to someone I dislike",
                  message, about=actor)


def open_interview(world: World, actor: Actor, partner: Actor) -> None:
    """Turn the scene a guest has opened with a microphone into an interview, and let the interviewee take it to heart.

    Args:
        world: World whose scene, thoughts and log are updated in place.
        actor: Interviewer, who has just opened or joined a scene with the partner.
        partner: The guest interviewed.
    """
    scene = conversation_of(world, actor["id"])
    # A scene the interviewer only joined keeps the subject it had.
    if scene is not None and scene["participants"][0] == actor["id"]:
        scene["topic"] = f"{actor['name']}'s microphone interview of {partner['name']}"
    friendly = opinion_of(partner, actor["id"], world["time"]) >= 0
    message = f"{actor['name']} sticks a microphone in {partner['name']}'s face"
    log_act(world, actor, "interview_guest", "microphone", [partner["id"]], message)
    if friendly:
        think(partner, "interviewed", world["time"], f"{called(partner, actor)} interviewed me", message, about=actor)
    else:
        think(partner, "grilled", world["time"], f"{called(partner, actor)} grilled me with a microphone", message,
              about=actor)
