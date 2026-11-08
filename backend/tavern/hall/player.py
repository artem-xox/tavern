"""The player: which guest they play, and whether they hold the wheel."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.staff import on_staff


def steered(world: Mapping[str, Any], actor_id: str) -> bool:
    """Tell whether the player holds the wheel of a body right now.

    `on_staff` says what a body may do; this says who decides for it.

    Args:
        world: Current world.
        actor_id: Visitor to ask about.

    Returns:
        True when the world has a player who plays this visitor and has not given the wheel back
        to the guest's own mind (autopilot).
    """
    player = world.get("player")
    return player is not None and player["steering"] and player["actor_id"] == actor_id


def check_player(world: Mapping[str, Any]) -> None:
    """Check the player record saved with a world.

    Args:
        world: Decoded save whose `player` is None or `{actor_id, steering}`.

    Raises:
        ValueError: The record is malformed, or its actor is not a guest of this evening (present,
            expected or departed), or is on staff.
    """
    player = world["player"]
    if player is None:
        return
    if not isinstance(player, dict) or set(player) != {"actor_id", "steering"}:
        raise ValueError(f"Invalid saved player record {player!r}")
    if type(player["steering"]) is not bool:
        raise ValueError(f"Invalid saved player: steering must be true or false, not {player['steering']!r}")
    everyone = [*world["actors"], *world["departed"], *world["expected"]]
    played = next((item for item in everyone if item["id"] == player["actor_id"]), None)
    if played is None:
        raise ValueError(f"Invalid saved player: {player['actor_id']!r} is not a guest of this evening")
    if on_staff(played):
        raise ValueError(f"Invalid saved player: {player['actor_id']!r} is staff")
