"""Measures of a headless evening, read from what the lockstep runner logged."""

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict

from tavern.lockstep import Evening, Spell
from tavern.recording import KindCost, Record, cost_by_kind


class StuckTime(TypedDict):
    """How long one guest was stuck: the total of stuck spells, and the longest stall of any length."""

    seconds: float
    longest: float


class AttentionCounts(TypedDict):
    """How often guests turned to a sound: interrupted, alerted while busy, or merely glanced."""

    interrupts: int
    alerts: int
    glances: int


def attention_counts(evening: Evening) -> AttentionCounts:
    """Split the evening's turned heads into interrupts, alerts and glances.

    Args:
        evening: What the lockstep runner logged; every interrupt or alert also turned a head.

    Returns:
        Logged `interrupted` and `alerted` events, and the remaining turned heads as glances.

    Raises:
        ValueError: More interrupts and alerts were logged than heads turned.
    """
    interrupts = sum(event["type"] == "interrupted" for event in evening.events)
    alerts = sum(event["type"] == "alerted" for event in evening.events)
    if interrupts + alerts > evening.gazes:
        raise ValueError(f"{interrupts + alerts} interrupts and alerts but only {evening.gazes} turned heads")
    return {"interrupts": interrupts, "alerts": alerts, "glances": evening.gazes - interrupts - alerts}


class ConversationCounts(TypedDict):
    """How conversation scenes went: scenes started, lines spoken, guests who joined and who left."""

    scenes: int
    turns: int
    joins: int
    leaves: int


def conversation_counts(evening: Evening) -> ConversationCounts:
    """Count the evening's conversation scenes, turns, joins and leaves.

    Args:
        evening: What the lockstep runner logged.

    Returns:
        Logged `conversation_started`, `turn`, `joined_conversation` and `left_conversation` events.

    Raises:
        KeyError: An event has no type.
    """
    kinds = Counter(event["type"] for event in evening.events)
    return {"scenes": kinds["conversation_started"], "turns": kinds["turn"],
            "joins": kinds["joined_conversation"], "leaves": kinds["left_conversation"]}


class Metrics(TypedDict):
    """The measures of one evening; durations in game seconds, cost in USD per call kind."""

    game_seconds: float
    guests: int
    departures: int
    completed: dict[str, int]
    conversations: int
    quarrels: int
    decisions: dict[str, int]
    errors: int
    cost: dict[str, KindCost]
    stuck: dict[str, StuckTime]


def completed_activities(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Count completed activities per verb.

    Args:
        events: Event log; `action_completed` events read "<name> completed <verb>".

    Returns:
        Completions per verb, in verb order.

    Raises:
        ValueError: A completion message does not end in "completed <verb>".
    """
    verbs: Counter[str] = Counter()
    for event in events:
        if event["type"] != "action_completed":
            continue
        verb = re.fullmatch(r".* completed ([a-z_]+)", event["message"])
        if verb is None:
            raise ValueError(f"Cannot read the verb of a completed activity: {event['message']!r}")
        verbs[verb.group(1)] += 1
    return dict(sorted(verbs.items()))


def _occurrences(events: Sequence[Mapping[str, Any]], kind: str) -> int:
    # A chat or quarrel logs one event per participant, with the same time and message.
    return len({(event["time"], event["message"]) for event in events if event["type"] == kind})


def stuck_time(spells: Sequence[Spell], guests: Sequence[str], threshold: float) -> dict[str, StuckTime]:
    """Sum each guest's stuck time.

    A guest stalls while standing without an action and nobody talks to them, or while
    waiting on a blocked route (see `lockstep.run_evening`). A short stall is the normal pause
    between asking for a decision and acting on it (one model latency plus a tick), so only
    spells longer than the threshold count as stuck, and they count in full. `longest` is the
    longest stall of any length, to compare with limits such as "never idle for 30 seconds".

    Args:
        spells: Stalled spells of the evening.
        guests: Every guest, in report order.
        threshold: Seconds a stall may last before it counts as stuck.

    Returns:
        Stuck seconds and longest stall per guest, in guest order.

    Raises:
        ValueError: The threshold is negative, a spell ends before it starts, or a spell
            belongs to someone who is not a guest.
    """
    if not threshold >= 0:
        raise ValueError(f"Stuck threshold must be a nonnegative number of seconds, not {threshold!r}")
    stuck: dict[str, StuckTime] = {guest: {"seconds": 0.0, "longest": 0.0} for guest in guests}
    for spell in spells:
        length = spell["end"] - spell["start"]
        if spell["actor_id"] not in stuck or not length >= 0:
            raise ValueError(f"Impossible stalled spell: {spell!r}")
        guest = stuck[spell["actor_id"]]
        guest["seconds"] += length if length > threshold else 0.0
        guest["longest"] = max(guest["longest"], length)
    return stuck


def evening_metrics(evening: Evening, calls: Sequence[Record], input_usd_per_million: float,
                    stuck_threshold: float) -> Metrics:
    """Measure a finished headless evening.

    Args:
        evening: What the lockstep runner logged.
        calls: The evening's model calls: recorded live, or replayed.
        input_usd_per_million: USD tariff per million input tokens.
        stuck_threshold: Seconds a stall may last before it counts as stuck.

    Returns:
        Game time, guests and departures; completed activities per verb; conversations and
        quarrels; decision stages by source, and those whose model call failed (`errors`);
        cost per call kind; and stuck time per guest. Values are unrounded.

    Raises:
        ValueError: A completion is unreadable, the tariff or threshold is invalid, or a
            spell is impossible.
    """
    events = evening.events
    return {"game_seconds": evening.end_time, "guests": len(evening.guests),
            "departures": sum(event["type"] == "departure" for event in events),
            "completed": completed_activities(events),
            "conversations": _occurrences(events, "conversation"), "quarrels": _occurrences(events, "quarrel"),
            "decisions": dict(sorted(Counter(item["source"] for item in evening.choices).items())),
            "errors": sum(item["error"] is not None for item in evening.choices),
            "cost": cost_by_kind(calls, input_usd_per_million),
            "stuck": stuck_time(evening.spells, evening.guests, stuck_threshold)}
