"""The player's commands: check one and apply it to the world and the mind loop."""

from collections.abc import Mapping
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.evening.mind_loop import MindLoop
from tavern.hall.memory import log_event
from tavern.hall.player import steered
from tavern.hall.state import Actor, World, find_actor
from tavern.hall.world import observe_actor, start_action
from tavern.mind.candidates import open_actions


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


def _played_guest(world: World, command: str) -> Actor:
    # The body the player holds the wheel of, or the reason they cannot use their hands now.
    player = world["player"]
    if player is None:
        raise ValueError(f"{command} needs a player, and this evening has none")
    if not steered(world, player["actor_id"]):
        raise ValueError(f"{command} needs the wheel, and the guest is on autopilot")
    guest = find_actor(world, player["actor_id"])
    if guest is None:
        raise ValueError(f"{command}: the played guest is not in the hall")
    return guest


def act(world: World, command: Mapping[str, Any]) -> None:
    """Start an action for the played guest, as a decision of their own would.

    The world checks it like any guest's (`start_action`), and the guest's `decision` says the player chose it.
    Leaving a scene for another action ends the guest's part in it by the scene's own rule.

    Args:
        world: Authoritative world, whose played guest and event log are updated in place.
        command: `{"type": "act", "action": {"id", "verb", "target_id"?, "item"?, "cell"?}}`.

    Raises:
        ValueError: The evening has no player, the guest is on autopilot or not in the hall, the command names no
            action, or the world refuses it (the world's reason). Nothing starts then.
    """
    guest = _played_guest(world, "act")
    action = command.get("action")
    if not isinstance(action, Mapping):
        raise ValueError(f"act needs an action, not {action!r}")
    result = start_action(world, guest["id"], action)
    if not result["accepted"]:
        raise ValueError(result["reason"])
    guest["decision"] = {"source": "player", "scores": {}, "error": None}
    log_event(world, guest["id"], "player_act", f"{guest['name']} chose {action['verb']}")["verb"] = action["verb"]


def options(world: World, command: Mapping[str, Any]) -> dict[str, Any]:
    """List the actions open to the played guest now, as their own mind would be offered them.

    The world stays as it is, apart from the knowledge refresh `observe_actor` does for every decision.

    Args:
        world: Current world.
        command: `{"type": "options", "target_id"?: str}`; with a target, only the actions aimed at it.

    Returns:
        `{"type": "options", "target_id": str | None, "options": [{"action": Action, "label": str}]}`, the label
        being the verb's own (`Activity.label`).

    Raises:
        ValueError: The evening has no player, the guest is on autopilot or not in the hall, or `target_id` is
            not a nonempty string.
    """
    guest = _played_guest(world, "options")
    target = command.get("target_id")
    if target is not None and (not isinstance(target, str) or not target):
        raise ValueError(f"options needs target_id to be a nonempty string, not {target!r}")
    listed = [item for item in open_actions(observe_actor(world, guest["id"]))
              if target is None or item["target_id"] == target]
    return {"type": "options", "target_id": target,
            "options": [{"action": item, "label": ACTIVITIES[item["verb"]].label or item["verb"].replace("_", " ")}
                        for item in listed]}
