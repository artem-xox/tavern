"""When visitors ask for their next decision, and how an answer reaches the world."""

from collections.abc import Callable, Container, Mapping
from typing import Any

from tavern.body.queues import out_of_patience
from tavern.hall.closing import inn_closed
from tavern.hall.memory import record_event
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, Decision, World
from tavern.hall.world import observe_actor, observe_people, start_action
from tavern.social.scenes import conversation_of


def free_to_decide(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor can act on a decision now.

    Args:
        world: Current world.
        actor: Visitor in that world.

    Returns:
        True when they are a guest, idle or out of patience in a line, and take part in no
        conversation scene (staff never decide: their routine is `tavern.body.bartending`): members leave a scene by its own rules (a goodbye, an interrupt,
        closing time), never by being pulled away mid-chat.
    """
    return (not on_staff(actor) and (actor["status"] == "idle" or out_of_patience(world, actor))
            and conversation_of(world, actor["id"]) is None)


def decision_requests(world: Mapping[str, Any], pending: Container[str],
                      next_decision: Mapping[str, float]) -> list[tuple[str, dict[str, Any]]]:
    """List the visitors who should ask for a decision now, with what they observe.

    Args:
        world: Current world; observing refreshes each asking visitor's knowledge.
        pending: Visitors already waiting for an answer: one request per visitor at a time.
        next_decision: Earliest game time each visitor may ask again; absent means at once.

    Returns:
        (actor ID, observation) pairs in actor order for visitors free to decide.
    """
    requests = []
    for actor in world["actors"]:
        if actor["id"] in pending or not free_to_decide(world, actor):
            continue
        if world["time"] < next_decision.get(actor["id"], 0):
            continue
        # Decisions also see who else is about and what they are visibly doing.
        requests.append((actor["id"], {**observe_actor(world, actor["id"]),
                                       "people": observe_people(world, actor["id"])}))
    return requests


def stale_requests(world: Mapping[str, Any], asked_at: Mapping[str, float]) -> list[str]:
    """List the visitors whose pending request an interrupt has overtaken.

    Args:
        world: Current world.
        asked_at: Game time each pending request was made, per visitor.

    Returns:
        Visitors in actor order who were interrupted after asking: their answer no longer fits
        and they should ask again. A request made on the interrupt's own tick already saw it.
    """
    return [actor["id"] for actor in world["actors"] if actor["id"] in asked_at
            and actor["interrupted_at"] is not None and actor["interrupted_at"] > asked_at[actor["id"]]]


# Below this score for its best option a Jev decision has no good one: in five live evenings (876 decisions,
# 2026-10-05) the best option scored under 0.35 in 2.5%, under 0.40 in 4.2% (about 7 an evening) and under 0.45 in
# 7.6%. The doubts between 0.40 and 0.45 were borderline and doubled the pauses, so the line is 0.40.
UNSURE_BELOW = 0.40
# After a doubt the guest is not paused again for this long: their mind is working on it, and a chain of pauses
# would stand them idle (live seed 7: seven doubts of one guest in 140 s before this).
UNSURE_COOLDOWN = 30.0


def apply_decision(world: World, actor: Actor,
                   outcome: Callable[[], Mapping[str, Any]]) -> float:
    """Record a visitor's decision and start its action.

    Args:
        world: Authoritative mutable world; refusals and failures are logged in it.
        actor: Visitor free to decide (see `free_to_decide`).
        outcome: Returns the decision, or raises the error that prevented it, like an
            asyncio task's `result`.

    Returns:
        The earliest game time the visitor may ask for their next decision.
    """
    try:
        decision = outcome()
        actor["decision"] = Decision(source=decision["source"], scores=decision["scores"], error=decision["error"])
        for stage in ("seat", "family"):
            if stage in decision:
                actor["decision"][stage] = decision[stage]
        action = decision["action"]
        if _unsure(world, actor, decision):
            # Better a pause than a poor choice: the mind is asked, and the next decision follows its answer.
            action = {"id": "wait", "verb": "wait", "target_id": None}
        result = start_action(world, actor["id"], action)
        if not result["accepted"]:
            log_control(world, f"{actor['name']}: {result['reason']}")
    except Exception as error:
        actor["decision"] = {"source": "local", "scores": {}, "error": str(error)}
        log_control(world, f"Decision failed for {actor['name']}")
    # A second's pause after every answer, applied or refused, keeps a refused visitor from
    # asking again on every tick.
    return world["time"] + 1.0


def _unsure(world: World, actor: Actor, decision: Mapping[str, Any]) -> bool:
    # A doubt is a real model's verdict: local scores are not calibrated, and a failed call has none. The seat
    # stage is left out, since one chair is often as good as another. At closing time the guest goes home.
    if decision["source"] != "jev" or decision["error"] is not None or inn_closed(world) \
            or decision["action"]["verb"] == "wait":
        return False
    if any(item["type"] == "unsure" and world["time"] - item["time"] < UNSURE_COOLDOWN for item in actor["memory"]):
        return False
    stages = [decision["scores"], *(decision[key]["scores"] for key in ("family",) if key in decision
                                    and decision[key]["source"] == "jev" and decision[key]["error"] is None)]
    best = next((max(scores.values()) for scores in stages if scores and max(scores.values()) < UNSURE_BELOW), None)
    if best is None:
        return False
    record_event(world, actor, "unsure", f"{actor['name']} could not tell what to do: the best option scored "
                                         f"{best:.2f}")
    return True


def log_control(world: World, message: str) -> None:
    """Log an event that no visitor caused, keeping the latest 100 events.

    Args:
        world: World whose event log is appended to.
        message: Human-readable description.
    """
    world["events"].append({"time": world["time"], "actor_id": None,
                            "type": "control", "message": message})
    world["events"] = world["events"][-100:]
