"""The question a guest's mind is asked when it takes stock: the shared prefix, the guest, and the moment in words."""

from collections.abc import Mapping
from typing import Any

from tavern.mind.goals import GOALS, goal_words
from tavern.mind.questions import Question


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
    people = "; ".join(f"{name} (id \"{key}\")" for key, name in view["others"].items()) or "no one"
    return (f"Guests they could set a goal about: {people}. Goal kinds: "
            + "; ".join(f"{kind} = {goal_words({'kind': kind, 'target': None, 'status': 'active'}, 'that guest')}"
                        for kind in GOALS) + ".")


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
        _others(view),
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
                   "description": "The ID of the guest the goal is about, or null when the goal is none."}},
        "required": ["thought", "intention", "goal", "target"], "additionalProperties": False}
