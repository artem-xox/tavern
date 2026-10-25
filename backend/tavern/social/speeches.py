"""Speeches from the stage: when a performer speaks, who in the hall hears the number, and what the room makes of it."""

from collections.abc import Mapping
from typing import Any

from tavern.body.expression import look_at
from tavern.body.hearing import EVENT_SOUNDS, emit, heard_loudness
from tavern.hall.chance import roll
from tavern.hall.memory import log_event, record_event
from tavern.hall.state import Actor, World
from tavern.social.heckles import heckler_of
from tavern.social.names import called
from tavern.social.numbers import NUMBERS, choose_number, scripted_number
from tavern.social.social_acts import take_offence
from tavern.social.thoughts import THOUGHTS, active_thoughts, opinion_of, think

# The loudness, 0–1, from which a listener makes out a speech; a quieter one is only a murmur from the stage.
HEARD_FROM = 0.1
# Game seconds a listener keeps their eyes on the speaker, about as long as the speech lasts.
LISTENS_FOR = 8.0
# Game seconds after a speech during which a listener it pleased may still cheer it.
APPLAUSE_WITHIN = 20.0
# Game seconds a guest who has just spoken lets pass before climbing up again; the room has heard them.
SPEAKS_AGAIN_AFTER = 180.0
# Game seconds after any number during which nobody climbs up for another: eight numbers in ten minutes (live seed 5,
# 2026-10-25) made the stage a routine rather than an event.
ROOM_QUIET = 90.0
# Game seconds a performer stands on the stage waiting for their number's words before saying scripted ones.
PERFORM_WAIT = 4.0
# How the log tells each number, after the performer's name.
_TOLD = {"toast": "raised a toast to {target}", "roast": "roasted {target} from the stage",
         "pitch": "gave a speech", "confession": "made a drunken confession from the stage"}


def on_stage_for(world: Mapping[str, Any], actor: Mapping[str, Any]) -> float | None:
    """Tell how long a guest has stood on the stage with no number given yet.

    Args:
        world: Current world, with its rules' `give_speech` duration.
        actor: Guest who may be performing.

    Returns:
        Game seconds since they climbed up (from `_remaining`, saved with the action), or None when they are not up
        there doing `give_speech`, or have already given their number since climbing up.
    """
    action = actor.get("action")
    if not action or action["verb"] != "give_speech" or actor["status"] != "interacting":
        return None
    since = world["rules"]["durations"]["give_speech"] - actor["_remaining"]
    given = any(item["type"] == "gave_speech" and item["time"] >= world["time"] - since for item in actor["memory"])
    return None if given else since


def number_for(world: Mapping[str, Any], speaker: Mapping[str, Any]) -> tuple[str, str | None]:
    """Choose the number a guest on the stage gives now, from who is in the hall (`numbers.choose_number`).

    Args:
        world: Current world.
        speaker: Guest on the stage.

    Returns:
        (kind, target ID or None).
    """
    return choose_number(speaker, [item["id"] for item in world["actors"]], world["time"])


def perform_overdue(world: World) -> None:
    """Let every performer still waiting for words `PERFORM_WAIT` seconds after climbing up say scripted ones.

    Args:
        world: World whose performers may give their number now.
    """
    for actor in list(world["actors"]):
        since = on_stage_for(world, actor)
        if since is not None and since >= PERFORM_WAIT:
            kind, target_id = number_for(world, actor)
            target = next((item for item in world["actors"] if item["id"] == target_id), None)
            lines = scripted_number(actor, kind, called(actor, target) if target else None,
                                    roll(world, "speech", actor["id"]))
            perform(world, actor, kind, target_id, lines)


def _admires(listener: Mapping[str, Any], speaker: Mapping[str, Any], now: float) -> bool:
    # Liking carries it; the sociable warm to a speaker, and drink makes anyone generous.
    sociability = listener.get("traits", {}).get("sociability", 0.5)
    return opinion_of(listener, speaker["id"], now) + 40 * (sociability - 0.5) + 30 * listener.get("drunkenness", 0.0) >= 0


def perform(world: World, speaker: Actor, kind: str, target_id: str | None, lines: list[str]) -> None:
    """Let a guest on the stage give their number: it is logged, heard, remembered and taken to heart.

    Args:
        world: World whose log, sounds, `heard` lines and thoughts are updated in place.
        speaker: The guest on the stage; they remember their own words too.
        kind: The number (`numbers.NUMBERS`), kept on the event and in the speaker's memory.
        target_id: Whom an aimed number is aimed at, or None.
        lines: The words, said one after another.

    Raises:
        ValueError: The kind is unknown, an aimed number has no target in the hall, or there are no words.
    """
    target = next((item for item in world["actors"] if item["id"] == target_id), None)
    if kind not in NUMBERS or NUMBERS[kind].aimed != (target is not None) or not lines:
        raise ValueError(f"A {kind!r} number at {target_id!r} with {len(lines)} lines cannot be given")
    line = " ".join(lines)
    told = _TOLD[kind].format(target=target["name"] if target else "")
    message = f'{speaker["name"]} {told}: "{line}"'
    record_event(world, speaker, "gave_speech", message)
    event = world["events"][-1]
    event.update(line=line, number=kind, target_id=target_id)
    speaker["memory"][-1]["number"] = kind
    listeners = _hear(world, speaker, message, line)
    if target is not None:
        _land(world, speaker, kind, target, listeners, message)
    event["heckler_id"] = heckler_of(speaker, target_id, listeners, world["time"])


def _hear(world: World, speaker: Actor, message: str, line: str) -> list[Actor]:
    # Everyone in earshot keeps the words and makes up their mind about the speaker; returns who heard it.
    # The sound the event just made, found again by the same kind, time and cause (`hearing.emit` merges them).
    stimulus = emit(world, EVENT_SOUNDS["gave_speech"], [speaker["id"]], [speaker["x"], speaker["y"]], [], message,
                    "gave_speech")
    scene, keep = f"speech-{world['time']:.0f}", world["rules"]["conversation"]["recall_lines"]
    damping = world["rules"]["attention"]["wall_damping"]
    taken, listeners = {"speech_admired": 0, "speech_tiresome": 0}, []
    for listener in world["actors"]:
        own = listener["id"] == speaker["id"]
        # A sleeper is woken by a loud enough sound (`dozing.waking_sound`) and hears it like anyone; no more is asked here,
        # since `body.dozing` imports the activity table that calls this module.
        if not own and heard_loudness(world["map"], stimulus, (listener["x"], listener["y"]), damping) < HEARD_FROM:
            continue
        # A `heard.Heard` line; that module cannot be imported here without a cycle through the activity table.
        listener["heard"].append({"time": world["time"], "scene_id": scene, "speaker_id": speaker["id"],
                                  "speaker": called(listener, speaker), "line": line, "act": "boast"})
        del listener["heard"][:-keep]
        if not own:
            kind = "speech_admired" if _admires(listener, speaker, world["time"]) else "speech_tiresome"
            text = f"{called(listener, speaker)} gave a speech from the stage"
            think(listener, kind, world["time"], text, message, about=speaker)
            # They remember it the moment it is said, and turn to look at the speaker for as long as it lasts.
            listener["memory"].append({"time": world["time"], "actor_id": listener["id"], "type": "heard_speech",
                                       "message": f'{listener["name"]} heard {called(listener, speaker)} say: "{line}"'})
            del listener["memory"][:-100]
            look_at(listener, [speaker["x"], speaker["y"]], world["time"] + LISTENS_FOR, stimulus["id"])
            taken[kind] += 1
            listeners.append(listener)
    log_event(world, speaker["id"], "speech_reaction",
              f"{speaker['name']}'s speech: {taken['speech_admired']} admired it, {taken['speech_tiresome']} groaned")
    return listeners


def _land(world: World, speaker: Actor, kind: str, target: Actor, listeners: list[Actor], message: str) -> None:
    # A toast warms its target; a roast stings them, and their friends who heard it take offence as at an insult.
    if kind == "toast":
        think(target, "toasted", world["time"], f"{called(target, speaker)} raised a toast to me", message, about=speaker)
    elif kind == "roast":
        think(target, "roasted", world["time"], f"{called(target, speaker)} roasted me from the stage", message,
              about=speaker)
        for listener in listeners:
            take_offence(world, listener, speaker, target)


def applause(observation: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    """List what a guest may do about a speech that pleased them.

    Args:
        observation: The guest's observation, with their thoughts and the game `time`.

    Returns:
        `("cheer", None)` while a `speech_admired` thought is no older than `APPLAUSE_WITHIN`; otherwise nothing.
    """
    now = observation.get("time")
    fresh = now is not None and any(
        item["kind"] == "speech_admired" and now - (item["expires_at"] - THOUGHTS[item["kind"]].seconds) <= APPLAUSE_WITHIN
        for item in active_thoughts(observation["actor"].get("thoughts", []), now))
    return [("cheer", None)] if fresh else []


def spoke_lately(observation: Mapping[str, Any]) -> bool:
    """Tell whether a guest gave a speech so recently that they would not give another.

    Args:
        observation: The guest's observation, with their latest `memory` and the game `time`.

    Returns:
        True when a `gave_speech` event in their memory is under `SPEAKS_AGAIN_AFTER` seconds old.
    """
    now = observation.get("time")
    return now is not None and any(item["type"] == "gave_speech" and now - item["time"] < SPEAKS_AGAIN_AFTER
                                   for item in observation["actor"].get("memory", observation.get("memory", [])))


def performs(observation: Mapping[str, Any]) -> bool:
    """Tell whether a guest gets up to speak: a famous guest with a public persona and a number worth giving.

    Args:
        observation: The guest's observation, with their `card`, relations, drink and `memory`, the mind's latest
            `intention`, the `people` in sight and the game `time`.

    Returns:
        True when the card has a `persona`, the room has heard no number for `ROOM_QUIET` seconds, and the guest has
        a number to give (`numbers.choose_number`): a roast, a toast or a confession, or a pitch when their intention
        serves one of their obsessions or holds the goal to address the room. An ordinary local, or one with nothing
        to say, never climbs the stage.
    """
    actor = observation["actor"]
    card, intention, now = actor.get("card"), actor.get("intention"), observation.get("time") or 0.0
    if not (card and card.get("persona")) or _heard_lately(actor, now):
        return False
    kind, _ = choose_number(actor, [item["id"] for item in observation.get("people", [])], now)
    if kind != "pitch":
        return True
    if not intention:
        return False
    goal = intention.get("goal")
    return intention.get("obsession") is not None or bool(
        goal and goal["kind"] == "address_room" and goal["status"] == "active")


def _heard_lately(actor: Mapping[str, Any], now: float) -> bool:
    # Any number the guest gave or heard lately keeps them off the stage: the room is still taking the last one in.
    return any(item["type"] in ("gave_speech", "heard_speech") and now - item["time"] < ROOM_QUIET
               for item in actor.get("memory", []))
