"""Speech acts in a conversation scene and their outcomes: relief, shared places, or a quarrel."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from random import Random
from types import MappingProxyType
from typing import Any

from tavern.memory import grieve, record_event
from tavern.scenes import Conversation, end_conversation, leave_conversation

# An act's effect receives the world, the scene, the speaker, and whom they addressed (None for everyone).
ActEffect = Callable[[dict[str, Any], Conversation, dict[str, Any], dict[str, Any] | None], None]


@dataclass(frozen=True)
class Act:
    """What a speech act does once spoken, and what it means to whoever writes the lines.

    Attributes:
        effect: Consequence in the world, or None for an act that changes nothing.
        meaning: When a speaker uses it and what follows, for a turn writer.
    """

    effect: ActEffect | None
    meaning: str


def _members(world: Mapping[str, Any], scene: Conversation) -> list[dict[str, Any]]:
    return [item for item in world["actors"] if item["id"] in scene["participants"]]


def _relieve(world: dict[str, Any], scene: Conversation, speaker: dict[str, Any],
             addressee: dict[str, Any] | None) -> None:
    # A friendly exchange eases everyone's wish for company, not only the speaker's.
    for member in _members(world, scene):
        member["needs"]["social"] = max(0.0, member["needs"]["social"] - world["rules"]["conversation"]["relief"])


def _tell_places(world: dict[str, Any], scene: Conversation, speaker: dict[str, Any],
                 addressee: dict[str, Any] | None) -> None:
    for listener in _members(world, scene):
        if listener["id"] != speaker["id"]:
            _share_places(speaker, listener)
    _relieve(world, scene, speaker, addressee)


def _complain(world: dict[str, Any], scene: Conversation, speaker: dict[str, Any],
              addressee: dict[str, Any] | None) -> None:
    # A grumble to everyone is taken up by the next in the circle.
    others = [item for item in _members(world, scene) if item["id"] != speaker["id"]]
    partner = addressee if addressee in others else others[0]
    if _quarrels(world, speaker, partner):
        _quarrel(world, speaker, partner, scene["topic"])
        end_conversation(world, scene, pleasant=False)


def _say_goodbye(world: dict[str, Any], scene: Conversation, speaker: dict[str, Any],
                 addressee: dict[str, Any] | None) -> None:
    leave_conversation(world, speaker)


ACTS: Mapping[str, Act] = MappingProxyType({
    "greet": Act(None, "open the conversation, or welcome someone who joined it"),
    "small_talk": Act(_relieve, "pass the time pleasantly; it eases everyone's wish for company"),
    "share_place": Act(_tell_places, "tell the others where the tap, the WC or the darts are; they learn "
                                     "every such place the speaker knows, and it eases the wish for company"),
    "joke": Act(_relieve, "make the others laugh; it eases everyone's wish for company"),
    "complain": Act(_complain, "grumble about something; after a few beers an impatient pair may quarrel, "
                               "which ends the conversation and leaves both aggrieved"),
    "leave_conversation": Act(_say_goodbye, "say goodbye and leave; the others carry on while two remain"),
})


def _quarrels(world: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    # Ale loosens tongues: a sober pair never quarrels, a tipsy impatient pair often does.
    rules = world["rules"]
    tipsy = max(0, left["visit"]["beers"] + right["visit"]["beers"] - 1)
    temper = 2 - left["traits"].get("patience", 0.5) - right["traits"].get("patience", 0.5)
    chance = min(rules["quarrel_max"], rules["quarrel_per_beer"] * tipsy * temper)
    # Seeded by the evening and tick, so a replay or a reloaded save rolls the same dice.
    return Random(f"{world['seed']}:{world['tick']}:{left['id']}:{right['id']}").random() < chance


def _quarrel(world: Mapping[str, Any], actor: dict[str, Any], partner: dict[str, Any], topic: str) -> None:
    for visitor, other in ((actor, partner), (partner, actor)):
        grieve(visitor, f"Quarreled with {other['name']} about {topic}")
        record_event(world, visitor, "quarrel", f"{actor['name']} and {partner['name']} quarreled about {topic}")


def _share_places(speaker: Mapping[str, Any], listener: dict[str, Any]) -> None:
    for identifier, known in speaker["knowledge"]["objects"].items():
        if known["kind"] not in ("tap", "toilet", "darts") or identifier in listener["knowledge"]["objects"]:
            continue
        listener["knowledge"]["objects"][identifier] = {**deepcopy(known), "heard_from": speaker["id"]}
