"""Activity families: one first-stage option per family, standing for its concrete actions."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.body.activities import ACTIVITIES


def group_families(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Offer one option per activity family, for the first stage of a choice.

    Args:
        candidates: Unique concrete actions, in the order they should be offered.

    Returns:
        One option per family, where its first member stood. A family with a single action
        is offered as that action; a family with several is offered as a family option,
        `{"id": family, "verb": family, "target_id": None, "members": [...]}`, which a
        second stage resolves to one of its members, kept in candidate order.

    Raises:
        ValueError: A candidate's verb is not in the activity table.
    """
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for action in candidates:
        if action["verb"] not in ACTIVITIES:
            raise ValueError(f"No activity family for the verb {action['verb']!r}")
        groups.setdefault(ACTIVITIES[action["verb"]].family, []).append(action)
    return [dict(members[0]) if len(members) == 1 else
            {"id": family, "verb": family, "target_id": None, "members": [dict(item) for item in members]}
            for family, members in groups.items()]


def family_scores(options: Sequence[Mapping[str, Any]], scores: Mapping[str, float]) -> dict[str, float]:
    """Score first-stage options from the scores of concrete actions.

    Args:
        options: First-stage options, from `group_families`.
        scores: Score per concrete action ID, covering every member.

    Returns:
        Score per option ID: an action keeps its own, a family is worth its best member.

    Raises:
        KeyError: A concrete action has no score.
    """
    return {option["id"]: max(scores[item["id"]] for item in option.get("members", [option]))
            for option in options}
