"""The player in an evening: lines by act, misreadings, silences, ignorings, actions and refused script steps."""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.evening.player_script import REFUSAL_PREFIX



class PlayerCounts(TypedDict):
    """What the player did: `lines` by speech act (silences apart), `actions` by verb."""

    actor: str
    lines: dict[str, int]
    misread: int
    silences: int
    ignored: int
    actions: dict[str, int]
    refused: int


def player_counts(events: Sequence[Mapping[str, Any]], actor_id: str | None) -> PlayerCounts | None:
    """Count the player's lines, actions and troubles.

    Args:
        events: The complete event log: `turn` events with `player` true, `misread`, `ignored` (S3-05; none before
            it), `player_act` with a `verb`, and the lockstep's `control` events for refused script steps.
        actor_id: The guest the player plays, or None for an evening with no player.

    Returns:
        The counts, or None where nobody plays. `ignored` is how many guests the player's silence left unanswered.
    """
    if actor_id is None:
        return None
    turns = [item for item in events if item["type"] == "turn" and item.get("player")]
    return {"actor": actor_id,
            "lines": dict(Counter(item["act"] for item in turns if item["act"] != "silence")),
            "misread": sum(item["type"] == "misread" for item in events),
            "silences": sum(item["act"] == "silence" for item in turns),
            "ignored": sum(item["type"] == "ignored" for item in events),
            "actions": dict(Counter(item["verb"] for item in events if item["type"] == "player_act")),
            "refused": sum(item["type"] == "control" and item["message"].startswith(REFUSAL_PREFIX)
                           for item in events)}
