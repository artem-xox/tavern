"""How lively a talk between two guests was: repeats, echoes, new ground, variety of acts and staying on their brief."""

from collections.abc import Mapping, Sequence
import re
from typing import Any, NamedTuple, TypedDict


class DialogueMetrics(TypedDict):
    """The talk between two guests, from the event log.

    Attributes:
        lines: Lines either said to the other.
        balance: The quieter one's share of those lines (0.5 is even; 0 when one never spoke).
        repeated: Share of lines alike (`ALIKE`) to a line the same speaker said earlier in the pair's talk.
        echo: Mean share of a line's words taken from the other's line just before it.
        novelty: Share of lines at least half of whose words are new to the talk.
        variety: Distinct speech acts over lines.
        on_brief: Share of lines naming one of their speaker's brief words.
        fallbacks: Lines for either that failed and were replaced by a scripted one.
    """

    lines: int
    balance: float
    repeated: float
    echo: float
    novelty: float
    variety: float
    on_brief: float
    fallbacks: int


class _Line(NamedTuple):
    speaker: str
    act: str
    text: str
    words: frozenset[str]


# As `repetition.ALIKE`: shared words over all words at which two lines say the same thing.
ALIKE = 0.7
# As in `repetition`: lowercase runs of three letters or more, so a, to and of make no two lines alike.
_WORD = re.compile(r"[a-z][a-z']{2,}")
_TURN = re.compile(r"(.*?) to (.*?) \(([a-z_]+)\): (.*)", re.DOTALL)


def dialogue_metrics(events: Sequence[Mapping[str, Any]], pair: Mapping[str, str],
                     brief: Mapping[str, Sequence[str]]) -> DialogueMetrics:
    """Measure how the two guests of a pair talked to each other.

    Args:
        events: The event log; `turn` events are worded "<speaker> to <listener> (<act>): <line>", and
            `turn_failed` ones "A line for <speaker> failed …".
        pair: The two guests, ID to name as the log writes it.
        brief: Words (lowercase) a guest's lines should touch, by ID; a word counts inside a longer one.

    Returns:
        The metrics; all zero when the two said nothing to each other.

    Raises:
        ValueError: The pair is not two guests, or a turn is worded otherwise.
    """
    if len(pair) != 2:
        raise ValueError(f"A pair is two guests, not {sorted(pair)!r}")
    lines = _pair_lines(events, pair)
    fallbacks = sum(event["type"] == "turn_failed" and any(
        event["message"].startswith(f"A line for {name} failed") for name in pair.values()) for event in events)
    if not lines:
        return DialogueMetrics(lines=0, balance=0.0, repeated=0.0, echo=0.0, novelty=0.0, variety=0.0,
                               on_brief=0.0, fallbacks=fallbacks)
    count = len(lines)
    return DialogueMetrics(
        lines=count, balance=min(sum(line.speaker == key for line in lines) for key in pair) / count,
        repeated=_repeats(lines) / count, echo=_echo(lines), novelty=_novel(lines) / count,
        variety=len({line.act for line in lines}) / count,
        on_brief=sum(any(word in line.text.lower() for word in brief.get(line.speaker, ())) for line in lines) / count,
        fallbacks=fallbacks)


def talk_window(events: Sequence[Mapping[str, Any]], pair: Mapping[str, str],
                seconds: float) -> list[Mapping[str, Any]]:
    """Cut the event log to a stretch of the pair's talk.

    Args:
        events: The event log, in time order.
        pair: The two guests, ID to name as the log writes it.
        seconds: How long the stretch lasts, in game seconds.

    Returns:
        Events from the first line one of the pair said to the other through `seconds` later, ends included;
        none when they never spoke to each other.

    Raises:
        ValueError: A turn is worded otherwise.
    """
    first = next((event["time"] for event in events if event["type"] == "turn" and _pair_lines([event], pair)), None)
    return [] if first is None else [event for event in events if first <= event["time"] <= first + seconds]


def pair_transcript(events: Sequence[Mapping[str, Any]], pair: Mapping[str, str]) -> list[str]:
    """Write out what the two said to each other, for a reader.

    Args:
        events: The event log.
        pair: The two guests, ID to name as the log writes it.

    Returns:
        "<name> (<act>): <line>" for each line one said to the other, in order.

    Raises:
        ValueError: A turn is worded otherwise.
    """
    return [f"{pair[line.speaker]} ({line.act}): {line.text}" for line in _pair_lines(events, pair)]


def _pair_lines(events: Sequence[Mapping[str, Any]], pair: Mapping[str, str]) -> list[_Line]:
    # Only lines one of the pair said to the other: talk with the barkeep or to the whole table does not count.
    found = []
    for event in events:
        if event["type"] != "turn" or event["actor_id"] not in pair:
            continue
        match = _TURN.fullmatch(event["message"])
        if match is None:
            raise ValueError(f"Cannot read the turn in {event['message']!r}")
        other = next(name for key, name in pair.items() if key != event["actor_id"])
        if match.group(2) == other:
            found.append(_Line(event["actor_id"], match.group(3), match.group(4),
                               frozenset(_WORD.findall(match.group(4).lower()))))
    return found


def _alike(first: frozenset[str], second: frozenset[str]) -> float:
    # Two wordless lines (a grunt) are never alike: there is nothing to repeat.
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def _repeats(lines: Sequence[_Line]) -> int:
    return sum(any(earlier.speaker == line.speaker and _alike(earlier.words, line.words) >= ALIKE
                   for earlier in lines[:index]) for index, line in enumerate(lines))


def _echo(lines: Sequence[_Line]) -> float:
    # Each answer to the other's last line, with words to measure; none gives 0.
    shares = [len(line.words & previous.words) / len(line.words)
              for previous, line in zip(lines, lines[1:]) if previous.speaker != line.speaker and line.words]
    return sum(shares) / len(shares) if shares else 0.0


def _novel(lines: Sequence[_Line]) -> int:
    # A wordless line repeats nothing, so it counts as new.
    seen: set[str] = set()
    count = 0
    for line in lines:
        count += len(line.words - seen) * 2 >= len(line.words)
        seen |= line.words
    return count


def missed_thresholds(values: Mapping[str, float], thresholds: Mapping[str, Mapping[str, float]]) -> list[str]:
    """Name the measured values outside their bounds.

    Args:
        values: Measured values by name.
        thresholds: Bounds by name, each `{"min": x}`, `{"max": y}` or both, ends included. A bound for a
            value that was not measured (no talk to judge) is skipped: that failure shows as `lines`.

    Returns:
        "<name> <value> < <min>" or "<name> <value> > <max>" per value out of bounds, in threshold order.

    Raises:
        ValueError: A threshold has no bound or an unknown one.
    """
    missed = []
    for name, bounds in thresholds.items():
        if not bounds or set(bounds) - {"min", "max"}:
            raise ValueError(f"A threshold has a min, a max or both, not {dict(bounds)!r}")
        if name not in values:
            continue
        value = values[name]
        if "min" in bounds and value < bounds["min"]:
            missed.append(f"{name} {value:g} < {bounds['min']:g}")
        if "max" in bounds and value > bounds["max"]:
            missed.append(f"{name} {value:g} > {bounds['max']:g}")
    return missed
