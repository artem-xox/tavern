"""Goals: what a guest's mind may set out to do, which options serve it, and when it is done, failed or lapsed.

A goal is one kind from `GOALS` plus, for a kind about a person, who. The mind names a goal instead of
promising something in prose: a kind the table lacks or a person who is not in the hall is refused at the
boundary, so every goal is one the world can carry out. The choice reads the goal as a mark on the options
that serve it (`serving`), and `settle_goals` decides, from what the world logged, how each goal ended.
"""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.body.dozing import asleep
from tavern.hall.memory import record_event
from tavern.hall.staff import on_staff
from tavern.hall.state import World, find_actor
from tavern.mind.hall_view import Observation, known_object
from tavern.social.names import called
from tavern.social.thoughts import THOUGHTS, opinion_of

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
        on_duty: Whether someone at work behind a bar may set it: it keeps them at their post.
        serves: Whether an action (a concrete one: `id`, `verb`, `target_id`) brings the guest closer to it,
            read from their observation.
        reached: Whether the world shows it done: the guest, the goal's person, and the game time the
            goal was written at.
        aims: Aims (`aims.AIMS`, as `aim` strings) that serve it when aimed at its person.
        possible: Whether the hall can carry it out now: the world, the guest and the goal's person (for a kind
            without a person, the guest again).
        person: Whether it is about another guest; a kind without one has no target and `reached` is given the
            guest themselves as `other`.
    """

    wording: str
    lasts: float
    on_duty: bool
    serves: Callable[[Observation, Mapping[str, Any], Goal], bool]
    reached: Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], float], bool]
    aims: tuple[str, ...] = ()
    possible: Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], bool] = lambda world, actor, other: True
    person: bool = True


def _table_of(observation: Observation, person_id: str | None) -> str | None:
    # The table a person in sight sits at, as the guest sees it.
    for person in [*observation.get("visitors", []), *observation.get("people", [])]:
        if person["id"] == person_id and person.get("seat_id"):
            return person.get("table_id")
    return None


def _talks_to(observation: Observation, action: Mapping[str, Any], goal: Goal) -> bool:
    # Walking over to someone at another table is the way to a word with them; a chair at their table is not.
    return action["verb"] in ("talk", "join_conversation", "approach") and action["target_id"] == goal["target"]


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


def _reaches_with_a_drink(observation: Observation, action: Mapping[str, Any], goal: Goal) -> bool:
    # Reaching the person to talk, or bringing them an ale.
    return _talks_to(observation, action, goal) or (action["verb"] == "bring_drink" and action["target_id"] == goal["target"])


def _came_to_think(actor: Mapping[str, Any], kinds: tuple[str, ...], other: Mapping[str, Any], since: float) -> bool:
    # A thought of one of these kinds about the person, formed after the goal was written: the game logs what
    # happened between two guests as thoughts about each other, with the person in them.
    return any(item["kind"] in kinds and item["about"] == other["id"]
               and item["expires_at"] - THOUGHTS[item["kind"]].seconds >= since for item in actor["thoughts"])


def _gave_an_ale(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    return _came_to_think(actor, ("generous",), other, since)


def _played_dice(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    return _came_to_think(actor, ("won_at_dice", "lost_at_dice"), other, since)


def _quarreled(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    return _came_to_think(actor, ("quarrel",), other, since)


def _has_object(world: Mapping[str, Any], kind: str) -> bool:
    return any(item["kind"] == kind for item in world["map"]["objects"])


def _can_stand_a_round(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    return not on_staff(other) and not asleep(other) and _has_object(world, "tap")


def _can_play_dice(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    return not on_staff(other) and not asleep(other) and _has_object(world, "dice_table")


def _can_have_it_out(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    # A quarrel is with someone they do not like: a friend, or someone asleep or behind the bar, is no one to have it out with.
    return not on_staff(other) and not asleep(other) and opinion_of(actor, other["id"], world["time"]) <= 0


def _gives_a_speech(observation: Observation, action: Mapping[str, Any], goal: Goal) -> bool:
    return action["verb"] == "give_speech"


def _has_spoken(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any], since: float) -> bool:
    # The guest's own memory holds the `gave_speech` event, logged after the goal was written.
    return any(item["type"] == "gave_speech" and item["time"] >= since for item in actor["memory"])


def _has_a_stage(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    # Only a guest with a public persona on their card climbs a stage (`speeches.performs`).
    return _has_object(world, "stage") and not asleep(actor) and bool((actor.get("card") or {}).get("persona"))


GOALS: Mapping[str, GoalKind] = MappingProxyType({
    "talk_to": GoalKind("talk with {name}", 240.0, True, _talks_to, _has_talked),
    "sit_with": GoalKind("sit at the same table as {name}", 120.0, False, _sits_with, _sit_together),
    "treat": GoalKind("buy {name} an ale", 240.0, False, _reaches_with_a_drink, _gave_an_ale,
                      aims=("invite:buy_drink",), possible=_can_stand_a_round),
    "play_with": GoalKind("play a game of dice with {name}", 300.0, False, _talks_to, _played_dice,
                          aims=("invite:dice_together", "rematch"), possible=_can_play_dice),
    "have_it_out": GoalKind("have it out with {name}", 180.0, False, _talks_to, _quarreled,
                            aims=("have_it_out", "needle"), possible=_can_have_it_out),
    "address_room": GoalKind("address the whole room from the stage", 240.0, False, _gives_a_speech, _has_spoken,
                             possible=_has_a_stage, person=False),
})


def open_kinds(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> list[str]:
    """List the goals about a person that the hall can carry out now.

    Args:
        world: The world.
        actor: The guest who would hold the goal.
        other: The goal's person.

    Returns:
        Kinds of `GOALS` about a person, in table order, whose `possible` holds: no game of dice without a dice table, no round without a
        tap, no quarrel with a friend, and none of those with someone asleep or behind the bar.
    """
    return [kind for kind, goal in GOALS.items() if goal.person and goal.possible(world, actor, other)]


def open_alone(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[str]:
    """List the goals without a person that the hall can carry out now.

    Args:
        world: The world.
        actor: The guest who would hold the goal.

    Returns:
        Kinds of `GOALS` about no one, in table order, whose `possible` holds: no address without a stage.
    """
    return [kind for kind, goal in GOALS.items() if not goal.person and goal.possible(world, actor, actor)]


def serving(observation: Observation, action: Mapping[str, Any]) -> bool:
    """Tell whether an option brings a guest closer to their active goal.

    Args:
        observation: The guest's observation; their `actor.intention` may hold a goal.
        action: A concrete action, or a family option holding `members`.

    Returns:
        True when the action, or any member of the family, serves the guest's active goal or a promise they
        made and have not yet kept (`observation["promises"]`, see `commitments.promises_of`).
    """
    intention = observation["actor"].get("intention")
    goal = intention.get("goal") if intention else None
    aims = [item for item in [goal, *observation.get("promises", [])] if item is not None and item["status"] == "active"]
    if "members" in action:
        return any(serving(observation, member) for member in action["members"])
    return any(GOALS[item["kind"]].serves(observation, action, item) for item in aims)


def serving_aim(observation: Observation, candidate: Mapping[str, Any]) -> bool:
    """Tell whether what a guest means by a social option brings them closer to their active goal.

    Args:
        observation: The guest's observation; their `actor.intention` may hold a goal.
        candidate: An aim candidate (`aims.aim_candidates`): the social action, its `aim` and its person as `target_id`.

    Returns:
        True when the aim is one of the goal kind's `aims` and is aimed at the goal's person.
    """
    intention = observation["actor"].get("intention")
    goal = intention.get("goal") if intention else None
    return (goal is not None and goal["status"] == "active" and goal["target"] == candidate["target_id"]
            and candidate["aim"] in GOALS[goal["kind"]].aims)


def goal_words(goal: Goal, name: str | None) -> str:
    """Tell a goal in words.

    Args:
        goal: The goal.
        name: What the guest calls the goal's person, or None for a kind without one.

    Returns:
        For example "talk with Brida".
    """
    return GOALS[goal["kind"]].wording.format(name=name)


def check_goal(kind: str | None, target: str | None, others: Mapping[str, str], on_duty: bool = False,
               possible: Mapping[str, Collection[str]] | None = None, alone: Collection[str] | None = None) -> Goal | None:
    """Check a goal the mind named.

    Args:
        kind: A kind of `GOALS`, or None for no goal.
        target: The guest it is about, by ID.
        others: Guests in the hall besides the one deciding: ID to name.
        on_duty: Whether the one deciding works behind a bar, and so may set only goals that keep them there.
        possible: For each guest, the kinds the hall can carry out now (`open_kinds`); None asks nothing of the hall.
        alone: The kinds about no one the hall can carry out now (`open_alone`); None asks nothing of the hall.

    Returns:
        An active goal, or None for none.

    Raises:
        ValueError: The kind is not in `GOALS` or not open to someone on duty, the person is not in the hall, no
            goal names a person, or the hall cannot carry the kind out for that person now.
    """
    if kind is None:
        if target is not None:
            raise ValueError(f"A goal without a kind cannot be about {target!r}")
        return None
    if kind not in GOALS:
        raise ValueError(f"Unknown goal kind {kind!r}; choose one of {', '.join(GOALS)}")
    if on_duty and not GOALS[kind].on_duty:
        raise ValueError(f"Goal {kind!r} would take someone on duty from the bar")
    if not GOALS[kind].person:
        if target is not None:
            raise ValueError(f"Goal {kind!r} is about no one, not {target!r}")
        if alone is not None and kind not in alone:
            raise ValueError(f"Goal {kind!r} cannot be carried out now; choose one of {', '.join(alone) or 'none'}")
        return Goal(kind=kind, target=None, status="active")
    if target is None or target not in others:
        raise ValueError(f"Goal {kind!r} must be about a guest in the hall, not {target!r}")
    if possible is not None and kind not in possible.get(target, ()):
        raise ValueError(f"Goal {kind!r} cannot be carried out for {target!r} now; choose one of "
                         f"{', '.join(possible.get(target, ())) or 'none'}")
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
        other = actor if goal["target"] is None else find_actor(world, goal["target"])
        since, kind = intention["written_at"], GOALS[goal["kind"]]
        if other is not None and kind.reached(world, actor, other, since):
            goal["status"] = "done"
        elif other is None:
            goal["status"] = "failed"
        elif world["time"] - since >= kind.lasts:
            goal["status"] = "expired"
        else:
            continue
        name = called(actor, other) if other and goal["target"] else goal["target"]
        record_event(world, actor, f"goal_{goal['status']}", f"{actor['name']}'s goal to {goal_words(goal, name)}: "
                                                              f"{goal['status']}")
