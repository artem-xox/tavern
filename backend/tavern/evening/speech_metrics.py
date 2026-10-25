"""Speeches in an evening: how many were given, by whom, and how the room took them."""

from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict

_REACTION = re.compile(r"(\d+) admired it, (\d+) groaned$")


class SpeechCounts(TypedDict):
    """Speeches given, who gave them (by ID, in order), and the listeners who admired or groaned."""

    speeches: int
    speakers: list[str]
    admired: int
    groaned: int


def speech_counts(events: Sequence[Mapping[str, Any]]) -> SpeechCounts:
    """Count the evening's speeches and how they were taken.

    Args:
        events: The complete event log: `gave_speech` events and each speech's `speech_reaction` summary
            (`speeches.give_speech`).

    Returns:
        Speeches, their speakers once each in the order they first spoke, and the listeners who admired or groaned.

    Raises:
        ValueError: A `speech_reaction` message is not in the words `give_speech` logs.
        KeyError: An event has no type.
    """
    given = [event for event in events if event["type"] == "gave_speech"]
    admired = groaned = 0
    for event in events:
        if event["type"] != "speech_reaction":
            continue
        match = _REACTION.search(event["message"])
        if match is None:
            raise ValueError(f"A speech taken in words give_speech does not log: {event['message']!r}")
        admired, groaned = admired + int(match[1]), groaned + int(match[2])
    return {"speeches": len(given), "speakers": list(dict.fromkeys(event["actor_id"] for event in given)),
            "admired": admired, "groaned": groaned}



class StageCounts(TypedDict):
    """Numbers given from the stage by kind (only kinds given), and the heckles and comebacks that answered them."""

    numbers: dict[str, int]
    heckles: int
    comebacks: int


def stage_counts(events: Sequence[Mapping[str, Any]]) -> StageCounts:
    """Count the evening's stage numbers by kind, and the heckles and comebacks.

    Args:
        events: The complete event log: `gave_speech` events with their `number`, `heckled` and `heckle_answered`.

    Returns:
        Numbers by kind, in the order each kind was first given; heckles; comebacks. A `gave_speech` logged before
        numbers had kinds counts as a pitch: every speech then addressed the room with the speaker's own cause.

    Raises:
        KeyError: An event has no type.
    """
    numbers: dict[str, int] = {}
    for event in events:
        if event["type"] == "gave_speech":
            kind = event.get("number", "pitch")
            numbers[kind] = numbers.get(kind, 0) + 1
    return {"numbers": numbers, "heckles": sum(1 for event in events if event["type"] == "heckled"),
            "comebacks": sum(1 for event in events if event["type"] == "heckle_answered")}
