"""Fights in the world: who fights whom, each exchange of blows as it falls due, and how a fight ends."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import math
from typing import Any, TypedDict

from tavern.body.blows import (ENDINGS, EXCHANGE_SECONDS, WEAPONS, Ending, Fighter, ending, swing)
from tavern.body.wounds import laid_out, lay_low
from tavern.hall.chance import roll
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.social.aftermath import bout_ended
from tavern.social.names import called
from tavern.social.scenes import within_reach
from tavern.social.thoughts import think

# The verb both fighters carry for as long as the fight lasts: the world, not a timer, ends it.
FIGHT = "start_fight"
# What a fight may end in: the formula's endings, or a bystander pulling the two apart.
OUTCOMES = (*ENDINGS, "separated")
# A knocked-out guest lies this long (a roll between them): enough to be helped up, or left lying.
LIES = (20.0, 40.0)

# Starts an action the way `activate` does, for fighters brought into a fight: world, visitor, action, plan.
Activate = Callable[[World, Actor, dict[str, Any], tuple[list[int] | None, list[list[int]]]], None]


class Exchange(TypedDict):
    """One swing: when, who swung, whether it landed and how much health it took."""

    time: float
    attacker: str
    hit: bool
    damage: float


class Waiting(TypedDict):
    """A bystander waiting their turn to fight one of the two, a duel at a time."""

    id: str
    against: str


class Fight(TypedDict):
    """A fight between two. `a` started it; `weapons` is what each holds by ID. `outcome` is one of `ENDINGS` once it
    is over (with the `loser`, where there is one, and when it `ended_at`) and None while it runs. `witnessed` is
    whether the room has taken note of how it began (`tavern.social.bystanders`)."""

    id: str
    a: str
    b: str
    weapons: dict[str, str]
    started_at: float
    next_exchange_at: float
    exchanges: list[Exchange]
    waiting: list[Waiting]
    witnessed: bool
    outcome: str | None
    loser: str | None
    ended_at: float | None


@dataclass
class Bouts:
    """What a tick of fights asks of the world: who is let go of the fight, which fights ended this tick (any of them
    may have bystanders waiting a turn), and which of those ended in shouting."""

    released: list[Actor] = field(default_factory=list)
    ended: list[Fight] = field(default_factory=list)
    shouting: list[Fight] = field(default_factory=list)


def weapon_of(actor: Mapping[str, Any]) -> str:
    """Tell what a visitor fights with: a cudgel in their hands, else their fists.

    Args:
        actor: Visitor.

    Returns:
        A key of `WEAPONS`.
    """
    return "cudgel" if actor["inventory"].get("cudgel") else "fists"


def sex_of(actor: Mapping[str, Any]) -> str | None:
    """Tell a visitor's sex as their card says it.

    Args:
        actor: Visitor.

    Returns:
        `female` or `male`, or None for a visitor with no card or none on it.
    """
    card = actor.get("card")
    return card.get("sex") if card else None


def fighter_of(actor: Mapping[str, Any], weapon: str) -> Fighter:
    """Read a visitor as a fighter, as they are right now.

    Args:
        actor: Visitor; a trait the card does not give counts as an ordinary 0.5.
        weapon: A key of `WEAPONS`.

    Returns:
        The inputs of the formula (`tavern.body.blows`).
    """
    traits = actor["traits"]
    return Fighter(strength=traits.get("strength", 0.5), sex=sex_of(actor), brawling=traits.get("brawling", 0.5),
                   courage=traits.get("courage", 0.5), temper=traits.get("temper", 0.5),
                   drunkenness=actor["drunkenness"], health=actor["health"], fatigue=actor["needs"]["fatigue"],
                   weapon=weapon)


def running(world: Mapping[str, Any]) -> list[Fight]:
    """List the fights under way.

    Args:
        world: Current world.

    Returns:
        The fights with no outcome yet, oldest first.
    """
    return [fight for fight in world["fights"] if fight["outcome"] is None]


def fight_of(world: Mapping[str, Any], actor_id: Any) -> Fight | None:
    """Find the fight a visitor is in.

    Args:
        world: Current world.
        actor_id: Visitor looked for.

    Returns:
        The running fight they are one of the two in, or None.
    """
    return next((fight for fight in running(world) if actor_id in (fight["a"], fight["b"])), None)


def opponent_of(fight: Fight, actor_id: str) -> str:
    """Name the other fighter.

    Args:
        fight: A fight.
        actor_id: One of its two.

    Returns:
        The other one's ID.

    Raises:
        ValueError: The visitor is in neither.
    """
    if actor_id not in (fight["a"], fight["b"]):
        raise ValueError(f"{actor_id} is not in fight {fight['id']}")
    return fight["b"] if actor_id == fight["a"] else fight["a"]


def open_fight(world: World, attacker: Actor, victim: Actor) -> Fight:
    """Start a fight: it is recorded, both mugs are lost, the room hears it and the witnesses take note.

    Args:
        world: World whose `fights` receive it and whose events are logged.
        attacker: Visitor who starts it.
        victim: The one they turn on.

    Returns:
        The new fight; its first exchange falls due `EXCHANGE_SECONDS` from now.
    """
    now = world["time"]
    fight = Fight(id=f"fight-{len(world['fights']) + 1}", a=attacker["id"], b=victim["id"],
                  weapons={member["id"]: weapon_of(member) for member in (attacker, victim)},
                  started_at=now, next_exchange_at=now + EXCHANGE_SECONDS, exchanges=[], waiting=[], witnessed=False, outcome=None,
                  loser=None, ended_at=None)
    world["fights"].append(fight)
    message = f"{attacker['name']} attacked {victim['name']}"
    for member in (attacker, victim):
        record_event(world, member, "fight_started", message)
    think(victim, "attacked", now, f"{called(victim, attacker)} attacked me", message, about=attacker)
    for member in (attacker, victim):
        if member["inventory"].get("beer"):
            member["inventory"]["beer"] = 0
            record_event(world, member, "spilled", f"{member['name']}'s mug went flying")
    return fight


def engage_defenders(world: World, activate: Activate) -> None:
    """Pull every fight's second fighter into it: they carry the fight verb at the one who struck them.

    Args:
        world: World whose visitors are updated in place.
        activate: How the world starts an action for a visitor (`lifecycle.activate`), which takes them out of
            whatever they were doing, a conversation included.
    """
    for fight in running(world):
        defender, attacker = find_actor(world, fight["b"]), find_actor(world, fight["a"])
        if defender is None or attacker is None:
            continue
        held = defender["action"]
        if held is None or held["verb"] != FIGHT or held["target_id"] != attacker["id"]:
            activate(world, defender, {"id": f"{FIGHT}:{attacker['id']}", "verb": FIGHT, "target_id": attacker["id"]},
                     (None, []))


def run_fights(world: World) -> Bouts:
    """Play the exchanges that have fallen due, end the fights that are over, and let their fighters go.

    Args:
        world: World whose fighters' health, conditions and thoughts are updated in place.

    Returns:
        The fighters of the fights that ended this tick (or that no longer run, though they hold the fight verb), to
        be released, those fights, and the ones that ended with the two still cursing each other.
    """
    bouts = Bouts()
    for fight in running(world):
        first, second = find_actor(world, fight["a"]), find_actor(world, fight["b"])
        if first is None or second is None:
            # One of them is gone (they cannot have walked out mid-fight; a rule of the world must have removed them).
            _finish(world, fight, Ending("parted", None), [item for item in (first, second) if item], bouts)
            continue
        while fight["outcome"] is None and fight["next_exchange_at"] <= world["time"]:
            finished = _exchange(world, fight, first, second)
            if finished is not None:
                _finish(world, fight, finished, [first, second], bouts)
    bouts.ended = [fight for fight in world["fights"] if fight["ended_at"] == world["time"]]
    for actor in world["actors"]:
        held = actor["action"]
        if held and held["verb"] == FIGHT and fight_of(world, actor["id"]) is None and actor not in bouts.released:
            bouts.released.append(actor)
    return bouts


def try_separating(world: World, fight: Fight, by: Actor, fighters: tuple[Actor, Actor]) -> bool:
    """Let a bystander try to pull two fighters apart: the brave and the strong succeed, against strong fighters less.

    Args:
        world: World whose fight and thoughts are updated in place when it works.
        fight: The running fight.
        by: The visitor who steps between.
        fighters: Its two fighters.

    Returns:
        Whether the fight is over: it then ended `separated`, and both hold the helper's effort in mind.
    """
    traits = by["traits"]
    strongest = max(item["traits"].get("strength", 0.5) for item in fighters)
    chance = 0.25 + 0.4 * traits.get("strength", 0.5) + 0.3 * traits.get("courage", 0.5) - 0.3 * strongest
    if roll(world, "separate", by["id"], fight["id"]) >= min(0.9, max(0.05, chance)):
        return False
    fight["outcome"], fight["loser"], fight["ended_at"] = "separated", None, world["time"]
    bout_ended(world, fight, Ending("separated", None))
    for member in fighters:
        think(member, "separated_us", world["time"], f"{called(member, by)} pulled us apart",
              f"{by['name']} pulled {fighters[0]['name']} and {fighters[1]['name']} apart", about=by)
    return True


def begin_waiting(world: World, activate: Activate, ended: list[Fight]) -> None:
    """Start the next duel of a fight that just ended: the first bystander waiting a turn takes on who is left standing.

    Args:
        world: World whose visitors are updated in place.
        activate: How the world starts an action for a visitor (`lifecycle.activate`).
        ended: The fights that ended this tick.
    """
    for fight in ended:
        for entry in fight["waiting"]:
            waiter, target = find_actor(world, entry["id"]), find_actor(world, entry["against"])
            if (waiter is None or target is None or fight_of(world, waiter["id"]) or fight_of(world, target["id"])
                    or laid_out(target) or target["condition"] == "staggered" or not within_reach(world, waiter, target)):
                continue
            activate(world, waiter, {"id": f"{FIGHT}:{target['id']}", "verb": FIGHT, "target_id": target["id"]},
                     (None, []))
            break


def _exchange(world: World, fight: Fight, first: Actor, second: Actor) -> Ending | None:
    # Both swing at once, from where they stand: each swing reads the other as they were before this exchange.
    number = len(fight["exchanges"]) // 2 + 1
    elapsed, when = number * EXCHANGE_SECONDS, fight["next_exchange_at"]
    before = {first["id"]: fighter_of(first, fight["weapons"][first["id"]]),
              second["id"]: fighter_of(second, fight["weapons"][second["id"]])}
    after = {}
    for attacker, defender in ((first, second), (second, first)):
        health = swing(before[attacker["id"]], before[defender["id"]], roll(world, fight["id"], attacker["id"], "hit", str(number)),
                       roll(world, fight["id"], attacker["id"], "damage", str(number)), elapsed)
        after[defender["id"]] = health
        taken = before[defender["id"]].health - health
        fight["exchanges"].append(Exchange(time=when, attacker=attacker["id"], hit=taken > 0, damage=taken))
        if taken > 0:
            record_event(world, defender, "blow", f"{attacker['name']} hit {defender['name']}")
    for member in (first, second):
        member["health"] = after[member["id"]]
    fight["next_exchange_at"] = when + EXCHANGE_SECONDS
    return ending(fighter_of(first, fight["weapons"][first["id"]]), fighter_of(second, fight["weapons"][second["id"]]),
                  elapsed)


def _finish(world: World, fight: Fight, result: Ending, members: list[Actor], bouts: Bouts) -> None:
    now = world["time"]
    by_key = {"a": fight["a"], "b": fight["b"]}
    fight["outcome"], fight["loser"], fight["ended_at"] = result.kind, by_key.get(result.loser or ""), now
    downed = [fight["a"], fight["b"]] if result.kind == "double_knockout" else [fight["loser"]] if result.kind == "knockout" else []
    for member in members:
        if member["id"] in downed:
            lay_low(member, "out", now + LIES[0] + (LIES[1] - LIES[0]) * roll(world, fight["id"], member["id"], "lies"))
    bout_ended(world, fight, result)
    bouts.released.extend(members)
    if result.kind == "shouting":
        bouts.shouting.append(fight)


def check_saved_fights(world: Mapping[str, Any]) -> None:
    """Check the fights in a saved world.

    Args:
        world: Decoded save with `fights`, `actors` and `departed`.

    Raises:
        ValueError: A fight is malformed, names an unknown visitor or a weapon the game lacks, has an outcome that is
            not one of `ENDINGS`, runs while its fighters are not both holding the fight verb, or one visitor is in
            two running fights.
    """
    fights = world.get("fights")
    if not isinstance(fights, list):
        raise ValueError("Invalid saved fights")
    known = {item["id"] for item in [*world["actors"], *world["departed"]]}
    ids: set[str] = set()
    busy: set[str] = set()
    for fight in fights:
        if not isinstance(fight, dict) or set(fight) != set(Fight.__annotations__):
            raise ValueError("Invalid saved fight")
        if not isinstance(fight["id"], str) or fight["id"] in ids:
            raise ValueError("Saved fights need unique IDs")
        ids.add(fight["id"])
        if fight["a"] == fight["b"] or not {fight["a"], fight["b"]} <= known:
            raise ValueError("A saved fight is between two known visitors")
        if not isinstance(fight["weapons"], dict) or set(fight["weapons"]) != {fight["a"], fight["b"]} \
                or not set(fight["weapons"].values()) <= set(WEAPONS):
            raise ValueError("A saved fight's weapons must name its two fighters and kinds the game has")
        if type(fight["witnessed"]) is not bool:
            raise ValueError("A saved fight's witnessed flag must be true or false")
        _check_times(fight, world["time"])
        _check_outcome(fight, busy)
        for entry in fight["waiting"] if isinstance(fight["waiting"], list) else [None]:
            if not isinstance(entry, dict) or set(entry) != {"id", "against"} or entry["id"] not in known \
                    or entry["against"] not in (fight["a"], fight["b"]):
                raise ValueError("A saved fight's waiting list names a visitor and the fighter they wait for")
    held = {item["id"]: item["action"] for item in world["actors"]}
    for actor_id in busy:
        action = held.get(actor_id)
        if action is None or action["verb"] != FIGHT:
            raise ValueError("A visitor in a running fight must be holding the fight verb")


def _check_times(fight: Mapping[str, Any], now: float) -> None:
    for key in ("started_at", "next_exchange_at"):
        value = fight[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid saved fight {key}")
    if fight["started_at"] > now:
        raise ValueError("A saved fight began in the future")
    if not isinstance(fight["exchanges"], list) or any(
            not isinstance(item, dict) or set(item) != {"time", "attacker", "hit", "damage"}
            or item["attacker"] not in (fight["a"], fight["b"]) or type(item["hit"]) is not bool
            or type(item["damage"]) not in (int, float) or item["damage"] < 0 for item in fight["exchanges"]):
        raise ValueError("Invalid saved exchanges")


def _check_outcome(fight: Mapping[str, Any], busy: set[str]) -> None:
    outcome, loser, ended = fight["outcome"], fight["loser"], fight["ended_at"]
    if outcome is None:
        if loser is not None or ended is not None:
            raise ValueError("A running fight has no loser and no end")
        if busy & {fight["a"], fight["b"]}:
            raise ValueError("A visitor is in two running fights")
        busy.update((fight["a"], fight["b"]))
        return
    if outcome not in OUTCOMES or type(ended) not in (int, float) or ended < fight["started_at"]:
        raise ValueError("Invalid saved fight outcome")
    if loser is not None and loser not in (fight["a"], fight["b"]):
        raise ValueError("A saved fight's loser must be one of its two")
