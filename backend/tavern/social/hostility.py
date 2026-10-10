"""Who a guest might shove or fight: the gate of hostile options, read from their own observation."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tavern.body.drunkenness import inhibition_modifier
from tavern.social.thoughts import THOUGHTS, active_thoughts, opinion_of


@dataclass(frozen=True)
class Hostility:
    """When a guest may turn on someone.

    Attributes:
        opinion: Opinion of the target at or below which they may be turned on.
        recent: Seconds a cause stays fresh, counted from when its thought formed.
        urge: Urge (temper times the loosening of drink) a guest needs for each hostile verb.
        drunk: Drunkenness (0-1) from which drink alone brings a guest to a fight: really drunk, not merely tipsy.
        hatred: Opinion of the target at or below which a guest may fight sober, with `hatred_urge` of urge.
        hatred_urge: Urge a guest who hates the target needs to fight: a hot head is enough, drunk or not.
    """

    opinion: float
    recent: float
    urge: Mapping[str, float]
    drunk: float
    hatred: float
    hatred_urge: float


# A fight takes a hotter head than a shove: a sober hothead shoves, only drink or fury fights.
# A fight comes by two roads: strong drink (the `drunk` stage) in a hot head, or real hatred in a hot enough one.
HOSTILITY = Hostility(opinion=-30.0, recent=120.0, urge=MappingProxyType({"shove": 0.45, "start_fight": 0.85}),
                      drunk=0.45, hatred=-70.0, hatred_urge=0.5)

# The thoughts that give a grudge a reason to be acted on.
HOSTILE_CAUSES = ("insulted", "quarrel", "seat_taken", "friend_insulted", "line_cut")


def urge(observation: Mapping[str, Any]) -> float:
    """Tell how hard a guest's temper pushes them to lash out, loosened by drink.

    Args:
        observation: The guest's observation, with their `traits` and `drunkenness`.

    Returns:
        Their `temper` trait times `drunkenness.inhibition_modifier`; 0 for a guest with no temper
        trait, since hostility is opt-in (a Stage 0 visitor or a hand-made observation is peaceful).

    Raises:
        ValueError: Drunkenness is not a number from 0 to 1.
    """
    actor = observation["actor"]
    return actor.get("traits", {}).get("temper", 0.0) * inhibition_modifier(actor.get("drunkenness", 0.0))


def hostile_targets(observation: Mapping[str, Any], verb: str) -> list[str]:
    """List the people a guest could turn on with a hostile verb.

    Args:
        observation: The guest's observation, with `people` in sight and `time`. Without a clock
            no cause can be called recent, so nobody is a target.
        verb: `shove` or `start_fight`.

    Returns:
        IDs of those who sit at the guest's table or stand beside them, are not staff, are awake, are thought
        ill of (see `HOSTILITY.opinion`), gave a recent cause (`HOSTILE_CAUSES`), and the guest's
        urge reaches the verb's threshold; sorted.

    Raises:
        ValueError: The verb is not a hostile verb, or drunkenness is malformed.
    """
    if verb not in HOSTILITY.urge:
        raise ValueError(f"{verb!r} is not a hostile verb")
    now, actor = observation.get("time"), observation["actor"]
    if now is None or urge(observation) < min(HOSTILITY.urge[verb], HOSTILITY.hatred_urge if verb == "start_fight"
                                              else HOSTILITY.urge[verb]):
        return []
    return sorted({person["id"] for person in observation.get("people", [])
                   if person["id"] != actor["id"] and not person.get("post") and not person.get("asleep")
                   and not person.get("fighting") and person.get("condition", "ok") not in ("down", "out")
                   and _near(observation, person) and _willing(observation, person["id"], verb, now)
                   and _caused(actor, person["id"], now)})


def _willing(observation: Mapping[str, Any], other_id: str, verb: str, now: float) -> bool:
    # A shove needs a grudge and a temper. A fight comes by drink (a hot head, really drunk, who thinks ill of them) or
    # by hatred (a head hot enough, drunk or sober).
    actor, opinion, hot = observation["actor"], opinion_of(observation["actor"], other_id, now), urge(observation)
    if verb == "shove":
        return opinion <= HOSTILITY.opinion
    drunk = actor.get("drunkenness", 0.0) >= HOSTILITY.drunk and hot >= HOSTILITY.urge["start_fight"]
    return (opinion <= HOSTILITY.opinion and drunk) or (opinion <= HOSTILITY.hatred and hot >= HOSTILITY.hatred_urge)


def _near(observation: Mapping[str, Any], person: Mapping[str, Any]) -> bool:
    # The reach of a chat: the same table, or standing side by side (see `scenes.side_by_side`).
    seat = next((item for item in observation["objects"] if item["id"] == observation["actor"].get("seat_id")), None)
    table = seat.get("table_id") if seat else None
    return bool(person.get("beside")) or bool(table and person.get("seat_id") and person.get("table_id") == table)


def _caused(actor: Mapping[str, Any], other_id: str, now: float) -> bool:
    # A thought lasts its kind's seconds from forming, so `expires_at` gives back when it formed.
    return any(item["about"] == other_id and item["kind"] in HOSTILE_CAUSES
               and now - (item["expires_at"] - THOUGHTS[item["kind"]].seconds) <= HOSTILITY.recent
               for item in active_thoughts(actor.get("thoughts", []), now))
