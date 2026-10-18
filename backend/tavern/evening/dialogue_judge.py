"""A model's verdict on a recorded talk between two guests: the rubric it is asked, and the answer checked."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.mind.questions import Ask, Question


class Verdict(TypedDict):
    """Scores from 1 (wooden) to 5 (alive) per criterion, and a few words on why."""

    scores: dict[str, int]
    notes: str


# What the judge scores, each from 1 to 5. The order is the order of the report's columns.
CRITERIA: tuple[str, ...] = ("in_character", "development", "liveliness", "coherence")
_MEANING = {
    "in_character": "each speaks as their real public self would, as the character notes say; 1 = generic tavern "
                    "talk or the wrong person, 5 = you would know who speaks without the name",
    "development": "the talk goes somewhere: new points, an escalation, a concession, a walk-off; 1 = the same "
                   "point over and over, 5 = every few lines something changes",
    "liveliness": "it sounds like two people, not an echo: answers react to meaning, wit, interruptions; 1 = "
                  "each line rephrases the last one, 5 = sharp, varied, surprising",
    "coherence": "lines follow from one another and from what they are; 1 = non sequiturs, 5 = a real exchange"}
_RUBRIC = ("You judge a short recorded conversation between two famous people in a tavern game, written line by "
           "line by a small model. Be strict: a 3 is ordinary, a 5 is rare.\n\nScore each criterion from 1 to 5:\n"
           + "\n".join(f"- {name}: {meaning}" for name, meaning in _MEANING.items())
           + "\n\nAnswer with the scores and one or two sentences of notes naming the weakest moment.")
MAX_TOKENS = 300


def judge_question(transcript: Sequence[str], look_for: Mapping[str, str]) -> Question:
    """Ask for a verdict on a talk.

    Args:
        transcript: The talk, one "<name> (<act>): <line>" per line (`dialogue_metrics.pair_transcript`).
        look_for: What playing each speaker well looks like, by name.

    Returns:
        The question: the rubric as the cached prefix, then the character notes and the transcript.

    Raises:
        ValueError: The transcript is empty: there is nothing to judge.
    """
    if not transcript:
        raise ValueError("An empty talk cannot be judged")
    notes = "\n".join(f"- {name}: {text}" for name, text in look_for.items())
    content = f"Character notes:\n{notes}\n\nThe conversation, oldest first:\n" + "\n".join(transcript)
    return Question(system=[_RUBRIC], content=content, schema=_schema(), max_tokens=MAX_TOKENS)


def _schema() -> dict[str, Any]:
    # The range is checked in `parse_verdict`: structured output takes no numeric bounds.
    score = {"type": "integer", "description": "1 to 5"}
    return {"type": "object", "properties": {
        "scores": {"type": "object", "properties": dict.fromkeys(CRITERIA, score), "required": list(CRITERIA),
                   "additionalProperties": False},
        "notes": {"type": "string"}}, "required": ["scores", "notes"], "additionalProperties": False}


def parse_verdict(answer: Any) -> Verdict:
    """Check a verdict at the boundary.

    Args:
        answer: The decoded answer object.

    Returns:
        The verdict.

    Raises:
        ValueError: It is not exactly scores and notes, a score is not a whole number from 1 to 5, a criterion
            is missing or unknown, or the notes are blank.
    """
    if not isinstance(answer, Mapping) or set(answer) != {"scores", "notes"}:
        raise ValueError(f"A verdict has exactly scores and notes, not {answer!r}")
    scores = answer["scores"]
    if not isinstance(scores, Mapping) or set(scores) != set(CRITERIA):
        raise ValueError(f"A verdict scores exactly {', '.join(CRITERIA)}, not {scores!r}")
    for name, value in scores.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"The {name} score must be a whole number from 1 to 5, not {value!r}")
    if not isinstance(answer["notes"], str) or not answer["notes"].strip():
        raise ValueError("A verdict needs notes in words")
    return Verdict(scores=dict(scores), notes=answer["notes"])


async def judge_dialogue(transcript: Sequence[str], look_for: Mapping[str, str], ask: Ask) -> Verdict:
    """Ask a model through a port to judge a talk.

    Args:
        transcript: The talk, as for `judge_question`.
        look_for: What playing each speaker well looks like, by name.
        ask: The model port, e.g. `claude.ask_claude` bound to its config.

    Returns:
        The checked verdict.

    Raises:
        ValueError: The transcript is empty or the answer is malformed.
    """
    return parse_verdict(await ask(judge_question(transcript, look_for)))
