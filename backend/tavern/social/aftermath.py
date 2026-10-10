"""What a fight leaves behind in the minds of those in it and those who saw it: events and thoughts."""

from collections.abc import Mapping
from typing import Any

from tavern.body.blows import Ending
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.social.names import called
from tavern.social.scenes import conversation_of, start_conversation
from tavern.social.thoughts import think


def bout_ended(world: World, fight: Mapping[str, Any], result: Ending) -> None:
    """Say how a fight ended and give each fighter the thoughts it leaves.

    Args:
        world: World whose events and fighters' thoughts are updated in place.
        fight: The fight, with `a`, `b` and, where there is one, the `loser`.
        result: How it ended.
    """
    first, second = find_actor(world, fight["a"]), find_actor(world, fight["b"])
    if first is None or second is None:
        return
    winner, loser = ((second, first) if fight["loser"] == first["id"] else (first, second)) if fight["loser"] else (None, None)
    message = _words(result.kind, first, second, winner, loser)
    for member in (first, second):
        record_event(world, member, "fight_ended", message)
    now = world["time"]
    if winner is not None and loser is not None:
        kind = "knocked_out_by" if result.kind == "knockout" else "lost_fight"
        think(winner, "won_fight", now, f"I beat {called(winner, loser)}", message, about=loser)
        think(loser, kind, now, f"{called(loser, winner)} beat me", message, about=winner)
        return
    kind = "knocked_out_by" if result.kind == "double_knockout" else "fought"
    for member, other in ((first, second), (second, first)):
        think(member, kind, now, f"{called(member, other)} and I came to blows", message, about=other)


def _words(kind: str, first: Actor, second: Actor, winner: Actor | None, loser: Actor | None) -> str:
    if winner is not None and loser is not None:
        return (f"{winner['name']} knocked {loser['name']} out cold" if kind == "knockout"
                else f"{loser['name']} gave up and backed away from {winner['name']}")
    if kind == "double_knockout":
        return f"{first['name']} and {second['name']} knocked each other out"
    return (f"{first['name']} and {second['name']} broke apart, still shouting at each other" if kind == "shouting"
            else f"{first['name']} and {second['name']} were pulled apart" if kind == "separated"
            else f"{first['name']} and {second['name']} broke apart")


def keep_cursing(world: World, fight: Mapping[str, Any]) -> None:
    """Have two who broke apart still hot go on cursing each other: a scene of their own, about the fight.

    Args:
        world: World whose conversations receive it.
        fight: The fight that ended `shouting`, with its two fighters.
    """
    first, second = find_actor(world, fight["a"]), find_actor(world, fight["b"])
    if first is None or second is None or conversation_of(world, first["id"]) or conversation_of(world, second["id"]):
        return
    start_conversation(world, first, second)["topic"] = "the fight they have just had"
