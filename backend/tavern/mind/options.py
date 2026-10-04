"""The sentence for each option a visitor may take, told from their own view."""

from collections.abc import Callable, Mapping
from typing import Any

from tavern.body.activities import FAMILIES
from tavern.mind.hall_view import (company_at, headcount, in_use, known_object, label_of, line_place, place_words,
                              steps_to, visible_visitor, walk_words)

Observation = Mapping[str, Any]
Action = Mapping[str, Any]


def option_text(observation: Observation, action: Action) -> str:
    """Describe one concrete option in plain words, from the visitor's own view.

    Args:
        observation: The visitor's observation.
        action: A candidate with `verb` and `target_id`.

    Returns:
        A sentence; using a busy place with a line reads as waiting in it.

    Raises:
        ValueError: The verb has no sentence in `_OPTIONS`.
    """
    if action["verb"] not in _OPTIONS:
        raise ValueError(f"Cannot describe the action verb {action['verb']!r}")
    return _waiting(observation, action) or _OPTIONS[action["verb"]](observation, action)


def _waiting(observation: Observation, action: Action) -> str:
    # Using a busy place with a line means waiting in it; staying in line is the same choice again.
    item = known_object(observation, action.get("target_id"))
    if item is None or "queue_spots" not in item or action["verb"] == "cut_in_line":
        return ""
    ahead, joined = line_place(observation, item)
    used, place = in_use(observation, item), place_words(item)
    if joined and not ahead:
        return f"keep waiting in line for {place} (they are next{', while someone uses it' if used else ''})"
    parts = [f"{headcount(ahead)} {'is' if ahead == 1 else 'are'} waiting for {place}"
             f"{' ahead of them' if joined else ''}"] if ahead else []
    note = ", and ".join([*parts, *(["someone is using it"] if used else [])])
    if joined:
        return f"keep waiting in line for {place} ({note})"
    return f"walk {walk_words(steps_to(observation, item))} to {place} and wait in line ({note})" if note else ""


def _cut(observation: Observation, action: Action) -> str:
    item = _target(observation, action)
    ahead = line_place(observation, item)[0]
    return (f"push to the front of the line for {place_words(item)}, ahead of the {headcount(ahead)} waiting, "
            "who will resent it")


def _target(observation: Observation, action: Action) -> Mapping[str, Any]:
    target = known_object(observation, action["target_id"])
    if target is None:
        raise ValueError(f"Cannot describe an unknown target {action['target_id']!r}")
    return target


def _pour(observation: Observation, action: Action) -> str:
    tap = _target(observation, action)
    return (f"walk {walk_words(steps_to(observation, tap))} to the tap and pour a mug of ale "
            f"({tap.get('stock')} servings when last seen)")


def _drink(observation: Observation, action: Action) -> str:
    if observation["actor"].get("seat_id"):
        return "sip the mug of ale they are holding, right here in their seat"
    return "drink the mug of ale they are holding where they stand, as there is no seat to be had"


def _rest(observation: Observation, action: Action) -> str:
    chair = _target(observation, action)
    return f"walk {walk_words(steps_to(observation, chair))} to {label_of(chair)} and rest there"


def _seat_note(observation: Observation, chair: Mapping[str, Any]) -> str:
    table = known_object(observation, chair.get("table_id"))
    comforts = " and ".join(chair.get("comforts", [])) or "no special comfort"
    return (f"{label_of(table) if table else label_of(chair)} (appeal {chair.get('appeal', 0.0):.1f}, {comforts}; "
            f"{company_at(observation, chair.get('table_id'))}; {walk_words(steps_to(observation, chair))} away)")


def _seating(observation: Observation, action: Action) -> str:
    actor = observation["actor"]
    free = [item for item in observation["objects"] if item["kind"] == "chair" and item.get("table_id")
            and not in_use(observation, item) and item["id"] != actor.get("favorite_seat_id")]
    tables = {item["table_id"]: _seat_note(observation, item) for item in free}
    choice = "; ".join(tables.values()) or "none"
    if actor.get("favorite_seat_id"):
        return f"leave their own seat for a free chair at another table, for instance to join company (free: {choice})"
    return f"look for a seat and sit down (tables with a free chair: {choice})"


def _sit(observation: Observation, action: Action) -> str:
    actor, chair = observation["actor"], _target(observation, action)
    company = company_at(observation, chair.get("table_id"))
    if chair["id"] == actor.get("seat_id"):
        return f"stay in their seat, {label_of(chair)}, a while longer to rest, sip and chat ({company})"
    if chair["id"] == actor.get("favorite_seat_id"):
        return f"walk {walk_words(steps_to(observation, chair))} back to their own seat, {label_of(chair)}, and sit down ({company})"
    return f"take the chair {label_of(chair)}: {_seat_note(observation, chair)}"


def _someone(observation: Observation, visitor_id: Any) -> Mapping[str, Any] | None:
    # Everyone in sight when observed (`people`), else only seated company.
    return next((item for item in observation.get("people", []) if item["id"] == visitor_id),
                None) or visible_visitor(observation, visitor_id)


def _talk(observation: Observation, action: Action) -> str:
    partner = _someone(observation, action["target_id"])
    name = label_of(partner) if partner else action["target_id"]
    if partner and not partner.get("seat_id"):
        return f"start a conversation with {name}, who stands beside them"
    return f"chat with {name}, who sits across the table from them"


def _join(observation: Observation, action: Action) -> str:
    member = _someone(observation, action["target_id"])
    if member is None:
        raise ValueError(f"Cannot describe joining an unseen visitor {action['target_id']!r}")
    company = observation.get("people") or observation.get("visitors", [])
    names = [label_of(item) for item in company if item.get("conversation") == member.get("conversation")]
    where = "at their table" if member.get("seat_id") else "beside them"
    return f"join the conversation {' and '.join(names) or label_of(member)} are having {where}"


def _darts(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the darts board and play a round"


def _watch(observation: Observation, action: Action) -> str:
    view = _target(observation, action)
    sight = "the flames in the fireplace" if view["kind"] == "fireplace" else "the road outside a window"
    return f"walk {walk_words(steps_to(observation, view))} and watch {sight} for a while"


def _watch_dice(observation: Observation, action: Action) -> str:
    table = _target(observation, action)
    players = [_someone(observation, identifier) for identifier in (table.get("game") or {}).get("players", [])]
    names = [label_of(item) for item in players if item is not None]
    game = f"{' and '.join(names)} play dice" if len(names) == 2 else "a game of dice"
    return f"walk {walk_words(steps_to(observation, table))} to the dice table and watch {game}"


def _toilet(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the WC"


def _inspect(observation: Observation, action: Action) -> str:
    if all(item["kind"] != "toilet" for item in observation["objects"]):
        return "look around the room for places they have not found yet, such as the WC"
    return "wander around to re-check places they already know (there is nothing new to find)"


def _wait(observation: Observation, action: Action) -> str:
    return "wait where they are and do nothing for a moment"


def _leave(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the front door and go home for the night"


def family_text(observation: Observation, option: Action) -> str:
    """Describe a family option: its wish, with three examples of what it could be.

    Args:
        observation: The visitor's observation.
        option: A family option holding its `members`.

    Returns:
        "<family>: <example>; or <example>..." with any further members only counted.
    """
    members = option["members"]
    shown = "; or ".join(option_text(observation, item) for item in members[:3])
    more = f"; or one of {len(members) - 3} more like these" if len(members) > 3 else ""
    return f"{FAMILIES[option['verb']]}: {shown}{more}"


# Each verb's option sentence; a new verb needs an entry here (and one in `activities.ACTIVITIES`).
_OPTIONS: Mapping[str, Callable[[Observation, Action], str]] = {
    "take_beer": _pour, "drink": _drink, "rest": _rest, "seating": _seating, "sit": _sit, "talk": _talk,
    "join_conversation": _join, "play_darts": _darts, "watch": _watch, "watch_dice": _watch_dice,
    "use_toilet": _toilet,
    "inspect": _inspect, "wait": _wait, "leave": _leave, "cut_in_line": _cut}
