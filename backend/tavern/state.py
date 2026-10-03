"""Looking things up in the world: the one place that finds a visitor by ID."""

from collections.abc import Mapping
from typing import Any


def find_actor(world: Mapping[str, Any], actor_id: Any) -> dict[str, Any] | None:
    """Find a visitor in the hall.

    Args:
        world: World whose `actors` are searched; visitors who left are not.
        actor_id: ID to look for; anything that matches no visitor finds none.

    Returns:
        The visitor's record, or None.
    """
    return next((item for item in world["actors"] if item["id"] == actor_id), None)
