"""What a guest is offered about a fight in the room or their own hurts: reactions, and the road to mending."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.body.wounds import hurt
from tavern.social.bystanders import reactions


def is_hurt(observation: Mapping[str, Any]) -> bool:
    """Tell whether the guest is hurt enough that mending is their business.

    Args:
        observation: The guest's observation; an actor with no health counts as whole.

    Returns:
        True when their health is below the line of being hurt (`wounds.HURT`).
    """
    return hurt(observation["actor"])


def room_reactions(observation: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    """List what the guest may do about a fight in sight or someone on the floor.

    Args:
        observation: The guest's observation.

    Returns:
        `(verb, target_id)` pairs from `bystanders.reactions`; nothing for a guest who is hurt (their business is
        to mend) or one on an errand.
    """
    if is_hurt(observation) or observation["actor"]["id"] in observation.get("on_errands", []):
        return []
    return reactions(observation)


def treatments(observation: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    """List what a hurt guest may do to be mended, apart from going home.

    Args:
        observation: The guest's observation, with `people` carrying who is `healer`, `beside` or seated.

    Returns:
        `use_remedy` when they carry one, and `seek_remedy` toward each healer in sight who is awake, not laid out,
        and within reach or seated at a table they could walk to; sorted by ID.
    """
    actor = observation["actor"]
    options: list[tuple[str, str | None]] = [("use_remedy", None)] if actor["inventory"].get("remedy") else []
    healers: Sequence[Mapping[str, Any]] = sorted(
        (person for person in observation.get("people", []) if person.get("healer") and person["id"] != actor["id"]
         and not person.get("asleep") and not person.get("fighting")
         and person.get("condition", "ok") not in ("down", "out")
         and (person.get("beside") or (person.get("seat_id") and person.get("table_id")))), key=lambda item: item["id"])
    return options + [("seek_remedy", person["id"]) for person in healers]
