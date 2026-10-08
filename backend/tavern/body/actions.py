"""Whether a visitor may start or keep doing an action: verb, target, inventory, and partner."""

from collections.abc import Mapping
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.body.dozing import asleep
from tavern.hall.room import find_object
from tavern.hall.staff import on_staff
from tavern.hall.state import find_actor
from tavern.social.giving import gift_error
from tavern.social.invitations import fetch_error
from tavern.social.scenes import conversation_of, pressed, side_by_side, table_of


def stored_action(action: Mapping[str, Any]) -> dict[str, Any]:
    """Pick the fields of an action a visitor keeps and saves while doing it.

    Args:
        action: Action with an ID, a verb, a target ID, and maybe the item it names.

    Returns:
        The ID, verb and target, plus the item only when the action names one, so other actions keep
        their plain shape.
    """
    kept = {key: action.get(key) for key in ("id", "verb", "target_id")}
    return kept if action.get("item") is None else {**kept, "item": action["item"]}


def _target(world: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any] | None:
    return find_object(world["map"], action.get("target_id"))


def action_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    """Tell why a visitor may not start, or carry on with, an action.

    Args:
        world: Current world.
        actor: Visitor doing it.
        action: Action with an ID, a verb, and an optional target ID.

    Returns:
        A human-readable refusal reason, or None when the action is allowed.
    """
    if not isinstance(action.get("id"), str) or not action["id"]:
        return "Action ID must be a nonempty string"
    verb = action.get("verb")
    if not isinstance(verb, str) or verb not in world["rules"]["durations"]:
        return "Unknown action verb"
    activity = ACTIVITIES[verb]
    if activity.staff_only and not on_staff(actor):
        return f"Only staff can {verb.replace('_', ' ')}"
    if activity.seated and not actor.get("seat_id"):
        return "This needs a seat at a table"
    if action.get("item") is not None and not activity.names_item:
        return "This action does not take an item"
    if activity.names_item:
        return _give_error(world, actor, action)
    if activity.opens_errand:
        return _fetch_error(world, actor, action)
    if activity.partner:
        return _talk_error(world, actor, action)
    if activity.near_person:
        return _confront_error(world, actor, action)
    if activity.requires_item and actor["inventory"][activity.requires_item] <= 0:
        return f"No {activity.requires_item} in inventory"
    if activity.target_kinds:
        return _target_error(world, actor, action)
    if action.get("target_id") is not None:
        return "This action does not take a target"
    return None


def _target_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    target = _target(world, action)
    if target is None:
        return "Target no longer exists"
    activity = ACTIVITIES[action["verb"]]
    if target["kind"] not in activity.target_kinds:
        return "Target does not support this action"
    # A place with a line is never refused for being busy: the visitor joins its line instead.
    if target["reserved_by"] not in (None, actor["id"]) and "queue" not in target:
        return "Target is reserved by another visitor"
    if activity.empty_target and target["stock"] <= 0:
        return activity.empty_target
    return None


def _asleep(sleeper: Mapping[str, Any]) -> str:
    return f"{sleeper['name']} is asleep"


def _talk_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    partner = find_actor(world, action.get("target_id"))
    if partner is None or partner["id"] == actor["id"]:
        return "Choose another visitor to talk to"
    if asleep(partner):
        return _asleep(partner)
    if conversation_of(world, actor["id"]) is not None:
        # Someone already talking carries on with their part for as long as their scene lasts.
        current = actor.get("action")
        carrying_on = current is not None and current.get("id") == action["id"]
        return None if carrying_on else "Visitor is already in a conversation"
    scene = conversation_of(world, partner["id"])
    if ACTIVITIES[action["verb"]].joins:
        return _join_error(world, actor, partner, scene)
    if scene is not None:
        return "Visitor is already in a conversation"
    # Someone a need presses on declines, so they can see to it instead of being drawn back in.
    if pressed(world, partner):
        return f"{partner['name']} has something more pressing to see to"
    return None if _close_enough(world, actor, partner) else "Visitors must sit at one table or stand side by side"


def _confront_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    # Within reach is the reach of a chat. Whether the grudge is enough is for the decision to weigh,
    # as with any other verb: the world checks only what is possible.
    victim = find_actor(world, action.get("target_id"))
    if victim is None or victim["id"] == actor["id"]:
        return "Choose another visitor to confront"
    if on_staff(victim):
        return f"{victim['name']} works behind the bar and is not to be fought"
    if asleep(victim):
        return _asleep(victim)
    return None if _close_enough(world, actor, victim) else "Visitors must sit at one table or stand side by side"


def _give_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    receiver = find_actor(world, action.get("target_id"))
    if receiver is None or receiver["id"] == actor["id"]:
        return "Choose another visitor to give to"
    if on_staff(receiver):
        return f"{receiver['name']} works behind the bar and takes no gifts"
    if asleep(receiver):
        return _asleep(receiver)
    if not _close_enough(world, actor, receiver):
        return "Visitors must sit at one table or stand side by side"
    return gift_error(world, actor, receiver, action.get("item"))


def _fetch_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    receiver = find_actor(world, action.get("target_id"))
    if receiver is None or receiver["id"] == actor["id"]:
        return "Choose another visitor to bring a drink to"
    if on_staff(receiver):
        return f"{receiver['name']} works behind the bar and needs no drink brought"
    if asleep(receiver):
        return _asleep(receiver)
    return fetch_error(world, actor, receiver) or (
        None if _close_enough(world, actor, receiver) else "Visitors must sit at one table or stand side by side")


def _join_error(world: Mapping[str, Any], actor: Mapping[str, Any], member: Mapping[str, Any],
                scene: Mapping[str, Any] | None) -> str | None:
    if scene is None:
        return "Visitor is not in a conversation"
    if len(scene["participants"]) >= world["rules"]["conversation"]["max_participants"]:
        return "The conversation is full"
    if scene["table_id"] is not None:
        return None if table_of(world, actor) == scene["table_id"] else "Join a conversation at your own table"
    return None if side_by_side(world, actor, member) else "Stand beside someone in the conversation to join it"


def _close_enough(world: Mapping[str, Any], actor: Mapping[str, Any], partner: Mapping[str, Any]) -> bool:
    table = table_of(world, actor)
    return (table is not None and table == table_of(world, partner)) or side_by_side(world, actor, partner)
