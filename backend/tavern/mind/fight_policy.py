"""What a guest would score each reaction to a fight or a hurt without a model, from their traits and drink."""

from collections.abc import Mapping
from typing import Any

from tavern.body.wounds import health_of
from tavern.social.bystanders import friends_of_fighters
from tavern.social.hostility import urge


def utilities(observation: Mapping[str, Any]) -> dict[str, float]:
    """Score the verbs a fight or a hurt brings, 0-1.

    Args:
        observation: The guest's observation.

    Returns:
        A score per verb, a starting point to be tuned on offline evenings. Watching draws the curious and a little the
        timid; cheering the sociable, the rowdy and the drunk; stepping between needs courage and strength, and a friend
        among the fighters, and drink spoils it; waiting a turn needs the urge to lash out and the nerve; helping
        someone up the sociable and a healer; and mending comes before nearly everything for the hurt.
    """
    actor = observation["actor"]
    traits, drunk = actor.get("traits", {}), actor.get("drunkenness", 0.0)
    courage, strength, sociability, curiosity, temper = (traits.get(name, 0.5) for name in (
        "courage", "strength", "sociability", "curiosity", "temper"))
    fighters = [person["id"] for person in observation.get("people", []) if person.get("fighting")]
    friend = friends_of_fighters(actor, fighters, observation.get("time", float("-inf")))
    healer = bool(actor.get("inventory", {}).get("remedy"))
    lost = 1 - health_of(actor) / 100
    return {"watch_fight": min(1.0, 0.3 + 0.35 * curiosity + 0.15 * (1 - courage)),
            "cheer": min(1.0, 0.05 + 0.3 * sociability + 0.35 * drunk + 0.1 * temper),
            "intervene": min(1.0, max(0.0, 0.05 + 0.55 * courage * (0.5 + 0.5 * strength) + 0.2 * friend - 0.25 * drunk)),
            "join_fight": min(1.0, 0.05 + 0.6 * min(1.0, urge(observation)) * courage),
            "help_up": min(1.0, 0.3 + 0.4 * sociability + 0.3 * healer),
            "seek_remedy": min(1.0, 0.7 + 0.25 * lost),
            "use_remedy": 0.95}
