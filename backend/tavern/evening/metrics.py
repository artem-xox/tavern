"""Measures of a headless evening, read from what the lockstep runner logged."""

from collections import Counter
from collections.abc import Mapping, Sequence
import math
import re
from typing import Any, TypedDict

from tavern.evening.lockstep import Evening, Spell
from tavern.evening.recording import KindCost, Record, Tariff, cost_by_kind
from tavern.social.facts import inspected


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


class IntentionCounts(TypedDict):
    """How guests' intentions went: written and kept, or failed (the old one stayed)."""

    written: int
    failed: int


def intention_counts(evening: Evening) -> IntentionCounts:
    """Count the evening's written and failed intentions.

    Args:
        evening: What the lockstep runner logged.

    Returns:
        Logged `intention` and `intention_failed` events.

    Raises:
        KeyError: An event has no type.
    """
    kinds = Counter(event["type"] for event in evening.events)
    return {"written": kinds["intention"], "failed": kinds["intention_failed"]}


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
                    stuck_threshold: float, tariffs: Mapping[str, Tariff] | None = None) -> Metrics:
    """Measure a finished headless evening.

    Args:
        evening: What the lockstep runner logged.
        calls: The evening's model calls: recorded live, or replayed.
        input_usd_per_million: USD tariff per million input tokens of kinds without a tariff (Jev's).
        stuck_threshold: Seconds a stall may last before it counts as stuck.
        tariffs: Full tariffs of call kinds priced otherwise than Jev, such as Claude's `turn` and
            `intention`.

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
            "cost": cost_by_kind(calls, input_usd_per_million, tariffs),
            "stuck": stuck_time(evening.spells, evening.guests, stuck_threshold)}


class NewsReach(TypedDict):
    """How far one news item travelled: the names of its `holders` (first holders included), the most
    `max_hops` any copy is from the original holders, and the path (see `facts.inspected`) of the first
    copy that arrived at two hops, or None."""

    holders: list[str]
    max_hops: int
    first_two_hop_path: list[str] | None


def news_metrics(world: Mapping[str, Any]) -> dict[str, NewsReach]:
    """Measure how each news item of the evening spread, from the world as it ended.

    Args:
        world: Final world of an evening; its news and every guest's copies, the departed included.

    Returns:
        Per news ID, in the scenario's order, its reach. Holders are listed present guests first, then
        the departed; of several copies that reached two hops, the one heard earliest wins, and a tie
        goes to the earlier in that order. An item nobody holds has no holders and zero hops.
    """
    guests = [*world["actors"], *world["departed"]]
    shown = {guest["id"]: {copy["id"]: copy for copy in inspected(world, guest)} for guest in guests}
    reach: dict[str, NewsReach] = {}
    for news in world["news"]:
        holders = [guest for guest in guests if news["id"] in shown[guest["id"]]]
        two_hops = sorted((guest for guest in holders if shown[guest["id"]][news["id"]]["hops"] == 2),
                          key=lambda guest: guest["knowledge"]["facts"][news["id"]]["heard_at"])
        reach[news["id"]] = {
            "holders": [guest["name"] for guest in holders],
            "max_hops": max((shown[guest["id"]][news["id"]]["hops"] for guest in holders), default=0),
            "first_two_hop_path": shown[two_hops[0]["id"]][news["id"]]["chain"] if two_hops else None}
    return reach


class WriterStats(TypedDict):
    """How the turn writer did over an evening.

    `turns` lines were spoken, `fallbacks` of them scripted after a failed or rejected line;
    `calls` model calls of the writer's kind, `failures` of them failed. Latency is wall-clock
    seconds per call (nearest rank), `cache_hit_rate` the share of prompt tokens read from the
    cache, and cost is in USD; None where there is nothing to measure.
    """

    turns: int
    fallbacks: int
    calls: int
    failures: int
    latency_p50: float | None
    latency_p95: float | None
    cache_hit_rate: float | None
    usd: float
    usd_per_turn: float | None


def writer_stats(evening: Evening, calls: Sequence[Record], kind: str, tariff: Tariff) -> WriterStats:
    """Measure the model turn writer over a finished evening.

    Args:
        evening: What the lockstep runner logged; `turn` and `turn_failed` events count.
        calls: The evening's model calls; only those of `kind` are measured.
        kind: Call kind of the writer, e.g. `turn`.
        tariff: Its prices.

    Returns:
        Unrounded measures. The cache hit rate counts calls with reported usage: cache reads
        over all prompt tokens (uncached input, cache reads and cache writes).

    Raises:
        ValueError: A price is negative or not finite.
    """
    mine = [record for record in calls if record["kind"] == kind]
    cost: Mapping[str, Any] = cost_by_kind(mine, 0.0, {kind: tariff}).get(kind, {})
    read = cost.get("cache_read_input_tokens", 0)
    prompt = cost.get("input_tokens", 0) + read + cost.get("cache_creation_input_tokens", 0)
    turns, usd = sum(event["type"] == "turn" for event in evening.events), cost.get("usd", 0.0)
    latencies = [record["latency"] for record in mine]
    return {"turns": turns, "fallbacks": sum(event["type"] == "turn_failed" for event in evening.events),
            "calls": len(mine), "failures": sum(record["error"] is not None for record in mine),
            "latency_p50": _nearest_rank(latencies, 0.5), "latency_p95": _nearest_rank(latencies, 0.95),
            "cache_hit_rate": read / prompt if prompt else None, "usd": usd,
            "usd_per_turn": usd / turns if turns else None}


def unspoken_calls(evening: Evening, calls: Sequence[Record], kind: str) -> int:
    """Count the writer's calls whose line no scene spoke: it ended, or its company changed, first.

    Args:
        evening: What the lockstep runner logged; `turn` events are the lines spoken.
        calls: The evening's model calls; only those of `kind` count.
        kind: Call kind of the writer, e.g. `turn`.

    Returns:
        Calls beyond the lines spoken, never below 0: a scripted line spoken without a call (a late
        answer, an unclaimed turn) hides a wasted call, so this is a floor.
    """
    spoken = sum(event["type"] == "turn" for event in evening.events)
    return max(0, sum(record["kind"] == kind for record in calls) - spoken)


def _nearest_rank(values: Sequence[float], share: float) -> float | None:
    # The smallest value with at least `share` of the values at or below it; None for none.
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)] if ordered else None


class DiceCounts(TypedDict):
    """How the dice went: games played to a result, games broken off or given up (one `dice_abandoned`
    event for the guest left sitting), guests who watched a game to its end, and games won per guest ID."""

    games: int
    abandoned: int
    onlookers: int
    wins: dict[str, int]


def dice_metrics(events: Sequence[Mapping[str, Any]]) -> DiceCounts:
    """Count the dice played in an evening.

    Args:
        events: The complete event log: `dice_won` (one per game, logged for the winner),
            `dice_abandoned` and `dice_watched`.

    Returns:
        The counts, with wins per guest ID in order of the first win.
    """
    wins = Counter(event["actor_id"] for event in events if event["type"] == "dice_won")
    return {"games": sum(wins.values()), "abandoned": sum(event["type"] == "dice_abandoned" for event in events),
            "onlookers": sum(event["type"] == "dice_watched" for event in events), "wins": dict(wins)}


class SleepCounts(TypedDict):
    """How the sleep went: naps begun and per guest, naps that ran their course (`woke_up`), naps cut short by
    a loud sound (`woken`), each departed guest's tiredness as they left, and how many chose to go home tired."""

    naps: int
    napped: dict[str, int]
    slept_out: int
    woken: int
    fatigue_at_departure: dict[str, float]
    tired_home: int


def sleep_metrics(events: Sequence[Mapping[str, Any]], departed: Sequence[Mapping[str, Any]],
                  closes_at: float | None, tired: float = 60.0) -> SleepCounts:
    """Count the sleep in an evening.

    Args:
        events: The complete event log: `dozed_off`, `woke_up` and `woken`.
        departed: The guests who went home, with their `needs` as they left and `visit.left_at`.
        closes_at: Closing time; a guest who left at or after it was sent home, so did not choose to go tired.
            None for an evening that never closes.
        tired: Tiredness (0–100) from which a guest counts as having gone home tired; the sleep candidate's
            threshold (`tavern.mind.agents.SLEEPY`) by default.

    Returns:
        The counts, with naps per guest ID in order of the first nap.
    """
    napped = Counter(event["actor_id"] for event in events if event["type"] == "dozed_off")
    fatigue = {guest["id"]: guest["needs"]["fatigue"] for guest in departed}
    return {"naps": sum(napped.values()), "napped": dict(napped),
            "slept_out": sum(event["type"] == "woke_up" for event in events),
            "woken": sum(event["type"] == "woken" for event in events), "fatigue_at_departure": fatigue,
            "tired_home": sum(guest["needs"]["fatigue"] >= tired
                              and (closes_at is None or guest["visit"]["left_at"] < closes_at) for guest in departed)}


class BarCounts(TypedDict):
    """How the bar went: mugs the barkeep poured, conversations he opened, lines he spoke and news items
    he told."""

    served: int
    opened: int
    lines: int
    news_told: int


def bar_metrics(events: Sequence[Mapping[str, Any]], staff: Sequence[str]) -> BarCounts:
    """Count what the barkeep did in an evening.

    Args:
        events: The complete event log: `served`, `conversation_started`, `turn` and `news_told`.
        staff: IDs of the staff in the hall at the end (`tavern.hall.staff.guests` leaves them out); an
            event counts for the bar when its actor is one of them.

    Returns:
        The counts. A conversation a guest opened with the barkeep is not one he opened.
    """
    done = Counter(event["type"] for event in events if event["actor_id"] in staff)
    return {"served": done["served"], "opened": done["conversation_started"], "lines": done["turn"],
            "news_told": done["news_told"]}
