"""How a visitor reads the hall in words: what is in use, who waits ahead, how far things are, who sits where."""

from collections.abc import Mapping
from typing import Any

Observation = Mapping[str, Any]


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


def line_place(observation: Observation, item: Mapping[str, Any]) -> tuple[int, bool]:
    """Tell where the visitor stands in a known place's line, as last seen.

    Args:
        observation: The visitor's observation.
        item: Known object record; one without a line has nobody in it.

    Returns:
        How many people wait ahead of the visitor, and whether the visitor stands in that line;
        for someone not in it, everyone waiting is ahead. Like a busy place (see `in_use`), a
        line seen 10 seconds ago or more has probably cleared; without a clock it is trusted.
    """
    waiting = [entry["actor_id"] for entry in item.get("queue", [])]
    me = observation["actor"]["id"]
    if me in waiting:
        return waiting.index(me), True
    now, seen = observation.get("time"), item.get("last_seen")
    return (0 if now is not None and seen is not None and now - seen >= 10.0 else len(waiting)), False


def headcount(count: int) -> str:
    """Say how many people there are, in words up to five.

    Args:
        count: Number of people, nonnegative.

    Returns:
        "nobody", "one person", ... or "7 people".
    """
    words = ("nobody", "one person", "two people", "three people", "four people", "five people")
    return words[count] if count < len(words) else f"{count} people"


def known_object(observation: Observation, object_id: Any) -> Mapping[str, Any] | None:
    """Find a place the visitor knows by ID.

    Args:
        observation: The visitor's observation.
        object_id: ID to look for; None finds nothing.

    Returns:
        The known record, or None.
    """
    return next((item for item in observation["objects"] if item["id"] == object_id), None)


def label_of(item: Mapping[str, Any]) -> str:
    """Name a place or person.

    Args:
        item: Object or visitor record. The world names every object after its ID unless the map
            gives it a name.

    Returns:
        Its name, else its ID.
    """
    return item.get("name") or item["id"]


def visible_visitor(observation: Observation, visitor_id: Any) -> Mapping[str, Any] | None:
    """Find a seated visitor in sight by ID.

    Args:
        observation: The visitor's observation.
        visitor_id: ID to look for.

    Returns:
        Their public record, or None.
    """
    return next((item for item in observation.get("visitors", []) if item["id"] == visitor_id), None)


def steps_to(observation: Observation, item: Mapping[str, Any]) -> int:
    """Approximate the walk to a place as grid steps to the nearest spot it is used from.

    Args:
        observation: The visitor's observation.
        item: Known object record.

    Returns:
        Manhattan distance in cells, ignoring obstacles.
    """
    actor = observation["actor"]
    spots = item.get("interaction_spots") or [[item["x"], item["y"]]]
    return min(abs(x - actor["x"]) + abs(y - actor["y"]) for x, y in spots)


def walk_words(steps: int) -> str:
    """Say a walking distance.

    Args:
        steps: Number of steps.

    Returns:
        "1 step" or "N steps".
    """
    return f"{steps} step{'' if steps == 1 else 's'}"


def place_words(item: Mapping[str, Any]) -> str:
    """Name a place the way a guest would say it.

    Args:
        item: Known object record.

    Returns:
        "the tap", "the WC", ... or "the <label>" for other kinds.
    """
    nouns = {"tap": "the tap", "toilet": "the WC", "darts": "the darts board", "door": "the front door",
             "fireplace": "the fireplace", "window": "a window", "bar": "the bar"}
    return nouns[item["kind"]] if item["kind"] in nouns else f"the {label_of(item)}"


def company_at(observation: Observation, table_id: Any) -> str:
    """Say who sits at a table, as far as the visitor can see.

    Args:
        observation: The visitor's observation.
        table_id: Table to look at.

    Returns:
        "Ann and Bea sitting there", or "nobody else there".
    """
    names = [label_of(item) for item in observation.get("visitors", [])
             if item.get("seat_id") and item.get("table_id") == table_id]
    return f"{' and '.join(names)} sitting there" if names else "nobody else there"
