"""Answers to what was just done to a guest: which fresh thoughts about someone call for one, and which actions give it.

No verb or family belongs to this module: an answer is an option the guest already has, aimed at the person the
thought is about. The table only says which verbs answer which thought, and for how long.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.social.names import called
from tavern.social.thoughts import THOUGHTS, Thought, active_thoughts


@dataclass(frozen=True)
class Response:
    """How a fresh thought about someone calls for an answer.

    Attributes:
        verbs: Verbs that answer it when aimed at the person the thought is about.
        within: Game seconds after the thought during which it still calls for an answer.
    """

    verbs: tuple[str, ...]
    within: float


# To have it out with someone is to go and talk to them. A blow is no answer here: hostile acts stay rare and keep
# their own gates (`tavern.social.hostility`), so nothing in this table makes a shove or a fight likelier.
_HAVE_IT_OUT = ("talk", "approach", "join_conversation")
_RETURN = (*_HAVE_IT_OUT, "give", "bring_drink")
RESPONSES: Mapping[str, Response] = MappingProxyType({
    "seat_taken": Response(_HAVE_IT_OUT, 90.0),
    "table_intruded": Response(("talk", "join_conversation"), 90.0),
    "line_cut": Response(("talk", "join_conversation"), 60.0),
    "insulted": Response(_HAVE_IT_OUT, 90.0),
    "quarrel": Response(_HAVE_IT_OUT, 90.0),
    "friend_insulted": Response(_HAVE_IT_OUT, 90.0),
    "let_down": Response(_HAVE_IT_OUT, 120.0),
    "lost_at_dice": Response(_HAVE_IT_OUT, 90.0),
    "treated": Response(_RETURN, 120.0),
    "gifted": Response(_RETURN, 120.0),
    "cared_for": Response(_RETURN, 120.0),
    "kept_word": Response(_HAVE_IT_OUT, 120.0),
    "shoved": Response(("talk",), 60.0),
})


def age_of(thought: Mapping[str, Any], now: float) -> float:
    """Tell how long ago a thought began.

    Args:
        thought: A thought of a kind in `THOUGHTS`.
        now: Current game time.

    Returns:
        Game seconds since it began, from its expiry and how long its kind lasts.
    """
    return now - (thought["expires_at"] - THOUGHTS[thought["kind"]].seconds)


def calling(actor: Mapping[str, Any], now: float) -> list[Thought]:
    """List the thoughts that call for an answer now.

    Args:
        actor: Visitor; one without `thoughts` has none.
        now: Current game time.

    Returns:
        Their active, unanswered thoughts about someone, of a kind in `RESPONSES` and no older than its window,
        in the order the visitor had them.
    """
    return [item for item in active_thoughts(actor.get("thoughts", []), now)
            if item["kind"] in RESPONSES and item["about"] is not None and not item.get("answered")
            and age_of(item, now) <= RESPONSES[item["kind"]].within]


def answering(actor: Mapping[str, Any], now: float, action: Mapping[str, Any]) -> Thought | None:
    """Find the thought an action answers.

    Args:
        actor: Visitor.
        now: Current game time.
        action: A concrete action, or a family option holding `members`.

    Returns:
        The freshest thought from `calling` that is about the action's target and has the action's verb among its
        `verbs`; for a family, the freshest any member answers. Of two equally fresh, the one the visitor had later
        wins. None when it answers nothing.
    """
    members = action.get("members", [action])
    found = [item for item in reversed(calling(actor, now)) for member in members
             if member["target_id"] == item["about"] and member["verb"] in RESPONSES[item["kind"]].verbs]
    return min(found, key=lambda item: age_of(item, now), default=None)


def mark_answered(world: World, actor: Actor, action: Mapping[str, Any]) -> None:
    """Note that a visitor has begun to answer a thought, once.

    Args:
        world: World whose event log is appended to.
        actor: Visitor who started the action, updated in place.
        action: The accepted action.

    Raises:
        ValueError: The thought is about someone who is not in the hall, which no action could answer.
    """
    thought = answering(actor, world["time"], action)
    if thought is None:
        return
    other = find_actor(world, thought["about"])
    if other is None:
        raise ValueError(f"{actor['name']} cannot answer {thought['about']!r}, who is not in the hall")
    thought["answered"] = True
    record_event(world, actor, "answered", f"{actor['name']} went to answer {called(actor, other)}, who "
                                           f"{THOUGHTS[thought['kind']].reason} ({age_of(thought, world['time']):.0f} s later)")
