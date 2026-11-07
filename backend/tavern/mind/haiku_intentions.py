"""How Claude Haiku is asked for a guest's intention, and how its answer is read."""

from collections.abc import Collection, Mapping
from typing import Any

from tavern.mind.goals import GOALS, check_goal, goal_words
from tavern.mind.intentions import Intender, Written, check_intention
from tavern.mind.questions import Ask, Question


def _wishes(view: Mapping[str, Any]) -> list[str]:
    # Their obsessions by number, so the answer can name the one this intention serves.
    if not view["obsessions"]:
        return []
    numbered = "; ".join(f"{index}: {text}" for index, text in enumerate(view["obsessions"]))
    return [f"Their obsessions tonight, by number: {numbered}. Name the number of the one this intention serves, "
            "or null when it serves none."]


def _previous(view: Mapping[str, Any]) -> str:
    previous = view["previous"]
    if previous is None:
        return "Their previous thought and intention: none yet."
    goal = previous.get("goal")
    aim = "" if goal is None else (f" Their previous goal: {goal_words(goal, view['others'].get(goal['target']))} "
                                   f"({goal['status']}).")
    return (f"Their previous thought: \"{previous['thought']}\" Their previous intention: \"{previous['intention']}\" "
            f"(decided at {previous['written_at']:.0f} s, after: {previous['trigger']['text']}).{aim}")


def _duty(view: Mapping[str, Any]) -> list[str]:
    # Someone at work stays at their post: their thought, intention and goal are about the work and the people
    # who come to the bar, never games, money or leaving it.
    if view["duty"] is None:
        return []
    return [f"{view['name']} is on duty behind the {view['duty']} all evening. What they want must be what a "
            "barkeep wants: pouring, keeping the peace, hearing the news from those who lean on the bar. Never "
            "games, wagers or money, and never leaving the bar."]


def _others(view: Mapping[str, Any]) -> str:
    # Each guest with the goal kinds the hall can carry out for them now: the same list `parse_stance` checks against.
    people = "; ".join(f"{name} (id \"{key}\"; goals open: {', '.join(view['possible'][key]) or 'none'})"
                       for key, name in view["others"].items()) or "no one"
    return (f"Guests they could set a goal about: {people}. Goal kinds: "
            + "; ".join(f"{kind} = {goal_words({'kind': kind, 'target': None, 'status': 'active'}, 'that guest')}"
                        for kind in GOALS) + f". Goals about no one (target null) open now: {', '.join(view['alone']) or 'none'}.")


def _earlier(view: Mapping[str, Any]) -> list[str]:
    # The latest lines they said or heard tonight, so their mind builds on talk it already had.
    lines = [f"{line['speaker']}: \"{line['line']}\"" for scene in view["earlier"] for line in scene["lines"]]
    return [f"What they said and heard lately, oldest first: {' / '.join(lines)}."] if lines else []


def intention_question(prefix: str, view: Mapping[str, Any]) -> Question:
    """Ask the mind for a guest's thought and intention.

    Args:
        prefix: Shared system prefix, the same for every guest (world notes, rules, examples); it
            should exceed the model's minimum cacheable length.
        view: The guest's view (see `intention_view`).

    Returns:
        The question: the prefix, then the guest's card as its own cached block, then the moment.

    Raises:
        ValueError: The prefix is blank.
    """
    if not prefix.strip():
        raise ValueError("An intention question needs a shared prefix")
    thoughts = "; ".join(view["thoughts"]) or "none"
    content = "\n".join([
        f"It is {view['time']:.0f} s into the evening. {view['name']} takes stock now.",
        f"What prompted it: {view['trigger']['text']}.", _previous(view),
        f"The situation as they see it: {view['situation']}",
        f"Thoughts on their mind: {thoughts}.", *_earlier(view), f"Drink: they are {view['drink']}.", *_duty(view),
        *_wishes(view), _others(view),
        f"Write {view['name']}'s thought, intention and goal."])
    return Question(system=[prefix, view["card"]], content=content, schema=_schema(), max_tokens=250)


def _schema() -> dict[str, Any]:
    text = {"type": "string"}
    # The goal's kinds and people are checked at the boundary (`parse_stance`), so the schema is the same
    # for every guest and moment and stays cacheable.
    return {"type": "object", "properties": {
        "thought": {**text, "description": "One first-person sentence: how they read the situation now."},
        "intention": {**text, "description": "One sentence: what they want to do next."},
        "goal": {**text, "description": "A goal kind, or none when they set out to do nothing in particular."},
        "target": {"anyOf": [text, {"type": "null"}],
                   "description": "The ID of the guest the goal is about, or null when the goal is none."},
        # Not required: a guest without obsessions has none to name (checked against the card at the boundary).
        "obsession": {"anyOf": [{"type": "integer"}, {"type": "null"}],
                      "description": "The number of the obsession this intention serves, or null."}},
        "required": ["thought", "intention", "goal", "target"], "additionalProperties": False}


def parse_stance(answer: Any, others: Mapping[str, str], on_duty: bool = False, obsessions: int = 0,
                 possible: Mapping[str, Collection[str]] | None = None, alone: Collection[str] | None = None) -> Written:
    """Check what the mind answered at the boundary.

    Args:
        answer: Decoded answer: a thought, an intention, a goal kind (or "none") and its person's ID.
        others: Guests in the hall besides the one asking: ID to name (`intention_view`).
        on_duty: Whether the one asking works behind a bar (`intention_view`'s `duty`).
        obsessions: How many obsessions the guest's card lists (`len(intention_view["obsessions"])`).
        possible: For each guest, the goal kinds the hall can carry out now (`intention_view`'s `possible`); None
            asks nothing of the hall.

    Returns:
        The thought, the intention, the goal they name, active, or none, and the obsession they serve.

    Raises:
        ValueError: The answer is not those four fields, with at most an `obsession`; a text is blank or over 400
            characters, the obsession is not an index into the card's list, the goal kind is not in `GOALS` or not open to someone on duty, its person is not in the hall, or the
            hall cannot carry it out for that person now.
    """
    if not isinstance(answer, Mapping) or set(answer) - {"obsession"} != {"thought", "intention", "goal", "target"}:
        raise ValueError(f"An answer has a thought, an intention, a goal and a target, not {answer!r}")
    kind = answer["goal"]
    if not isinstance(kind, str) or not (answer["target"] is None or isinstance(answer["target"], str)):
        raise ValueError(f"A goal is a kind and the ID of a guest, not {kind!r} and {answer['target']!r}")
    goal = check_goal(None if kind == "none" else kind, answer["target"], others, on_duty, possible, alone)
    return check_intention({"thought": answer["thought"], "intention": answer["intention"], "goal": goal,
                            "obsession": answer.get("obsession")}, obsessions)


def intention_writer(prefix: str, ask: Ask) -> Intender:
    """Bind the mind-layer port into a writer of intentions.

    Args:
        prefix: Shared system prefix (see `intention_question`).
        ask: Model port, e.g. Claude Haiku through `claude.ask_claude`, recorded or replayed.

    Returns:
        A writer that asks the port and validates the answer; it raises what the port raises,
        or ValueError for an invalid answer.
    """
    async def write(view: Mapping[str, Any]) -> Written:
        return parse_stance(await ask(intention_question(prefix, view)), view["others"], view["duty"] is not None,
                            len(view["obsessions"]), view["possible"], view["alone"])
    return write
