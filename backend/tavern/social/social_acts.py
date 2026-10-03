"""What friendly and touchy speech acts do to the listeners: thoughts, softened grudges, and names."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.state import Actor, World
from tavern.social.names import called
from tavern.social.scenes import Conversation
from tavern.social.thoughts import familiarity_of, learn_name, opinion_of, soften, think

# A listener who thinks this well of a boaster enjoys the tale whatever their patience.
LIKED = 10.0
# A listener who thinks this well of someone (or counts them a friend) resents an insult to them.
FOND = 20.0


def _others(world: Mapping[str, Any], scene: Mapping[str, Any], speaker: Mapping[str, Any]) -> list[Actor]:
    return [item for item in world["actors"] if item["id"] in scene["participants"] and item["id"] != speaker["id"]]


def _listeners(world: Mapping[str, Any], scene: Mapping[str, Any], speaker: Mapping[str, Any],
               addressee: Actor | None) -> list[Actor]:
    # A line to nobody in particular reaches everyone else in the scene.
    return [addressee] if addressee is not None else _others(world, scene, speaker)


def _feel(world: Mapping[str, Any], listener: Actor, kind: str, speaker: Mapping[str, Any],
          words: str) -> None:
    # `words` completes "{speaker} ... me" in the listener's own terms and, naming them, in the log.
    think(listener, kind, world["time"], f"{called(listener, speaker)} {words} me",
          f"{speaker['name']} {words} {listener['name']}", about=speaker)


def compliment(world: World, scene: Conversation, speaker: Actor,
               addressee: Actor | None) -> None:
    """Warm the addressee (everyone else, if nobody in particular) to the speaker.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor paying the compliment.
        addressee: Visitor complimented, or None.
    """
    for listener in _listeners(world, scene, speaker, addressee):
        _feel(world, listener, "compliment", speaker, "complimented")


def boast(world: World, scene: Conversation, speaker: Actor,
          addressee: Actor | None) -> None:
    """Let everyone else in the scene take a boast: mildly impressed or mildly put off.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor boasting; a boast is heard by the whole company, whoever it addresses.
        addressee: Unused.
    """
    for listener in _others(world, scene, speaker):
        # A patient listener (a missing trait counts as middling) or one who likes the boaster
        # enjoys the tale; an impatient one is tired by it.
        liked = opinion_of(listener, speaker["id"], world["time"]) >= LIKED
        if liked or listener["traits"].get("patience", 0.5) >= 0.5:
            _feel(world, listener, "boast_admired", speaker, "told a fine tale of themselves to")
        else:
            _feel(world, listener, "boast_tiresome", speaker, "boasted at")


def _answered(world: Mapping[str, Any], scene: Mapping[str, Any], speaker: Mapping[str, Any],
              addressee: Actor | None) -> Actor | None:
    # Agreeing with nobody in particular answers whoever spoke last, if still there.
    if addressee is not None:
        return addressee
    earlier = [turn["speaker"] for turn in scene["turns"][:-1] if turn["speaker"] != speaker["id"]]
    return next((item for item in _others(world, scene, speaker) if earlier and item["id"] == earlier[-1]), None)


def agree(world: World, scene: Conversation, speaker: Actor,
          addressee: Actor | None) -> None:
    """Let the one agreed with think a little better of the speaker.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor agreeing.
        addressee: Visitor agreed with, or None for whoever spoke last.
    """
    listener = _answered(world, scene, speaker, addressee)
    if listener is not None:
        _feel(world, listener, "agreed", speaker, "agreed with")


def disagree(world: World, scene: Conversation, speaker: Actor,
             addressee: Actor | None) -> None:
    """Let the one disagreed with think a little worse of the speaker.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor disagreeing.
        addressee: Visitor disagreed with, or None for whoever spoke last.
    """
    listener = _answered(world, scene, speaker, addressee)
    if listener is not None:
        _feel(world, listener, "disagreed", speaker, "disagreed with")


def apologize(world: World, scene: Conversation, speaker: Actor,
              addressee: Actor | None) -> None:
    """Halve the latest grudge the addressee (everyone else, if nobody in particular) holds against the speaker.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor apologizing.
        addressee: Visitor apologized to, or None.
    """
    for listener in _listeners(world, scene, speaker, addressee):
        soften(listener, speaker["id"], world["time"])


def introduce(world: World, scene: Conversation, speaker: Actor,
              addressee: Actor | None) -> None:
    """Teach everyone else in the scene the speaker's name; strangers become acquaintances.

    Args:
        world: Current world; old friends of a listener present in the hall learn it too.
        scene: Speaker's scene.
        speaker: Visitor introducing themselves; everyone in the scene hears the name.
        addressee: Unused.
    """
    for listener in _others(world, scene, speaker):
        learn_name(listener, speaker, True, world["actors"])


def take_offence(world: Mapping[str, Any], listener: Actor, insulter: Mapping[str, Any],
                 target: Mapping[str, Any]) -> bool:
    """Let a guest who heard an insult resent it if they like whoever was insulted.

    Args:
        world: Current world.
        listener: Visitor who heard it, in the scene or overhearing it.
        insulter: Visitor who insulted.
        target: Visitor insulted.

    Returns:
        Whether they took offence: they count the target a friend or think at least `FOND` of
        them. Neither party to the insult takes offence this way.
    """
    if listener["id"] in (insulter["id"], target["id"]):
        return False
    fond = familiarity_of(listener, target["id"]) == "friend" or opinion_of(
        listener, target["id"], world["time"]) >= FOND
    if fond:
        think(listener, "friend_insulted", world["time"], f"{called(listener, insulter)} insulted "
              f"{called(listener, target)}", f"{insulter['name']} insulted {target['name']}", about=insulter)
    return fond
