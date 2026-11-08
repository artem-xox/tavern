"""The player's commands: check one and apply it to the world and the mind loop."""

from collections.abc import Mapping
from typing import Any

from tavern.evening.mind_loop import MindLoop
from tavern.hall.memory import log_event
from tavern.hall.state import World
from tavern.mind.scripted import MAX_LINE
from tavern.social.scenes import conversation_of


def steer(world: World, mind: MindLoop, command: Mapping[str, Any]) -> None:
    """Take the wheel of the played guest for the player, or give it back to the guest's own mind (autopilot).

    Taking it overrules a decision in flight, cancels an intention and an invitation answer in flight, and drops a
    claim on the guest's next line, so that nothing a model answers later reaches the guest. Giving it back lets
    the guest's mind decide and take stock again at once.

    Args:
        world: Authoritative world, whose `player` and event log are updated in place.
        mind: The evening's requests in flight.
        command: `{"type": "steer", "on": bool}`.

    Raises:
        ValueError: The evening has no player, or `on` is not true or false. Nothing changes then.
    """
    player = world["player"]
    if player is None:
        raise ValueError("steer needs a player, and this evening has none")
    on = command.get("on")
    if type(on) is not bool:
        raise ValueError(f"steer needs on to be true or false, not {on!r}")
    actor_id = player["actor_id"]
    player["steering"] = on
    if on:
        _drop_requests(world, mind, actor_id)
    else:
        mind.next_decision.pop(actor_id, None)
        mind.next_intention.pop(actor_id, None)
    people = [*world["actors"], *world["departed"], *world["expected"]]
    name = next(item["name"] for item in people if item["id"] == actor_id)
    log_event(world, actor_id, "steer", f"{name} is played by a person now" if on else f"{name} is on autopilot")


def _drop_requests(world: World, mind: MindLoop, actor_id: str) -> None:
    mind.overrule(actor_id)
    if actor_id in mind.pending:
        mind.courier.cancel(mind.pending.pop(actor_id)[0])
        mind.asked_at.pop(actor_id, None)
    if actor_id in mind.intending:
        mind.courier.cancel(mind.intending.pop(actor_id)[0])
    for scene in world["conversations"]:
        claim = scene["writing"]
        if claim is None or claim["speaker"] != actor_id or scene["written"] is not None:
            continue
        key = (scene["id"], claim["turn"])
        scene["writing"] = None
        if key in mind.writing:
            mind.courier.cancel(mind.writing.pop(key))
        if key in mind.answering:
            mind.courier.cancel(mind.answering.pop(key)[0])


def say(world: World, mind: MindLoop, command: Mapping[str, Any]) -> None:
    """Type a line to the scene the played guest is in: claim the scene's next slot and have the line read.

    The guests will hear the player's exact words; a model only reads which speech act they perform. A guest's
    line in flight for the slot, or already written but not spoken, is dropped (the guest is asked again after the
    player's line), so the player cuts in.

    Args:
        world: Authoritative world, whose scene gets the player's claim.
        mind: The evening's requests in flight.
        command: `{"type": "say", "text": str, "to": "auto" | "everyone" | <guest id>}`; `to` defaults to auto.

    Raises:
        ValueError: The evening has no player or the guest is on autopilot; the guest is in no scene; the text,
            once trimmed, is empty or longer than `MAX_LINE`; `to` names nobody else in the scene; or a line of
            theirs is already being read or waits to be spoken there. Nothing changes then.
    """
    player = world["player"]
    if player is None or not player["steering"]:
        raise ValueError("say needs a player who holds the wheel")
    actor_id = player["actor_id"]
    scene = conversation_of(world, actor_id)
    if scene is None:
        raise ValueError("say needs the played guest to be in a conversation")
    text, to = command.get("text"), command.get("to", "auto")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_LINE:
        raise ValueError(f"say needs text of 1 to {MAX_LINE} characters, not {text!r}")
    if to not in ("auto", "everyone") and (not isinstance(to, str) or to == actor_id
                                           or to not in scene["participants"]):
        raise ValueError(f"say needs to to be auto, everyone or someone else in the scene, not {to!r}")
    claim = scene["writing"]
    if claim is not None and claim["speaker"] == actor_id:
        raise ValueError("A line of the player's is being read or waits to be spoken: one at a time")
    if claim is not None:
        _drop_claim(mind, scene["id"], claim["turn"])
    scene["written"] = None
    scene["writing"] = {"turn": len(scene["turns"]), "speaker": actor_id, "since": world["time"]}
    mind.read_line(world, scene["id"], text.strip(), to)


def _drop_claim(mind: MindLoop, scene_id: str, turn: int) -> None:
    # The guest's request for this slot, a line or an invitation answer, is cancelled: nothing it answers is wanted.
    key = (scene_id, turn)
    if key in mind.writing:
        mind.courier.cancel(mind.writing.pop(key))
    if key in mind.answering:
        mind.courier.cancel(mind.answering.pop(key)[0])
