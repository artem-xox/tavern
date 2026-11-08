"""What an activity does when it lands: pour, drink, open a scene, give, shove, go home and the rest."""

from typing import Any

from tavern.body.blows import shove_result
from tavern.body.drunkenness import drink_beer, drunk_stage
from tavern.body.fights import fight_of, fighter_of, open_fight, opponent_of, try_separating
from tavern.body.items import ITEMS
from tavern.body.wounds import DOWN_SECONDS, GROGGY_SECONDS, STAGGER_SECONDS, lay_low, treat
from tavern.hall.chance import roll
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.social.aims import begin_aim
from tavern.social.giving import hand_over
from tavern.social.invitations import begin_errand
from tavern.social.names import called
from tavern.social.scenes import conversation_of, join_conversation, start_conversation
from tavern.social.signature_acts import open_interview
from tavern.social.tables import intrude
from tavern.social.thoughts import opinion_of, think


def pour(world: World, actor: Actor, tap: dict[str, Any] | None) -> None:
    if tap is None:
        raise ValueError("Pouring a beer needs a tap")
    tap["stock"] -= 1
    actor["inventory"]["beer"] += 1


def drink(world: World, actor: Actor, target: dict[str, Any] | None) -> None:
    actor["inventory"]["beer"] -= 1
    actor["visit"]["beers"] += 1
    # Guests without a tolerance trait (cards add it in E10) drink like a middling drinker.
    tolerance = actor["traits"].get("tolerance", 0.5)
    before = drunk_stage(actor["drunkenness"])
    actor["drunkenness"] = drink_beer(actor["drunkenness"], tolerance, world["rules"]["drunkenness"])
    after = drunk_stage(actor["drunkenness"])
    # Crossing into drunk or wasted is a moment of its own: the client shows it, and the evening's metrics count it.
    if after.floor > before.floor and after.name in ("drunk", "wasted"):
        record_event(world, actor, f"got_{after.name}", f"{actor['name']} is {after.name} now")


def open_scene(world: World, actor: Actor, partner: Actor | None) -> None:
    if partner is None:
        raise ValueError("Starting a conversation needs a partner")
    start_conversation(world, actor, partner)
    begin_aim(world, actor, partner)


def join_scene(world: World, actor: Actor, member: Actor | None) -> None:
    if member is None:
        raise ValueError("Joining a conversation needs a member to join")
    join_conversation(world, actor, member)
    begin_aim(world, actor, member)


def approach_scene(world: World, actor: Actor, partner: Actor | None) -> None:
    if partner is None:
        raise ValueError("Walking over for a word needs a partner")
    if conversation_of(world, partner["id"]) is None:
        start_conversation(world, actor, partner)
    else:
        join_conversation(world, actor, partner)
    begin_aim(world, actor, partner)


def interview(world: World, actor: Actor, partner: Actor | None) -> None:
    if partner is None:
        raise ValueError("An interview needs someone to interview")
    approach_scene(world, actor, partner)
    open_interview(world, actor, partner)


def start_fight(world: World, actor: Actor, target: Any) -> None:
    # Both fighters carry the fight verb at each other; the one who chose it opens the fight, the other joins it.
    action = actor["action"]
    victim = find_actor(world, action["target_id"]) if action else None
    if victim is None or fight_of(world, actor["id"]) is not None:
        return
    open_fight(world, actor, victim)


def give(world: World, actor: Actor, receiver: Actor | None) -> None:
    action = actor["action"]
    if receiver is None or action is None or action.get("item") is None:
        raise ValueError("Giving needs someone to give to and an item to give")
    hand_over(world, actor, receiver, action["item"])


def bring_drink(world: World, actor: Actor, receiver: Actor | None) -> None:
    if receiver is None:
        raise ValueError("Bringing a drink needs someone to bring it to")
    begin_errand(world, actor, receiver, "buy_drink", unasked=True)


_SHOVES = {"staggered": ("stumbled back", STAGGER_SECONDS), "down": ("went sprawling", DOWN_SECONDS)}


def shove(world: World, actor: Actor, victim: Actor | None) -> None:
    # Both remember it, and it is one sound; the shoved holds a grudge, and may be staggered or thrown to the floor.
    if victim is None:
        raise ValueError("A hostile act needs someone to turn on")
    message = f"{actor['name']} shoved {victim['name']}"
    for member in (actor, victim):
        record_event(world, member, "shove", message)
    think(victim, "shoved", world["time"], f"{called(victim, actor)} shoved me", message, about=actor)
    result = shove_result(fighter_of(actor, "fists"), fighter_of(victim, "fists"),
                          roll(world, "shove", actor["id"], victim["id"]))
    if result in _SHOVES and fight_of(world, victim["id"]) is None:
        words, seconds = _SHOVES[result]
        lay_low(victim, result, world["time"] + seconds)
        record_event(world, victim, result, f"{victim['name']} {words}")


def use_remedy(world: World, actor: Actor, target: Any) -> None:
    actor["inventory"]["remedy"] -= 1
    treat(actor)
    record_event(world, actor, "tended", f"{actor['name']} took a remedy and looks better already")


def ask_for_remedy(world: World, actor: Actor, healer: Actor | None) -> None:
    # The healer hands one over unless they think too ill of the asker, as a receiver refuses a gift from a foe.
    kind = next((name for name, item in ITEMS.items() if item.cures and healer and healer["inventory"][name] > 0), None)
    if healer is None or kind is None:
        name = healer["name"] if healer else "Nobody"
        record_event(world, actor, "no_remedy", f"{name} had no remedy to give {actor['name']}")
    elif opinion_of(healer, actor["id"], world["time"]) < world["rules"]["giving"]["refuse_below"]:
        message = f"{healer['name']} would not give {actor['name']} a remedy"
        for member in (healer, actor):
            record_event(world, member, "remedy_refused", message)
    else:
        hand_over(world, healer, actor, kind)


def help_up(world: World, actor: Actor, fallen: Actor | None) -> None:
    if fallen is None or fallen["condition"] not in ("down", "out"):
        return
    fallen["condition"], fallen["condition_until"] = "groggy", world["time"] + GROGGY_SECONDS
    message = f"{actor['name']} helped {fallen['name']} to their feet"
    for member in (actor, fallen):
        record_event(world, member, "helped_up", message)
    think(fallen, "helped_up", world["time"], f"{called(fallen, actor)} helped me up off the floor", message, about=actor)


def intervene(world: World, actor: Actor, fighter: Actor | None) -> None:
    fight = fight_of(world, fighter["id"]) if fighter else None
    if fight is None:
        return
    other = find_actor(world, opponent_of(fight, fighter["id"])) if fighter else None
    if fighter is None or other is None or not try_separating(world, fight, actor, (fighter, other)):
        record_event(world, actor, "brushed_off", f"{actor['name']} tried to part them and was shaken off")


def join_fight(world: World, actor: Actor, target: Actor | None) -> None:
    # They take their place beside the fight; the next duel is theirs when this one is over (`fights.begin_waiting`).
    fight = fight_of(world, target["id"]) if target else None
    if target is None or fight is None or any(item["against"] == target["id"] for item in fight["waiting"]):
        return
    fight["waiting"].append({"id": actor["id"], "against": target["id"]})
    record_event(world, actor, "joined_fray", f"{actor['name']} squared up to wait a turn against {target['name']}")


def go_home(world: World, actor: Actor, door: dict[str, Any] | None) -> None:
    # step_world moves the visitor out once every actor has finished this tick.
    actor["visit"]["left_at"] = world["time"]


def fall_asleep(world: World, actor: Actor, target: Any) -> None:
    record_event(world, actor, "dozed_off", f"{actor['name']} fell asleep at the table")


def wake_up(world: World, actor: Actor, target: Any) -> None:
    record_event(world, actor, "woke_up", f"{actor['name']} woke up at the table")


def settle(world: World, actor: Actor, seat: dict[str, Any] | None) -> None:
    # The chair a visitor sits down on becomes their own; taking someone else's own seat wrongs them, and sitting down
    # at a table others hold without being welcome there upsets its hosts.
    if seat is None:
        raise ValueError("Settling down needs a seat")
    if actor["seat_id"] != seat["id"]:
        for owner in world["actors"]:
            if owner["id"] != actor["id"] and owner["favorite_seat_id"] == seat["id"]:
                message = f"{actor['name']} took {owner['name']}'s seat ({seat['name']})"
                record_event(world, owner, "seat_taken", message)
                think(owner, "seat_taken", world["time"], f"{called(owner, actor)} took my seat ({seat['name']})",
                      message, about=actor)
    if actor["seat_id"] != seat["id"]:
        intrude(world, actor, seat)
    actor.update({"seat_id": seat["id"], "favorite_seat_id": seat["id"]})
