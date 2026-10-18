"""Speeches from the stage: the words a speaker says, who in the hall hears them, and what the room makes of it."""

from collections.abc import Mapping
import re
from typing import Any

from tavern.body.expression import look_at
from tavern.body.hearing import EVENT_SOUNDS, emit, heard_loudness
from tavern.hall.chance import roll
from tavern.hall.memory import log_event, record_event
from tavern.hall.state import Actor, World
from tavern.social.names import called
from tavern.social.thoughts import THOUGHTS, active_thoughts, opinion_of, think

# The loudness, 0–1, from which a listener makes out a speech; a quieter one is only a murmur from the stage.
HEARD_FROM = 0.1
# Game seconds a listener keeps their eyes on the speaker, about as long as the speech lasts.
LISTENS_FOR = 8.0
# The longest part of a speaker's thought they voice, in characters: about two lines of a bubble.
MAX_THOUGHT = 160
# What the speaker opens with; the card's first catchphrase, when there is one, closes the speech.
OPENERS = ("Quiet, everyone! Hear me out!", "Friends, patrons, whoever is still sober! A word!",
           "Everybody listen! I have something to say!")
PLAIN_CLOSER = "That is all, and it is the truth!"
# Game seconds after a speech during which a listener it pleased may still cheer it.
APPLAUSE_WITHIN = 20.0
# Game seconds a guest who has just spoken lets pass before climbing up again; the room has heard them.
SPEAKS_AGAIN_AFTER = 180.0


def speech_lines(world: Mapping[str, Any], speaker: Mapping[str, Any]) -> str:
    """Write the words a guest says from the stage.

    Args:
        world: World whose seed and tick pick the opener.
        speaker: Guest speaking; their card's first catchphrase closes the speech.

    Returns:
        An opener, the first sentence of the speaker's current thought (their intention's, up to `MAX_THOUGHT`
        characters; what they have to say), and a catchphrase (or a plain closer for a guest without one).
    """
    opener = OPENERS[int(roll(world, "speech", speaker["id"]) * len(OPENERS))]
    catchphrases = ((speaker.get("card") or {}).get("catchphrases")) or []
    closer = catchphrases[0] if catchphrases else PLAIN_CLOSER
    intention = speaker.get("intention")
    if not intention:
        return f"{opener} {closer}"
    thought = intention["thought"].strip()
    sentence = (re.match(r".*?[.!?](?=\s|$)", thought) or [thought])[0]
    return f"{opener} {sentence[:MAX_THOUGHT].rstrip()} {closer}"


def _admires(listener: Mapping[str, Any], speaker: Mapping[str, Any], now: float) -> bool:
    # Liking carries it; the sociable warm to a speaker, and drink makes anyone generous.
    sociability = listener.get("traits", {}).get("sociability", 0.5)
    return opinion_of(listener, speaker["id"], now) + 40 * (sociability - 0.5) + 30 * listener.get("drunkenness", 0.0) >= 0


def give_speech(world: World, speaker: Actor, stage: Any) -> None:
    """Let a guest address the room: the words are logged, heard and remembered by everyone in earshot.

    Args:
        world: World whose log, sounds, `heard` lines and thoughts are updated in place.
        speaker: The guest on the stage; they remember their own words too.
        stage: The stage object they stand at (unused beyond being the target).
    """
    line = speech_lines(world, speaker)
    message = f'{speaker["name"]} gave a speech: "{line}"'
    record_event(world, speaker, "gave_speech", message)
    world["events"][-1]["line"] = line
    # The sound the event just made, found again by the same kind, time and cause (`hearing.emit` merges them).
    stimulus = emit(world, EVENT_SOUNDS["gave_speech"], [speaker["id"]], [speaker["x"], speaker["y"]], [], message,
                    "gave_speech")
    scene, keep = f"speech-{world['time']:.0f}", world["rules"]["conversation"]["recall_lines"]
    damping = world["rules"]["attention"]["wall_damping"]
    taken = {"speech_admired": 0, "speech_tiresome": 0}
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
    log_event(world, speaker["id"], "speech_reaction",
              f"{speaker['name']}'s speech: {taken['speech_admired']} admired it, {taken['speech_tiresome']} groaned")


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
    """Tell whether a guest gets up to speak: a famous guest with a public persona who has something to say.

    Args:
        observation: The guest's observation, with their `card` and the mind's latest `intention`.

    Returns:
        True when the card has a `persona` and the intention serves one of their obsessions or holds the goal to
        address the room; an ordinary local, or one with nothing on their mind, never climbs the stage.
    """
    actor = observation["actor"]
    card, intention = actor.get("card"), actor.get("intention")
    if not (card and card.get("persona") and intention):
        return False
    goal = intention.get("goal")
    return intention.get("obsession") is not None or bool(
        goal and goal["kind"] == "address_room" and goal["status"] == "active")
