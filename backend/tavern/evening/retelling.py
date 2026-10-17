"""Retelling: an evening laid out for a storyteller model as numbered lines, and its cited chapters checked."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.evening.story_score import StoryScore, story_moments
from tavern.mind.questions import Ask, Question

MAX_LINES = 60  # Event lines in one question: the evening's story, not its whole log.
NEAR = 3  # Events on each side of a moment whose talk goes with it.
MAX_CHAPTERS = 5
MAX_CHAPTER_TEXT = 400  # Characters of one chapter: a few sentences.
MAX_TOKENS = 1200  # Bounds the answer; emoji take several tokens each.
# Besides the moments, these logged events give the storyteller the colour of the evening.
_COLOUR = ("arrival", "departure", "turn", "news_told", "insulted", "last_call")
_STYLE = """You are the storyteller of the Story Tavern. At closing time you retell the evening to the people who \
missed it, from a numbered log of what happened.

Write a catchy title and three to five short chapters of one to three sentences each. Be funny and warm, like a \
friend telling a tale at the bar. Open with a hook, build to the best moment, end on a punchline. Use emoji \
generously, one or two per sentence, so the story is fun to scan (🍺 🎲 💤 😡 👊 🎁 🚪).

Tell only what the log says: use the names in it, invent no events, and invent no guests. Quote a line of talk \
only when it is in the log. Every chapter lists the numbers of the log lines it tells, in `events`, as plain integers \
without the #. Write in English and never mention the log, its numbers or event types in the text."""
_SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"},
    "chapters": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "events": {"type": "array", "items": {"type": "integer"}}},
        "required": ["text", "events"], "additionalProperties": False}}},
    "required": ["title", "chapters"], "additionalProperties": False}


class Chapter(TypedDict):
    """One chapter of a retelling: its `text`, the log positions it `events` cite, and the `actors` (IDs) who
    did them, in the order they are first cited; an event nobody did, such as a last call, adds none."""

    text: str
    events: list[int]
    actors: list[str]


class Retelling(TypedDict):
    """An evening retold: a catchy `title` and a few cited chapters."""

    title: str
    chapters: list[Chapter]


def _clock(seconds: float) -> str:
    # Game time as minutes and seconds into the evening; truncated, as a clock shows it.
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def told(events: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    """Choose the lines of the log the storyteller sees, each under its position in the log.

    Args:
        events: The evening's event log in order; a line's position in it is its number.

    Returns:
        The moments of the story score first (the first `MAX_LINES` of them), then the talk within `NEAR`
        events of each moment, then the rest of the colour thinned evenly (the first of every few kept) to fit
        `MAX_LINES`. In log order. An event logged once per participant is told once.

    Raises:
        KeyError: An event lacks `type`, `time` or `message`.
    """
    position = {id(event): index for index, event in enumerate(events)}
    chosen = [position[id(item["event"])] for item in story_moments(events)][:MAX_LINES]
    colour = [index for index, event in enumerate(events) if event["type"] in _COLOUR]
    near = [index for moment in list(chosen) for index in range(moment - NEAR, moment + NEAR + 1) if index in colour]
    chosen += [index for index in dict.fromkeys(near) if index not in chosen][:MAX_LINES - len(chosen)]
    rest = [index for index in colour if index not in chosen]
    room = MAX_LINES - len(chosen)
    if room > 0 and rest:
        chosen += rest[::-(-len(rest) // room)]
    return {index: events[index] for index in sorted(chosen)}


def retelling_question(events: Sequence[Mapping[str, Any]], score: StoryScore, note: str | None = None) -> Question:
    """Lay an evening out for the storyteller.

    Args:
        events: The evening's event log in order.
        score: Its story score; the counts tell the storyteller how big each kind of moment was.
        note: Why the storyteller's last answer was rejected, when this is the second try.

    Returns:
        A question whose content lists the chosen lines as `[#number time] words`.

    Raises:
        ValueError: The log has no event to retell.
        KeyError: An event lacks `type`, `time` or `message`.
    """
    shown = told(events)
    if not shown:
        raise ValueError("The evening has nothing to retell: no moment or talk in its log")
    counts = ", ".join(f"{kind}: {count}" for kind, count in score["moments"].items())
    lines = "\n".join(f"[#{index} {_clock(event['time'])}] {event['message']}" for index, event in shown.items())
    again = "" if note is None else f"\n\nYour last answer was rejected: {note}. Cite only numbers listed above."
    return {"system": [_STYLE], "content": f"What happened tonight, in order:\n{lines}\n\nMoments counted: {counts}{again}",
            "schema": _SCHEMA, "max_tokens": MAX_TOKENS}


def _chapter(item: Any, number: int, shown: Mapping[int, Mapping[str, Any]]) -> Chapter:
    if not isinstance(item, dict) or set(item) != {"text", "events"}:
        raise ValueError(f"Chapter {number} must be an object with a text and the events it cites, not {item!r}")
    text, cited = item["text"], item["events"]
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_CHAPTER_TEXT:
        raise ValueError(f"Chapter {number}'s text must be 1 to {MAX_CHAPTER_TEXT} characters, not {text!r}")
    if not isinstance(cited, list) or not cited:
        raise ValueError(f"Chapter {number} cites no event of the log")
    for event_id in cited:
        if type(event_id) is not int or event_id not in shown:
            raise ValueError(f"Chapter {number} cites #{event_id}, which was not among the lines shown")
    events = list(dict.fromkeys(cited))
    actors = [actor for actor in dict.fromkeys(shown[index]["actor_id"] for index in events) if actor is not None]
    return {"text": text.strip(), "events": events, "actors": actors}


def parse_retelling(answer: Any, shown: Mapping[int, Mapping[str, Any]]) -> Retelling:
    """Check the storyteller's answer: every chapter must cite lines it was shown.

    Args:
        answer: The decoded JSON the model returned.
        shown: The lines it was shown, from `told`.

    Returns:
        The title and chapters, trimmed, each citing its events once and naming who did them.

    Raises:
        ValueError: The answer is not a nonempty `title` and 1 to `MAX_CHAPTERS` chapters, or a chapter has no
            text of at most `MAX_CHAPTER_TEXT` characters, cites nothing, or cites a line that was not shown.
    """
    if not isinstance(answer, dict) or set(answer) != {"title", "chapters"}:
        raise ValueError(f"A retelling is an object with a title and chapters, not {answer!r}")
    title, chapters = answer["title"], answer["chapters"]
    if not isinstance(title, str) or not title.strip():
        raise ValueError("A retelling's title must be a nonempty string")
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= MAX_CHAPTERS:
        raise ValueError(f"A retelling has 1 to {MAX_CHAPTERS} chapters, not {chapters!r}")
    return {"title": title.strip(), "chapters": [_chapter(item, number, shown) for number, item in enumerate(chapters, 1)]}


def _cited_only(answer: Any, shown: Mapping[int, Mapping[str, Any]]) -> Any:
    # The last resort: keep the chapters whose citations stand, and show the story without the others.
    if not isinstance(answer, dict) or not isinstance(answer.get("chapters"), list):
        return answer
    standing = [item for item in answer["chapters"] if isinstance(item, dict) and isinstance(item.get("events"), list)
                and item["events"] and all(type(index) is int and index in shown for index in item["events"])]
    if answer["chapters"] and not standing:
        raise ValueError("No chapter of the retelling cites a line that was shown")
    return {**answer, "chapters": standing}


async def retell(events: Sequence[Mapping[str, Any]], score: StoryScore, ask: Ask) -> Retelling:
    """Have the storyteller retell an evening, with every chapter backed by the log.

    Args:
        events: The evening's event log in order.
        score: Its story score.
        ask: The model port. It is asked once; when the answer breaks the rules of `parse_retelling` it is asked
            once more with the reason, and then only the chapters that cite lines it was shown are kept.

    Returns:
        The checked retelling.

    Raises:
        ValueError: The log has nothing to retell, or the second answer has no chapter that stands.
        Exception: Whatever the port raises for a failed call is not caught.
    """
    shown = told(events)
    try:
        return parse_retelling(await ask(retelling_question(events, score)), shown)
    except ValueError as rejected:
        second = await ask(retelling_question(events, score, str(rejected)))
    return parse_retelling(_cited_only(second, shown), shown)
