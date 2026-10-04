"""Overhearing: each spoken line is a sound, and guests outside the scene catch its act and gist by distance."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from tavern.body.hearing import Sound, Stimulus, emit, salience
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social import facts
from tavern.social.conversation import ACTS
from tavern.social.names import called
from tavern.social.scenes import Conversation, Turn
from tavern.social.social_acts import take_offence
from tavern.social.thoughts import friends_of, learn_name

# Talk is as loud as the chat a `talk` starts with but carries across a table or two; laughter
# carries further; an insult is loud enough to turn heads, yet stays below what interrupts a
# middling listener at the next table (see `attention`).
_SPEECH = Sound("chat", 0.25, 10.0, "voices talking")
_LOUD: Mapping[str, Sound] = MappingProxyType({
    "joke": Sound("laughter", 0.25, 14.0, "laughter"),
    "insult": Sound("insult", 0.4, 14.0, "an angry insult"),
})
TURN_SOUNDS: Mapping[str, Sound] = MappingProxyType({act: _LOUD.get(act, _SPEECH) for act in ACTS})

# Salience at which a listener outside the scene catches what kind of line it was, and at which
# they make out the words: who spoke to whom, and what was said.
OVERHEAR_ACT = 0.08
OVERHEAR_GIST = 0.15


def overhear_turn(world: World, scene: Conversation, turn: Turn) -> Stimulus:
    """Make a spoken line heard: a sound from the whole company, caught by guests outside it.

    A listener whose salience (`hearing.salience`) reaches `OVERHEAR_ACT` notices the act;
    one reaching `OVERHEAR_GIST` makes out the words. Making out an introduction teaches the
    speaker's name; making out news gives them a copy (`facts.overhear`); making out an insult to someone the listener likes makes them resent the
    insulter (`social_acts.take_offence`); any insult noticed is remembered.

    Args:
        world: World whose stimuli and visitors are updated in place.
        scene: Scene the line was spoken in, before the act takes effect.
        turn: The spoken line.

    Returns:
        The sound, pending for attention at the end of the tick. Its sources are everyone in
        the scene, so none of them attends to their own conversation.
    """
    people = {item["id"]: item for item in world["actors"]}
    speaker = people[turn["speaker"]]
    addressee = people.get(turn["addressee"]) if turn["addressee"] is not None else None
    cause = f"{speaker['name']} to {addressee['name'] if addressee else 'everyone'}: \"{turn['line']}\""
    stimulus = emit(world, TURN_SOUNDS[turn["act"]], list(scene["participants"]), [speaker["x"], speaker["y"]],
                    [addressee["id"]] if addressee else [], cause, "turn")
    for listener in world["actors"]:
        if listener["id"] in scene["participants"]:
            continue
        level = salience(world, stimulus, listener, friends_of(listener))
        if level >= OVERHEAR_ACT:
            _catch(world, listener, turn, speaker, addressee, level >= OVERHEAR_GIST)
    return stimulus


def _catch(world: World, listener: Actor, turn: Turn, speaker: Actor,
           addressee: Actor | None, gist: bool) -> None:
    if gist and turn["act"] == "introduce":
        learn_name(listener, speaker, False, world["actors"])
    if gist and turn["act"] == "share_news":
        facts.overhear(world, listener, speaker, turn)
    if turn["act"] != "insult":
        return
    if not gist or addressee is None:
        record_event(world, listener, "overheard", f"{listener['name']} overheard an insult")
        return
    record_event(world, listener, "overheard", f"{listener['name']} overheard {called(listener, speaker)} insult "
                 f"{called(listener, addressee)}: \"{turn['line']}\"")
    take_offence(world, listener, speaker, addressee)
