"""Recap: an evening's moments and talk laid out as a question for a storyteller, and its answer checked."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.evening.story_score import StoryScore, story_moments
from tavern.mind.questions import Ask, Question

MAX_LINES = 60  # Event lines in one question: the evening's story, not its whole log.
MAX_TEXT = 1200  # Characters of the retold story: a short read.
MAX_TOKENS = 700  # Bounds the answer; emoji take several tokens each.
# Besides the moments, these logged events give the storyteller the colour of the evening.
_COLOUR = ("arrival", "departure", "turn", "news_told", "insulted", "last_call")
_STYLE = """You are the storyteller of the Story Tavern. At closing time you retell the evening to the people who \
missed it, from a log of what happened.

Write a short, lively retelling: a catchy title and a story of three to six sentences. Be funny and warm, like a \
friend telling a tale at the bar. Open with a hook, build to the best moment, end on a punchline. Use emoji \
generously, one or two per sentence, so the story is fun to scan (🍺 🎲 💤 😡 👊 🎁 🚪).

Tell only what the log says: use the names in it, invent no events, and invent no guests. Quote a line of talk \
only when it is in the log. Write in English and never mention the log, event types or numbers."""
_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}},
           "required": ["title", "text"], "additionalProperties": False}


class Recap(TypedDict):
    """An evening retold: a catchy `title` and a short `text` with emoji."""

    title: str
    text: str


def _clock(seconds: float) -> str:
    # Game time as minutes and seconds into the evening; truncated, as a clock shows it.
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def _told(events: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    # Every moment stays; the colour is thinned evenly (first events kept) to fit `MAX_LINES`, with duplicates
    # of a shared event (one per participant) told once.
    moments = story_moments(events)
    chosen = {id(item["event"]) for item in moments}
    colour = [event for event in events if event["type"] in _COLOUR and id(event) not in chosen]
    room = max(0, MAX_LINES - len(moments))
    if room:
        chosen |= {id(event) for event in colour[::max(1, -(-len(colour) // room))]}
    return [event for event in events if id(event) in chosen]


def recap_question(events: Sequence[Mapping[str, Any]], score: StoryScore) -> Question:
    """Lay an evening out for the storyteller.

    Args:
        events: The evening's event log in order.
        score: Its story score; the counts tell the storyteller how big each kind of moment was.

    Returns:
        A question whose content lists the moments and the evening's colour as timed lines.

    Raises:
        ValueError: The log has no event to retell.
        KeyError: An event lacks `type`, `time` or `message`.
    """
    told = _told(events)
    if not told:
        raise ValueError("The evening has nothing to retell: no moment or talk in its log")
    counts = ", ".join(f"{kind}: {count}" for kind, count in score["moments"].items())
    lines = "\n".join(f"[{_clock(event['time'])}] {event['message']}" for event in told)
    return {"system": [_STYLE], "content": f"What happened tonight, in order:\n{lines}\n\nMoments counted: {counts}",
            "schema": _SCHEMA, "max_tokens": MAX_TOKENS}


def parse_recap(answer: Any) -> Recap:
    """Check the storyteller's answer.

    Args:
        answer: The decoded JSON the model returned.

    Returns:
        The title and text, trimmed.

    Raises:
        ValueError: The answer is not exactly a nonempty `title` and a nonempty `text` of at most `MAX_TEXT`
            characters.
    """
    if not isinstance(answer, dict) or set(answer) != {"title", "text"}:
        raise ValueError(f"A recap is an object with a title and a text, not {answer!r}")
    title, text = answer["title"], answer["text"]
    if not isinstance(title, str) or not isinstance(text, str) or not title.strip() or not text.strip():
        raise ValueError("A recap's title and text must be nonempty strings")
    if len(text.strip()) > MAX_TEXT:
        raise ValueError(f"A recap's text is {len(text.strip())} characters; the most is {MAX_TEXT}")
    return {"title": title.strip(), "text": text.strip()}


async def retell(events: Sequence[Mapping[str, Any]], score: StoryScore, ask: Ask) -> Recap:
    """Have the storyteller retell an evening.

    Args:
        events: The evening's event log in order.
        score: Its story score.
        ask: The model port; one question, one answer.

    Returns:
        The checked retelling.

    Raises:
        ValueError: The log has nothing to retell, or the answer breaks the rules of `parse_recap`.
    """
    return parse_recap(await ask(recap_question(events, score)))
