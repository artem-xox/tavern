"""When visitors ask for their next decision, and how an answer reaches the world."""

from collections.abc import Callable, Container, Mapping
from typing import Any

from tavern.world import observe_actor, observe_people, start_action


def free_to_decide(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor can act on a decision now.

    Args:
        world: Current world.
        actor: Visitor in that world.

    Returns:
        True when they are idle and nobody is talking to them: a conversation partner
        is never pulled away mid-chat.
    """
    addressed = any(item.get("action") and item["action"]["verb"] == "talk"
                    and item["action"]["target_id"] == actor["id"] for item in world["actors"])
    return actor["status"] == "idle" and not addressed


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


def apply_decision(world: dict[str, Any], actor: dict[str, Any],
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
        actor["decision"] = {key: decision[key] for key in ("source", "scores", "error")}
        if "seat" in decision:
            actor["decision"]["seat"] = decision["seat"]
        result = start_action(world, actor["id"], decision["action"])
        if not result["accepted"]:
            log_control(world, f"{actor['name']}: {result['reason']}")
    except Exception as error:
        actor["decision"] = {"source": "local", "scores": {}, "error": str(error)}
        log_control(world, f"Decision failed for {actor['name']}")
    # A second's pause after every answer, applied or refused, keeps a refused visitor from
    # asking again on every tick.
    return world["time"] + 1.0


def log_control(world: dict[str, Any], message: str) -> None:
    """Log an event that no visitor caused, keeping the latest 100 events.

    Args:
        world: World whose event log is appended to.
        message: Human-readable description.
    """
    world["events"].append({"time": world["time"], "actor_id": None,
                            "type": "control", "message": message})
    world["events"] = world["events"][-100:]
