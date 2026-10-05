"""Goals: what a guest's mind may set out to do, which options serve it, and when it is done, failed or lapsed.

A goal is one kind from `GOALS` plus, for a kind about a person, who. The mind names a goal instead of
promising something in prose: a kind the table lacks or a person who is not in the hall is refused at the
boundary, so every goal is one the world can carry out. The choice reads the goal as a mark on the options
that serve it (`serving`), and `settle_goals` decides, from what the world logged, how each goal ended.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.hall.memory import record_event
from tavern.hall.state import World, find_actor
from tavern.mind.hall_view import Observation, known_object
from tavern.social.names import called

# active: being pursued; done: the world shows it was reached; failed: it can no longer be reached
# (its person left); expired: it was not reached within its time.
STATUSES = ("active", "done", "failed", "expired")


class Goal(TypedDict):
    """What a guest set out to do: a kind from `GOALS`, the guest it is about (None for a kind without
    one) and how it stands."""

    kind: str
    target: str | None
    status: str


@dataclass(frozen=True)
class GoalKind:
    """One kind of goal.

    Attributes:
        wording: How the briefing tells it; `{name}` stands for the person as the guest calls them.
        lasts: Game seconds before an unreached goal lapses.
        serves: Whether an action (a concrete one: `id`, `verb`, `target_id`) brings the guest closer to it,
            read from their observation.
        reached: Whether the world shows it done: the guest, the goal's person, and the game time the
            goal was written at.
    """

    wording: str
    lasts: float
    serves: Callable[[Observation, Mapping[str, Any], Goal], bool]
    reached: Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], float], bool]


def _table_of(observation: Observation, person_id: str | None) -> str | None:
    # The table a person in sight sits at, as the guest sees it.
    for person in [*observation.get("visitors", []), *observation.get("people", [])]:
        if person["id"] == person_id and person.get("seat_id"):
            return person.get("table_id")
    return None


def _talks_to(observation: Observation, action: Mapping[str, Any], goal: Goal) -> bool:
    if action["verb"] in ("talk", "join_conversation"):
        return action["target_id"] == goal["target"]
    # Taking a chair at their table puts them within reach of a chat.
    return _sits_with(observation, action, goal)


def _sits_with(observation: Observation, action: Mapping[str, Any], goal: Goal) -> bool:
    table = _table_of(observation, goal["target"])
    if table is None:
        return False
    # `seating` is the wish to sit, before any chair is chosen: it serves while the person sits at a table.
    return action["verb"] == "seating" or (action["verb"] == "sit" and _chair_table(observation, action) == table)


def _chair_table(observation: Observation, action: Mapping[str, Any]) -> str | None:
    chair = known_object(observation, action["target_id"])
    return chair.get("table_id") if chair else None


def _has_talked(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    # A line the other spoke where the guest was a member of the scene, after the goal was set.
    return any(line["speaker_id"] == other["id"] and line["time"] >= since for line in actor["heard"])


def _sit_together(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    chairs = {item["id"]: item.get("table_id") for item in world["map"]["objects"] if item["kind"] == "chair"}
    table = chairs.get(actor.get("seat_id"))
    return table is not None and table == chairs.get(other.get("seat_id"))


GOALS: Mapping[str, GoalKind] = MappingProxyType({
    "talk_to": GoalKind("talk with {name}", 240.0, _talks_to, _has_talked),
    "sit_with": GoalKind("sit at the same table as {name}", 120.0, _sits_with, _sit_together),
})


def serving(observation: Observation, action: Mapping[str, Any]) -> bool:
    """Tell whether an option brings a guest closer to their active goal.

    Args:
        observation: The guest's observation; their `actor.intention` may hold a goal.
        action: A concrete action, or a family option holding `members`.

    Returns:
        True when the guest has an active goal and the action, or any member of the family, serves it.
    """
    intention = observation["actor"].get("intention")
    goal = intention.get("goal") if intention else None
    if goal is None or goal["status"] != "active":
        return False
    if "members" in action:
        return any(serving(observation, member) for member in action["members"])
    return GOALS[goal["kind"]].serves(observation, action, goal)


def goal_words(goal: Goal, name: str | None) -> str:
    """Tell a goal in words.

    Args:
        goal: The goal.
        name: What the guest calls the goal's person, or None for a kind without one.

    Returns:
        For example "talk with Brida".
    """
    return GOALS[goal["kind"]].wording.format(name=name)


def check_goal(kind: str | None, target: str | None, others: Mapping[str, str]) -> Goal | None:
    """Check a goal the mind named.

    Args:
        kind: A kind of `GOALS`, or None for no goal.
        target: The guest it is about, by ID.
        others: Guests in the hall besides the one deciding: ID to name.

    Returns:
        An active goal, or None for none.

    Raises:
        ValueError: The kind is not in `GOALS`, the person is not in the hall, or no goal names a person.
    """
    if kind is None:
        if target is not None:
            raise ValueError(f"A goal without a kind cannot be about {target!r}")
        return None
    if kind not in GOALS:
        raise ValueError(f"Unknown goal kind {kind!r}; choose one of {', '.join(GOALS)}")
    if target not in others:
        raise ValueError(f"Goal {kind!r} must be about a guest in the hall, not {target!r}")
    return Goal(kind=kind, target=target, status="active")


def settle_goals(world: World) -> None:
    """End the goals the world has decided, once each, and log how.

    Args:
        world: World whose guests' goals are updated in place. A goal is done once its kind's `reached` holds,
            failed once its person has left, expired once `lasts` has passed since the intention was written;
            a `goal_done`, `goal_failed` or `goal_expired` event is remembered by the guest.
    """
    for actor in world["actors"]:
        intention = actor["intention"]
        goal = intention["goal"] if intention is not None else None
        if intention is None or goal is None or goal["status"] != "active":
            continue
        other = find_actor(world, goal["target"])
        since, kind = intention["written_at"], GOALS[goal["kind"]]
        if other is not None and kind.reached(world, actor, other, since):
            goal["status"] = "done"
        elif other is None:
            goal["status"] = "failed"
        elif world["time"] - since >= kind.lasts:
            goal["status"] = "expired"
        else:
            continue
        name = called(actor, other) if other else goal["target"]
        record_event(world, actor, f"goal_{goal['status']}", f"{actor['name']}'s goal to {goal_words(goal, name)}: "
                                                              f"{goal['status']}")
