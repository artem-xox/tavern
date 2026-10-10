"""The question that has a model write a guest's phrasebook, and the check of its answer."""

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any

from tavern.mind.phrasebook import STOCK_KINDS, Phrasebook, check_phrasebook
from tavern.mind.questions import Question

# What the lines are written from. The secret and the goal are left out: a stock line is spoken to anyone, and
# whatever it is written from decides when it is stale (`card_hash`).
VOICE_FIELDS = ("name", "occupation", "background", "temperament", "speech", "quirks")
# Words a kind of line must not hold, whatever else it says. An answer to an invitation names none of the things
# that may be offered (the same line answers all of them) nor the luck of a game; a line that leaves because
# something presses does not say which need it is; a greeting does not assume the person is known; and no
# line invents a family for the guest, which the card does not give them.
_OFFERED = (r"dice|darts?|games?|play(?:ing)?|wager|bet|odds|luck|lucky|win|won|lose|lost|cheat|stakes?|deal|roll|"
            r"ale|beer|drinks?|pour|mug|cup|pint|buy|table|stool|seat|sit|bench|walk(?:ing)?|home|stroll")
_FORBIDDEN = {
    "accept": _OFFERED, "decline": _OFFERED,
    "pressed": r"nature|privy|yard|bladder|relieve|thirst|thirsty|sleep|sleepy|bed|tired|weary|ale|beer|drinks?|"
               r"cup|mug|water|dice|darts?|games?",
    "greet": r"again|back|usual|remember|before|last time|always|heard"}
_INVENTED = r"wife|husband|child|children|kids?|son|daughter|mother|father|brother|sister|family"
MAX_TOKENS = 3000  # Bounds the answer: six moments of about eight short lines, and some guests are wordy.


def card_hash(card: Mapping[str, Any]) -> str:
    """Name what a guest's stock lines were written from.

    Args:
        card: The guest's card, with `VOICE_FIELDS`.

    Returns:
        Twelve hex digits of the fields' digest; the lines are stale once it differs from the card's.

    Raises:
        KeyError: The card lacks one of `VOICE_FIELDS`.
    """
    text = json.dumps({key: card[key] for key in VOICE_FIELDS}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def voice_question(prompt: str, card: Mapping[str, Any]) -> Question:
    """Ask for a guest's stock lines.

    Args:
        prompt: The instructions (`data/minds/voice_prompt.md`).
        card: The guest's card, with `VOICE_FIELDS`.

    Returns:
        A question whose answer holds a list of lines for each of `STOCK_KINDS`.

    Raises:
        KeyError: The card lacks one of `VOICE_FIELDS`.
    """
    words = "\n".join(f"{key.capitalize()}: {card[key]}" for key in VOICE_FIELDS)
    lines = {"type": "array", "items": {"type": "string"}}
    schema = {"type": "object", "properties": {kind: lines for kind in STOCK_KINDS},
              "required": list(STOCK_KINDS), "additionalProperties": False}
    return Question(system=[prompt], content=f"THE GUEST\n\n{words}\n\nWrite their stock lines now.", schema=schema,
                    max_tokens=MAX_TOKENS)


def voice_lines(answer: Any, minimum: int) -> tuple[Phrasebook, list[str]]:
    """Check the model's answer to `voice_question`, leaving out the lines that name what they must not.

    Args:
        answer: The decoded answer object.
        minimum: Fewest lines of each moment worth keeping, once the unfit are out: fewer repeat too soon.

    Returns:
        The phrasebook (see `phrasebook.check_phrasebook`), and the lines left out, for the caller to report: an
        answer to an invitation that names a game, a drink, a seat or a walk, or a goodbye for a need that
        presses that names the need, a greeting that assumes the person is known, or any line that gives
        the guest a family.

    Raises:
        ValueError: The answer is not a valid phrasebook, or a moment has fewer than `minimum` lines left.
    """
    given = check_phrasebook(answer)
    book: dict[str, list[str]] = {}
    left_out: list[str] = []
    for kind in STOCK_KINDS:
        words = "|".join(filter(None, (_FORBIDDEN.get(kind), _INVENTED)))
        fit = [line for line in given.get(kind, []) if not re.search(rf"\b(?:{words})\b", line, re.IGNORECASE)]
        left_out += [line for line in given.get(kind, []) if line not in fit]
        if len(fit) < minimum:
            raise ValueError(f"A voice needs at least {minimum} fit lines of {kind}, not {len(fit)}")
        book[kind] = fit
    return book, left_out
