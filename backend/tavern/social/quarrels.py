"""How hot a quarrel has run, read from the insults a scene's last turns hold."""

from collections.abc import Callable, Mapping
from typing import Any

from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.social.hostility import may_fight, urge
from tavern.social.scenes import end_conversation

# The run of insults (two each) at which a quarrel boils over.
BOIL = 4

# How the world starts an action for a visitor (`lifecycle.activate`).
Activate = Callable[..., None]


def heat(scene: Mapping[str, Any]) -> int:
    """Count the insults two guests have traded, one after the other, at the end of a scene.

    Args:
        scene: A conversation scene with its `turns`.

    Returns:
        The length of the run of `insult` turns ending the scene, each addressed to the guest who spoke the one
        before it. Any other act, a third speaker, one speaker twice in a row, or an insult to nobody in
        particular ends the run; 0 for a scene with no turns or whose last turn is not an insult.
    """
    run, later = 0, None
    for turn in reversed(scene["turns"]):
        if turn["act"] != "insult" or turn["addressee"] is None:
            break
        # Each insult answers the one after it: the later speaker is the one this turn insulted, and the reverse.
        if later is not None and (later["speaker"] != turn["addressee"] or later["addressee"] != turn["speaker"]):
            break
        run, later = run + 1, turn
    return run


def boil_over(world: World, activate: Activate) -> None:
    """End every scene whose quarrel has run to `BOIL` insults: in a fight if either may start one, else a walk-off.

    Args:
        world: World whose scenes, fighters and event log are updated in place.
        activate: How the world starts an action for a visitor (`lifecycle.activate`).
    """
    for scene in list(world["conversations"]):
        if heat(scene) < BOIL:
            continue
        last = scene["turns"][-1]
        speaker, insulted = (_member(world, last["speaker"]), _member(world, last["addressee"]))
        attacker = _attacker(world, speaker, insulted)
        end_conversation(world, scene, pleasant=False)
        for member, other in ((speaker, insulted), (insulted, speaker)):
            _settle(world, member, other)
        if attacker is None:
            message = f"{insulted['name']} stormed off from {speaker['name']}"
            for member in (speaker, insulted):
                record_event(world, member, "stormed_off", message)
            continue
        victim = insulted if attacker is speaker else speaker
        activate(world, attacker, {"id": f"start_fight:{victim['id']}", "verb": "start_fight",
                                   "target_id": victim["id"]}, (None, []))


def _member(world: World, actor_id: str | None) -> Actor:
    found = find_actor(world, actor_id) if actor_id is not None else None
    if found is None:
        raise ValueError(f"{actor_id!r} quarreled in a scene but is not in the hall")
    return found


def _attacker(world: World, speaker: Actor, insulted: Actor) -> Actor | None:
    # Of those a quarrel brings to a fight, the hotter head strikes; on a tie, the one who insulted last, since the
    # other has only been provoked.
    ready = [(urge({"actor": member}), member is speaker, member) for member, other in
             ((speaker, insulted), (insulted, speaker)) if may_fight(member, other["id"], world["time"])]
    return max(ready, key=lambda item: item[:2])[2] if ready else None


def _settle(world: World, member: Actor, other: Actor) -> None:
    # A boiled quarrel has had its say: left open, the insult and the quarrel call each to go and "have it out" with
    # the other at once, and the same talk starts again.
    for thought in member["thoughts"]:
        if thought["about"] == other["id"] and thought["kind"] in ("insulted", "quarrel"):
            thought["answered"] = True
