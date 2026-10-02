"""Plain-language briefings: a visitor's situation and options, told from their own view."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from tavern.activities import ACTIVITIES

Observation = Mapping[str, Any]
Action = Mapping[str, Any]


def brief(observation: Observation, candidates: Sequence[Action]) -> dict[str, Any]:
    """Describe a visitor's situation and each of their options in plain words.

    Args:
        observation: Validated personal observation: own actor, known objects, visible
            visitors, recent memories and, when known, the current world time and whether
            the inn has closed.
        candidates: Actions the visitor could take next.

    Returns:
        `situation`, one paragraph, and `options`, a phrase per candidate ID that
        completes "How natural is it for them, right now, to ...".

    Raises:
        ValueError: A candidate's verb or target cannot be described.
    """
    parts = (_closing(observation), _stay(observation), _whereabouts(observation), _trigger(observation),
             _own_seat(observation),
             _needs(observation), _temperament(observation), _grievances(observation), _people(observation),
             _places(observation), _tables(observation), _recent(observation))
    return {"situation": " ".join(part for part in parts if part),
            "options": {action["id"]: _option(observation, action) for action in candidates}}


def in_use(observation: Observation, item: Mapping[str, Any]) -> bool:
    """Tell whether a known place is held by someone else, as far as the visitor can tell.

    Args:
        observation: The visitor's observation: own actor, seated company in sight and,
            when known, the current world time.
        item: Known object record, with `reserved_by` and, once observed, `last_seen`.

    Returns:
        True when someone is visibly sitting on it, or someone else held it at a sighting
        under 10 seconds old. A place seen busy longer ago is probably free again; without
        a clock the memory is trusted.
    """
    if item["id"] in {person.get("seat_id") for person in observation.get("visitors", [])}:
        return True
    if item.get("reserved_by") in (None, observation["actor"]["id"]):
        return False
    now, seen = observation.get("time"), item.get("last_seen")
    return now is None or seen is None or now - seen < 10.0


def _name(observation: Observation) -> str:
    return observation["actor"].get("name") or "The guest"


def _object(observation: Observation, object_id: Any) -> Mapping[str, Any] | None:
    return next((item for item in observation["objects"] if item["id"] == object_id), None)


def _label(item: Mapping[str, Any]) -> str:
    # The world names every object after its ID unless the map gives it a name.
    return item.get("name") or item["id"]


def _visitor(observation: Observation, visitor_id: Any) -> Mapping[str, Any] | None:
    return next((item for item in observation.get("visitors", []) if item["id"] == visitor_id), None)


def _steps(observation: Observation, item: Mapping[str, Any]) -> int:
    # Walking distance is approximated by grid steps to the nearest spot the place is used from.
    actor = observation["actor"]
    spots = item.get("interaction_spots") or [[item["x"], item["y"]]]
    return min(abs(x - actor["x"]) + abs(y - actor["y"]) for x, y in spots)


def _walk(steps: int) -> str:
    return f"{steps} step{'' if steps == 1 else 's'}"


def _place(item: Mapping[str, Any]) -> str:
    nouns = {"tap": "the tap", "toilet": "the WC", "darts": "the darts board", "door": "the front door",
             "fireplace": "the fireplace", "window": "a window", "bar": "the bar"}
    return nouns[item["kind"]] if item["kind"] in nouns else f"the {_label(item)}"


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{int(seconds)} seconds" if minutes == 0 else f"{minutes} minute{'' if minutes == 1 else 's'}"


def _closing(observation: Observation) -> str:
    if not observation.get("closed"):
        return ""
    return "The inn has closed for the night: the innkeeper is seeing every guest out, so it is time to go home."


def _stay(observation: Observation) -> str:
    visit = observation["actor"].get("visit", {})
    seconds, beers = visit.get("seconds", 0.0), visit.get("beers", 0)
    phase = ("has just arrived" if seconds < 60 else "is settling in" if seconds < 300
             else "has been here a good while" if seconds < 600 else "has had a long evening here")
    drunk = "no beer yet" if beers == 0 else "one beer" if beers == 1 else f"{beers} beers"
    return f"{_name(observation)} {phase} ({_duration(seconds)} in the inn) and has drunk {drunk} tonight."


def _whereabouts(observation: Observation) -> str:
    actor = observation["actor"]
    hands = "holding a full mug of ale" if actor["inventory"]["beer"] else "empty-handed"
    seat = _object(observation, actor.get("seat_id"))
    if seat:
        return f"They sit in their own seat, {_label(seat)}, {hands}."
    places = [item for item in observation["objects"] if item["kind"] != "chair"]
    near = min(places, key=lambda item: _steps(observation, item), default=None)
    return f"They are standing{f' near {_place(near)}' if near else ''}, {hands}."


def _trigger(observation: Observation) -> str:
    # What just caught their attention leads the choice it triggered; after 15 s it is old news.
    now = observation.get("time")
    noticed = [item for item in observation.get("memory", []) if item["type"] in ("interrupted", "alerted")]
    if now is None or not noticed or now - noticed[-1]["time"] >= 15:
        return ""
    return f"Just now: {noticed[-1]['message']}."


def _own_seat(observation: Observation) -> str:
    actor = observation["actor"]
    if actor.get("seat_id"):
        return ""
    own = _object(observation, actor.get("favorite_seat_id"))
    if own is None:
        return "They have not chosen a seat yet."
    taken = in_use(observation, own)
    return f"Their own seat tonight is {_label(own)}{', but someone else is sitting there now' if taken else ''}."


def _level(value: float) -> str:
    return "none" if value < 25 else "mild" if value < 50 else "strong" if value < 75 else "urgent"


def _needs(observation: Observation) -> str:
    needs = observation["actor"]["needs"]
    labels = {"thirst": "thirst", "fatigue": "tiredness", "bladder": "bladder",
              "social": "wish for company", "boredom": "boredom"}
    parts = [f"{label} {round(needs[need])} ({_level(needs[need])})" for need, label in labels.items() if need in needs]
    return f"Needs, from 0 satisfied to 100 urgent: {', '.join(parts)}."


def _temperament(observation: Observation) -> str:
    traits = observation["actor"].get("traits", {})
    words = {"patience": ("short-tempered", "patient"), "comfort": ("not fussy about seats", "loves a cosy seat"),
             "curiosity": ("incurious", "curious")}
    parts = []
    for trait, (low, high) in words.items():
        value = traits.get(trait, 0.5)
        word = f" ({low})" if value < 0.35 else f" ({high})" if value > 0.65 else ""
        parts.append(f"{trait} {value:.1f}{word}")
    return f"Temperament: {', '.join(parts)}."


def _grievances(observation: Observation) -> str:
    grievances = observation["actor"].get("visit", {}).get("grievances", [])
    return f"Grievances tonight: {'; '.join(grievances)}." if grievances else "Nobody has wronged them tonight."


def _shares_table(observation: Observation, visitor: Mapping[str, Any]) -> bool:
    seat = _object(observation, observation["actor"].get("seat_id"))
    return bool(seat and visitor.get("seat_id") and visitor.get("table_id") == seat.get("table_id"))


def _person(observation: Observation, visitor: Mapping[str, Any]) -> str:
    if visitor.get("seat_id"):
        table = _object(observation, visitor.get("table_id"))
        where = ("across the table from them" if _shares_table(observation, visitor)
                 else f"at the {_label(table)}" if table else "at a table")
        return f"{_label(visitor)} sits {where}{'' if visitor.get('available', True) else ', busy talking'}"
    activity = ACTIVITIES.get(visitor.get("doing"))
    return f"{_label(visitor)} is {activity.doing if activity and activity.doing else 'standing about'}"


def _people(observation: Observation) -> str:
    # `people` lists everyone in sight; bare observations only know seated company.
    if "people" not in observation:
        seated = [_person(observation, visitor) for visitor in observation.get("visitors", [])]
        return f"Seated in sight: {'; '.join(seated)}." if seated else "Nobody is seated in sight."
    people = [_person(observation, person) for person in observation["people"]]
    return f"In sight: {'; '.join(people)}." if people else "Nobody else is in sight; they are alone in the inn."


def _place_note(observation: Observation, item: Mapping[str, Any]) -> str:
    busy = in_use(observation, item)
    note = f"{_place(item)} {_walk(_steps(observation, item))} away"
    if item["kind"] == "tap":
        note += f" ({item.get('stock')} servings when last seen)" if item.get("stock") else " (it had run dry)"
    return note + (" (in use)" if busy else "")


def _places(observation: Observation) -> str:
    kinds = ("tap", "toilet", "darts", "fireplace", "door")
    notes = [_place_note(observation, item) for item in observation["objects"] if item["kind"] in kinds]
    windows = [item for item in observation["objects"] if item["kind"] == "window"]
    if windows:
        notes.append(_place_note(observation, min(windows, key=lambda item: _steps(observation, item))))
    missing = [noun for kind, noun in (("tap", "the tap"), ("toilet", "the WC")) if all(
        item["kind"] != kind for item in observation["objects"])]
    unknown = f" They have not found {' or '.join(missing)} yet." if missing else ""
    return (f"Places they know: {'; '.join(notes)}." if notes else "") + unknown


def _company(observation: Observation, table_id: Any) -> str:
    names = [_label(item) for item in observation.get("visitors", [])
             if item.get("seat_id") and item.get("table_id") == table_id]
    return f"{' and '.join(names)} sitting there" if names else "nobody else there"


def _table_note(observation: Observation, table: Mapping[str, Any]) -> str:
    chairs = [item for item in observation["objects"] if item.get("table_id") == table["id"]]
    actor_id = observation["actor"]["id"]
    free = sum(item.get("reserved_by") != actor_id and not in_use(observation, item) for item in chairs)
    comforts = " and ".join(table.get("comforts", [])) or "no special comfort"
    return (f"{_label(table)} (appeal {table.get('appeal', 0.0):.1f}, {comforts}; "
            f"{_company(observation, table['id'])}; {free} free chair{'' if free == 1 else 's'})")


def _tables(observation: Observation) -> str:
    tables = sorted((item for item in observation["objects"] if item["kind"] == "table"),
                    key=lambda item: -item.get("appeal", 0.0))
    return f"Tables: {'; '.join(_table_note(observation, item) for item in tables)}." if tables else ""


def _ago(seconds: float) -> str:
    return "just now" if seconds < 5 else f"{int(seconds)} s ago" if seconds < 60 else f"{int(seconds // 60)} min ago"


def _memory(memory: Mapping[str, Any]) -> str:
    if memory["type"] == "action_completed":
        activity = ACTIVITIES.get(memory["message"].rsplit(" ", 1)[-1])
        return activity.done if activity and activity.done else memory["message"]
    if memory["type"] == "action_failed":
        return f"was turned away ({memory['message']})"
    return memory["message"]


def _recent(observation: Observation) -> str:
    now = observation.get("time")
    # A finished chat is already remembered as the conversation itself.
    memories = [item for item in observation.get("memory", [])
                if item["type"] not in ("action_started", "interrupted", "alerted")
                and not (item["type"] == "action_completed" and item["message"].endswith(" talk"))][-5:]
    if now is None or not memories:
        return ""
    parts = [f"{_ago(now - item['time'])}, {_memory(item)}" for item in memories]
    return f"Recently: {'; '.join(parts)}."


def _option(observation: Observation, action: Action) -> str:
    builders: dict[str, Callable[[Observation, Action], str]] = {
        "take_beer": _pour, "drink": _drink, "rest": _rest, "seating": _seating, "sit": _sit, "talk": _talk,
        "play_darts": _darts, "watch": _watch, "use_toilet": _toilet, "inspect": _inspect, "wait": _wait,
        "leave": _leave}
    if action["verb"] not in builders:
        raise ValueError(f"Cannot describe the action verb {action['verb']!r}")
    return builders[action["verb"]](observation, action)


def _target(observation: Observation, action: Action) -> Mapping[str, Any]:
    target = _object(observation, action["target_id"])
    if target is None:
        raise ValueError(f"Cannot describe an unknown target {action['target_id']!r}")
    return target


def _pour(observation: Observation, action: Action) -> str:
    tap = _target(observation, action)
    return (f"walk {_walk(_steps(observation, tap))} to the tap and pour a mug of ale "
            f"({tap.get('stock')} servings when last seen)")


def _drink(observation: Observation, action: Action) -> str:
    if observation["actor"].get("seat_id"):
        return "sip the mug of ale they are holding, right here in their seat"
    return "drink the mug of ale they are holding where they stand, as there is no seat to be had"


def _rest(observation: Observation, action: Action) -> str:
    chair = _target(observation, action)
    return f"walk {_walk(_steps(observation, chair))} to {_label(chair)} and rest there"


def _seat_note(observation: Observation, chair: Mapping[str, Any]) -> str:
    table = _object(observation, chair.get("table_id"))
    comforts = " and ".join(chair.get("comforts", [])) or "no special comfort"
    return (f"{_label(table) if table else _label(chair)} (appeal {chair.get('appeal', 0.0):.1f}, {comforts}; "
            f"{_company(observation, chair.get('table_id'))}; {_walk(_steps(observation, chair))} away)")


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
    company = _company(observation, chair.get("table_id"))
    if chair["id"] == actor.get("seat_id"):
        return f"stay in their seat, {_label(chair)}, a while longer to rest, sip and chat ({company})"
    if chair["id"] == actor.get("favorite_seat_id"):
        return f"walk {_walk(_steps(observation, chair))} back to their own seat, {_label(chair)}, and sit down ({company})"
    return f"take the chair {_label(chair)}: {_seat_note(observation, chair)}"


def _talk(observation: Observation, action: Action) -> str:
    partner = _visitor(observation, action["target_id"])
    name = _label(partner) if partner else action["target_id"]
    return f"chat with {name}, who sits across the table from them"


def _darts(observation: Observation, action: Action) -> str:
    return f"walk {_walk(_steps(observation, _target(observation, action)))} to the darts board and play a round"


def _watch(observation: Observation, action: Action) -> str:
    view = _target(observation, action)
    sight = "the flames in the fireplace" if view["kind"] == "fireplace" else "the road outside a window"
    return f"walk {_walk(_steps(observation, view))} and watch {sight} for a while"


def _toilet(observation: Observation, action: Action) -> str:
    return f"walk {_walk(_steps(observation, _target(observation, action)))} to the WC"


def _inspect(observation: Observation, action: Action) -> str:
    if all(item["kind"] != "toilet" for item in observation["objects"]):
        return "look around the room for places they have not found yet, such as the WC"
    return "wander around to re-check places they already know (there is nothing new to find)"


def _wait(observation: Observation, action: Action) -> str:
    return "wait where they are and do nothing for a moment"


def _leave(observation: Observation, action: Action) -> str:
    return f"walk {_walk(_steps(observation, _target(observation, action)))} to the front door and go home for the night"
