"""Whether a visitor may start or keep doing an action: verb, target, inventory, and partner."""

from collections.abc import Mapping
from typing import Any

from tavern.activities import ACTIVITIES
from tavern.conversation import conversation_of
from tavern.room import find_object


def _actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any] | None:
    return next((item for item in world["actors"] if item["id"] == actor_id), None)


def _target(world: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any] | None:
    return find_object(world["map"], action.get("target_id"))


def _seat(world: Mapping[str, Any], actor: Mapping[str, Any]) -> dict[str, Any] | None:
    return _target(world, {"target_id": actor.get("seat_id")})


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
    if activity.partner:
        return _talk_error(world, actor, action)
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
    if target["reserved_by"] not in (None, actor["id"]):
        return "Target is reserved by another visitor"
    if activity.empty_target and target["stock"] <= 0:
        return activity.empty_target
    return None


def _talk_error(world: Mapping[str, Any], actor: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    partner = _actor(world, action.get("target_id"))
    if partner is None or partner["id"] == actor["id"]:
        return "Choose another seated visitor to talk to"
    left, right = _seat(world, actor), _seat(world, partner)
    if not left or not right or not left.get("table_id") or left.get("table_id") != right.get("table_id"):
        return "Visitors must be seated at the same table"
    if abs(actor["x"] - partner["x"]) + abs(actor["y"] - partner["y"]) > 4:
        return "Conversation partner is too far away"
    conversation = conversation_of(world, partner["id"])
    if conversation and conversation["id"] != actor["id"]:
        return "Visitor is already in a conversation"
    return None
