"""The sentences for the options a fight or a hurt brings, told from the guest's own view."""

from collections.abc import Callable, Mapping
from typing import Any

from tavern.mind.hall_view import label_of, visible_visitor

Observation = Mapping[str, Any]
Action = Mapping[str, Any]


def _someone(observation: Observation, person_id: Any) -> Mapping[str, Any] | None:
    return next((item for item in observation.get("people", []) if item["id"] == person_id),
                None) or visible_visitor(observation, person_id)


def _name(observation: Observation, person_id: Any) -> str:
    person = _someone(observation, person_id)
    return label_of(person) if person else str(person_id)


def _fighters(observation: Observation) -> str:
    # "Rurik and Toren" for each pair in sight, told once however many of the two are in view; "the fighters" if none.
    pairs: list[tuple[str, str]] = []
    for person in observation.get("people", []):
        if person.get("fighting") and not any(person["id"] in pair for pair in pairs):
            pairs.append((person["id"], person["fighting"]))
    told = [f"{_name(observation, first)} and {_name(observation, second)}" for first, second in pairs]
    return " and also ".join(told) or "the fighters"


def _watch(observation: Observation, action: Action) -> str:
    return f"stay where they are and watch {_fighters(observation)} fight, like the rest of the room"


def _cheer(observation: Observation, action: Action) -> str:
    return f"shout and cheer {_fighters(observation)} on (rowdy company's way; the fighters hear it)"


def _intervene(observation: Observation, action: Action) -> str:
    name = _name(observation, action["target_id"])
    person = _someone(observation, action["target_id"]) or {}
    other = _name(observation, person.get("fighting"))
    return (f"step between {name} and {other} and try to part them (it may not work, and a fight is hard to be "
            "caught in)")


def _join(observation: Observation, action: Action) -> str:
    name = _name(observation, action["target_id"])
    return (f"square up beside {name}, who is fighting, and wait a turn to take them on when their fight is over "
            "(fights are one on one)")


def _help_up(observation: Observation, action: Action) -> str:
    return f"help {_name(observation, action['target_id'])}, who lies on the floor, up on their feet"


def _seek(observation: Observation, action: Action) -> str:
    return (f"go to {_name(observation, action['target_id'])}, who carries remedies, and ask for one to mend their "
            "hurts (a healer who thinks ill of them may refuse)")


def _use(observation: Observation, action: Action) -> str:
    return "take one of the herbal remedies they carry and mend their hurts at once"


# One sentence per verb that a fight or a hurt brings; `options._OPTIONS` takes them in.
TEXTS: Mapping[str, Callable[[Observation, Action], str]] = {
    "watch_fight": _watch, "cheer": _cheer, "intervene": _intervene, "join_fight": _join, "help_up": _help_up,
    "seek_remedy": _seek, "use_remedy": _use}
