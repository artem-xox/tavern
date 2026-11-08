"""The player's commands: check one and apply it to the world and the mind loop."""

from collections.abc import Mapping
from typing import Any

from tavern.evening.mind_loop import MindLoop
from tavern.hall.memory import log_event
from tavern.hall.state import World


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
