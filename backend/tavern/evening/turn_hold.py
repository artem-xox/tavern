"""The line a person owes the hall: which due line of the played guest's a live clock may hold still for."""

from collections.abc import Mapping
from typing import Any

from tavern.social.player_lines import player_turn
from tavern.social.stage_lines import comeback_owed_to


def owed_line(world: Mapping[str, Any]) -> str | None:
    """Name the line the played guest owes now, so a live clock holds still for each one once.

    Args:
        world: Current world.

    Returns:
        `scene:<scene id>:<turn index>` when their scene's next line is theirs (`player_turn` `your_turn`),
        `comeback:<heckler id>:<heckle time>` when a heckle is owed an answer, and None otherwise (no player,
        autopilot, someone else's turn, a line being read, or the stage, whose number has a wait of its own).
    """
    turn = player_turn(world)  # type: ignore[arg-type]  # read-only: player_turn never writes the world
    if turn is None:
        return None
    if turn["state"] == "your_turn":
        scene = next(item for item in world["conversations"] if item["id"] == turn["scene_id"])
        return f"scene:{scene['id']}:{len(scene['turns'])}"
    if turn["state"] == "comeback":
        performer = world["player"]["actor_id"]
        heckler = comeback_owed_to(world, performer)
        assert heckler is not None  # the comeback state means one is owed
        heckled = max(event["time"] for event in world["events"] if event["type"] == "heckled"
                      and event["actor_id"] == heckler["id"] and event.get("performer_id") == performer)
        return f"comeback:{heckler['id']}:{heckled}"
    return None
