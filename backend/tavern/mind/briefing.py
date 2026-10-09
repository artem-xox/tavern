"""Plain-language briefings: a visitor's situation and options, told from their own view."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.body.activities import ACTIVITIES, FAMILIES
from tavern.body.items import carried_words, held_words
from tavern.hall.room import SEAT_TABLES
from tavern.mind.feelings import feelings
from tavern.mind.goals import goal_words, serving
from tavern.mind.hall_view import (company_at, headcount, home_table_of, hosts_words, in_use, known_object, label_of,
                                   line_place, place_words, setting_words, steps_to, walk_words)
from tavern.mind.options import family_text, option_text
from tavern.mind.portrait import portrait
from tavern.social.invitations import invitation_note

Observation = Mapping[str, Any]
Action = Mapping[str, Any]


def brief(observation: Observation, candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Describe a visitor's situation and each of their options in plain words.

    Args:
        observation: Validated personal observation: own actor, known objects, visible
            visitors, recent memories and, when known, the current world time and whether
            the inn has closed.
        candidates: Actions the visitor could take next.

    Returns:
        `situation`, one paragraph, and `options`, a phrase per candidate ID that
        completes "How natural is it for them, right now, to ...". A family option (see
        `families.group_families`) is told as the family's wish with its first members.

    Raises:
        ValueError: A candidate's verb or target cannot be described.
    """
    parts = (_closing(observation), _stay(observation), _whereabouts(observation), _carrying(observation), _trigger(observation),
             _own_seat(observation),
             _needs(observation), _unwell(observation), _temperament(observation), portrait(observation["actor"]),
             feelings(observation), invitation_note(observation), _intention(observation), _promises(observation),
             _people(observation),
             _places(observation), _tables(observation), _recent(observation))
    return {"situation": " ".join(part for part in parts if part),
            "options": {action["id"]: _marked(observation, action, family_text(observation, action)
                                              if action["verb"] in FAMILIES else option_text(observation, action))
                        for action in candidates}}


def _name(observation: Observation) -> str:
    return observation["actor"].get("name") or "The guest"


def _duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{int(seconds)} seconds" if minutes == 0 else f"{minutes} minute{'' if minutes == 1 else 's'}"


def _closing(observation: Observation) -> str:
    if observation.get("closed"):
        return "The inn has closed for the night: the innkeeper is seeing every guest out, so it is time to go home."
    since = observation.get("called_closing")
    if since is None:
        return ""
    return (f"The barkeep called closing time {_duration(since)} ago: the inn is about to shut for the night, so "
            "guests finish what is in hand, say their goodbyes and head home.")


def _stay(observation: Observation) -> str:
    visit = observation["actor"].get("visit", {})
    seconds, beers = visit.get("seconds", 0.0), visit.get("beers", 0)
    phase = ("has just arrived" if seconds < 60 else "is settling in" if seconds < 300
             else "has been here a good while" if seconds < 600 else "has had a long evening here")
    drunk = "no beer yet" if beers == 0 else "one beer" if beers == 1 else f"{beers} beers"
    return f"{_name(observation)} {phase} ({_duration(seconds)} in the inn) and has drunk {drunk} tonight."


def _whereabouts(observation: Observation) -> str:
    actor = observation["actor"]
    held = held_words(actor["inventory"])
    hands = f"holding {held}" if held else "empty-handed"
    seat = known_object(observation, actor.get("seat_id"))
    if seat:
        return f"They sit in their own seat, {label_of(seat)}, {hands}."
    for item in observation["objects"]:
        ahead, joined = line_place(observation, item)
        if joined:
            where = ", next to go in" if not ahead else f" with {headcount(ahead)} waiting ahead of them"
            return f"They are standing in line for {place_words(item)}{where}, {hands}."
    places = [item for item in observation["objects"] if item["kind"] not in SEAT_TABLES]
    near = min(places, key=lambda item: steps_to(observation, item), default=None)
    return f"They are standing{f' near {place_words(near)}' if near else ''}, {hands}."


def _carrying(observation: Observation) -> str:
    carried = carried_words(observation["actor"]["inventory"])
    return f"They are also carrying {carried}." if carried else ""


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
    own = known_object(observation, actor.get("favorite_seat_id"))
    if own is None:
        return "They have not chosen a seat yet."
    taken = in_use(observation, own)
    return f"Their own seat tonight is {label_of(own)}{', but someone else is sitting there now' if taken else ''}."


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


def _shares_table(observation: Observation, visitor: Mapping[str, Any]) -> bool:
    seat = known_object(observation, observation["actor"].get("seat_id"))
    return bool(seat and visitor.get("seat_id") and visitor.get("table_id") == seat.get("table_id"))


def _person(observation: Observation, visitor: Mapping[str, Any]) -> str:
    if visitor.get("seat_id"):
        table = known_object(observation, visitor.get("table_id"))
        where = ("across the table from them" if _shares_table(observation, visitor)
                 else f"at the {label_of(table)}" if table else "at a table")
        # Someone unavailable who is not talking or asleep is visibly in a hurry (see `scenes.pressed`).
        busy = (", asleep" if visitor.get("asleep") else ", busy talking" if visitor.get("conversation")
                else "" if visitor.get("available", True) else ", in a hurry")
        return f"{label_of(visitor)} sits {where}{busy}{_pale(visitor)}"
    doing = visitor.get("doing")
    activity = ACTIVITIES.get(doing) if isinstance(doing, str) else None
    if visitor.get("post"):
        return f"{label_of(visitor)}, the barkeep, is {activity.doing if activity and activity.doing else 'tending the bar'}"
    return f"{label_of(visitor)} is {activity.doing if activity and activity.doing else 'standing about'}{_pale(visitor)}"


def _pale(visitor: Mapping[str, Any]) -> str:
    # Anyone can see who came in with a fever (`tavern.body.ailment`).
    return ", looking pale and feverish" if visitor.get("ailing") else ""


def _unwell(observation: Observation) -> str:
    if not observation["actor"].get("ailing"):
        return ""
    return "They feel feverish and weak tonight; a healer's remedy would help."


def _promises(observation: Observation) -> str:
    # What the guest promised in talk and has not yet kept: the game will note whether they did.
    names = [label_of(person) for item in observation.get("promises", [])
             for person in [*observation.get("visitors", []), *observation.get("people", [])] if person["id"] == item["target"]]
    return "".join(f"They promised {name} to come and sit with them, and have not yet. " for name in dict.fromkeys(names)).strip()


def _marked(observation: Observation, action: Mapping[str, Any], text: str) -> str:
    # An option that brings the guest closer to their goal says so, so a model need not match prose.
    return f"{text} (this serves the goal they set themselves)" if serving(observation, action) else text


def _intention(observation: Observation) -> str:
    # The mind's latest intention (see `intentions.py`); Jev weighs the options against it.
    intention = observation["actor"].get("intention")
    if not intention:
        return ""
    now = observation.get("time")
    when = "" if now is None else f"decided {_ago(now - intention['written_at'])}, "
    goal = intention.get("goal")
    aim = "" if goal is None or goal["status"] != "active" else f" Their goal: {goal_words(goal, _goal_person(observation, goal))}."
    return (f"Their own reading of things: \"{intention['thought']}\" Their intention: "
            f"{intention['intention'].rstrip('.')} ({when}after: {intention['trigger']['text']}).{aim}")


def _goal_person(observation: Observation, goal: Mapping[str, Any]) -> str | None:
    # The goal's person as the guest calls them, when they are in sight.
    person = next((item for item in [*observation.get("visitors", []), *observation.get("people", [])]
                   if item["id"] == goal["target"]), None)
    return label_of(person) if person else "that guest"



def _people(observation: Observation) -> str:
    # `people` lists everyone in sight; bare observations only know seated company.
    if "people" not in observation:
        seated = [_person(observation, visitor) for visitor in observation.get("visitors", [])]
        return f"Seated in sight: {'; '.join(seated)}." if seated else "Nobody is seated in sight."
    people = [_person(observation, person) for person in observation["people"]]
    return f"In sight: {'; '.join(people)}." if people else "Nobody else is in sight; they are alone in the inn."


def _place_note(observation: Observation, item: Mapping[str, Any]) -> str:
    busy = in_use(observation, item)
    note = f"{place_words(item)} {walk_words(steps_to(observation, item))} away"
    if item["kind"] == "tap":
        note += f" ({item.get('stock')} servings when last seen)" if item.get("stock") else " (it had run dry)"
    waiting = line_place(observation, item)[0]
    return note + (" (in use)" if busy else "") + (f" ({headcount(waiting)} waiting in line)" if waiting else "")


def _places(observation: Observation) -> str:
    kinds = ("tap", "toilet", "darts", "fireplace", "door")
    notes = [_place_note(observation, item) for item in observation["objects"] if item["kind"] in kinds]
    windows = [item for item in observation["objects"] if item["kind"] == "window"]
    if windows:
        notes.append(_place_note(observation, min(windows, key=lambda item: steps_to(observation, item))))
    missing = [noun for kind, noun in (("tap", "the tap"), ("toilet", "the WC")) if all(
        item["kind"] != kind for item in observation["objects"])]
    unknown = f" They have not found {' or '.join(missing)} yet." if missing else ""
    return (f"Places they know: {'; '.join(notes)}." if notes else "") + unknown


def _table_note(observation: Observation, table: Mapping[str, Any]) -> str:
    chairs = [item for item in observation["objects"] if item.get("table_id") == table["id"]]
    actor_id = observation["actor"]["id"]
    free = sum(item.get("reserved_by") != actor_id and not in_use(observation, item) for item in chairs)
    details = [setting_words(table), "their own table" if home_table_of(observation) == table["id"] else "",
               hosts_words(observation, table["id"]), company_at(observation, table["id"]),
               f"{free} free chair{'' if free == 1 else 's'}"]
    return f"{label_of(table)} ({'; '.join(part for part in details if part)})"


def _tables(observation: Observation) -> str:
    # Nearest first: where a table stands matters more to a guest than how it is rated.
    tables = sorted((item for item in observation["objects"] if item["kind"] == "table"),
                    key=lambda item: (steps_to(observation, item), item["id"]))
    held = any(item.get("hosts") for item in tables)
    manners = (" A table someone has made theirs is theirs: sitting down there without being asked may upset them. "
               "Walk over and talk to them, or wait to be asked.") if held else ""
    return f"Tables: {'; '.join(_table_note(observation, item) for item in tables)}.{manners}" if tables else ""


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

