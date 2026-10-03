"""Outcomes of a chat between tablemates: shared places, relief, or a quarrel."""

from collections.abc import Mapping
from copy import deepcopy
from random import Random
from typing import Any

from tavern.memory import record_event
from tavern.thoughts import think


def conversation_of(world: Mapping[str, Any], actor_id: str) -> dict[str, Any] | None:
    """Find the visitor talking to, or being talked to by, someone.

    Args:
        world: Current world.
        actor_id: Visitor whose chat is looked up.

    Returns:
        The visitor whose `talk` action includes them, or None when they are not chatting.
    """
    return next((item for item in world["actors"] if item.get("action")
                 and item["action"]["verb"] == "talk"
                 and actor_id in (item["id"], item["action"]["target_id"])), None)


def complete_conversation(world: Mapping[str, Any], actor: dict[str, Any], partner: dict[str, Any]) -> None:
    """Settle a finished chat: both share places and feel less lonely, or they quarrel.

    Args:
        world: World whose event log, seed, and tick are used.
        actor: Visitor who started the chat.
        partner: Visitor they talked to.
    """
    topics = ("stories from the road", "the inn's beer", "their next journey", "a game of darts")
    count = sum(item["type"] == "conversation" for item in actor["memory"])
    topic = topics[count % len(topics)]
    if _quarrels(world, actor, partner):
        _quarrel(world, actor, partner, topic)
        return
    _share_places(actor, partner)
    _share_places(partner, actor)
    message = f"{actor['name']} and {partner['name']} chatted about {topic}"
    for visitor, other in ((actor, partner), (partner, actor)):
        visitor["needs"]["social"] = max(0, visitor["needs"]["social"] - 60)
        record_event(world, visitor, "conversation", message)
        think(visitor, "chat", world["time"], f"Chatted with {other['name']} about {topic}", message, about=other)


def _quarrels(world: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    # Ale loosens tongues: a sober pair never quarrels, a tipsy impatient pair often does.
    rules = world["rules"]
    tipsy = max(0, left["visit"]["beers"] + right["visit"]["beers"] - 1)
    temper = 2 - left["traits"].get("patience", 0.5) - right["traits"].get("patience", 0.5)
    chance = min(rules["quarrel_max"], rules["quarrel_per_beer"] * tipsy * temper)
    # Seeded by the evening and tick, so a replay or a reloaded save rolls the same dice.
    return Random(f"{world['seed']}:{world['tick']}:{left['id']}:{right['id']}").random() < chance


def _quarrel(world: Mapping[str, Any], actor: dict[str, Any], partner: dict[str, Any], topic: str) -> None:
    message = f"{actor['name']} and {partner['name']} quarreled about {topic}"
    for visitor, other in ((actor, partner), (partner, actor)):
        record_event(world, visitor, "quarrel", message)
        think(visitor, "quarrel", world["time"], f"Quarreled with {other['name']} about {topic}", message, about=other)


def _share_places(speaker: Mapping[str, Any], listener: dict[str, Any]) -> None:
    for identifier, known in speaker["knowledge"]["objects"].items():
        if known["kind"] not in ("tap", "toilet", "darts") or identifier in listener["knowledge"]["objects"]:
            continue
        listener["knowledge"]["objects"][identifier] = {**deepcopy(known), "heard_from": speaker["id"]}
