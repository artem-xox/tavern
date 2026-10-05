"""Repetition in an evening: intentions a guest's mind restates, and lines a speaker says again."""

from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict


class RepetitionCounts(TypedDict):
    """How often guests repeated themselves: intentions that restated the guest's previous one, and
    lines a speaker had already said tonight."""

    restated: int
    repeated: int


# How alike two texts must be to count as the same. In the live evenings recorded by 2026-10-04,
# every intention scoring 0.7 or more kept the previous plan almost word for word. The same plan in
# other words scored 0.57-0.63 or less, as did new plans, so the counts are a lower bound.
ALIKE = 0.7
# Words are lowercase letter runs of three letters or more: shorter ones (a, an, at, to, of) are in
# nearly every sentence and would make unrelated ones look alike.
_WORD = re.compile(r"[a-z][a-z']{2,}")
_INTENDS = re.compile(r".* Intends: (.*?) \(after: .*\)", re.DOTALL)
_LINE = re.compile(r".*? \([a-z_]+\): (.*)", re.DOTALL)


def repetition_counts(events: Sequence[Mapping[str, Any]], threshold: float) -> RepetitionCounts:
    """Count restated intentions and repeated lines.

    Args:
        events: The complete event log: `intention` events, worded "<name> thinks: … Intends:
            <intention> (after: …)", and `turn` events, worded "<speaker> to <listener> (<act>): <line>".
        threshold: How alike two texts must be to count as the same: shared words over all their
            words, in (0, 1].

    Returns:
        Intentions at least `threshold` alike to the same guest's previous one, and lines at least
        `threshold` alike to a line the same speaker said earlier tonight.

    Raises:
        ValueError: The threshold is outside (0, 1], or an intention or a line is worded otherwise.
    """
    if not 0 < threshold <= 1:
        raise ValueError(f"Likeness threshold must be in (0, 1], not {threshold!r}")
    return {"restated": _restated(events, threshold), "repeated": _repeated(events, threshold)}


def _restated(events: Sequence[Mapping[str, Any]], threshold: float) -> int:
    # Only the previous intention counts: a plan that comes back after another is a new decision,
    # as a second beer is.
    previous: dict[str, set[str]] = {}
    count = 0
    for event in events:
        if event["type"] == "intention":
            words = _words(_INTENDS, event)
            count += event["actor_id"] in previous and _alike(previous[event["actor_id"]], words) >= threshold
            previous[event["actor_id"]] = words
    return count


def _repeated(events: Sequence[Mapping[str, Any]], threshold: float) -> int:
    # Any earlier line counts: a listener notices a line heard before, however long ago.
    said: dict[str, list[set[str]]] = {}
    count = 0
    for event in events:
        if event["type"] == "turn":
            words, earlier = _words(_LINE, event), said.setdefault(event["actor_id"], [])
            count += any(_alike(item, words) >= threshold for item in earlier)
            earlier.append(words)
    return count


def _words(pattern: re.Pattern[str], event: Mapping[str, Any]) -> set[str]:
    found = pattern.fullmatch(event["message"])
    if found is None:
        raise ValueError(f"Cannot read the {event['type']} in {event['message']!r}")
    return set(_WORD.findall(found.group(1).lower()))


def _alike(first: set[str], second: set[str]) -> float:
    # Texts without a word of three letters are too short to judge, so they are never alike.
    words = first | second
    return len(first & second) / len(words) if words else 0.0
