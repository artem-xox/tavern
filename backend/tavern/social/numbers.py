"""Stage numbers: which number a guest on the stage performs, at whom, and the words when no writer answers."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tavern.body.drunkenness import drunk_stage
from tavern.social.thoughts import opinion_of

# A toast is raised to someone the speaker thinks at least this well of; a roast aims at someone thought `ROASTED_AT`
# or worse, the opinion at which a guest may insult someone (`conversation.DISLIKED`, which cannot be imported here:
# its acts import the activity table, which gives the speeches).
TOAST_LIKED = 30.0
ROASTED_AT = -10.0
# Stages of drink at which a guest toasts, and at which their secret comes near their lips.
TOASTING = ("tipsy", "drunk", "wasted")
CONFESSING = ("drunk", "wasted")
# What a pitch opens with when no writer answers; the card's first catchphrase, or the plain closer, ends every number.
OPENERS = ("Quiet, everyone! Hear me out!", "Friends, patrons, whoever is still sober! A word!",
           "Everybody listen! I have something to say!")
PLAIN_CLOSER = "That is all, and it is the truth!"


@dataclass(frozen=True)
class Number:
    """One kind of number a guest performs from the stage.

    Attributes:
        brief: What the line writer is asked to write; `{target}` stands for the name of the one it is aimed at.
        aimed: Whether it is aimed at someone present.
    """

    brief: str
    aimed: bool


NUMBERS: Mapping[str, Number] = MappingProxyType({
    "toast": Number("a toast to {target}: raise a mug to them before the whole room, in the speaker's own manner, warm "
                    "but with one joke at their expense that the room will enjoy", True),
    "roast": Number("a roast of {target}: mock them before the whole room with their public record, their famous "
                    "blunders and what they did tonight, sharp and funny, as a comedian would at a roast dinner", True),
    "pitch": Number("a pitch to the whole room: the speaker's big idea, claim, campaign or cause, announced as at a "
                    "rally, a launch or a press conference, with one bold promise", False),
    "confession": Number("a drunken confession: the speaker starts to tell the room their secret, comes close enough "
                         "that everyone can guess it, then catches themselves and covers it with bluster",
                         False),
})


def choose_number(speaker: Mapping[str, Any], present: Sequence[str], now: float) -> tuple[str, str | None]:
    """Choose the number a guest performs, and at whom.

    Args:
        speaker: Guest on the stage, with `relations`, `thoughts`, `drunkenness`, `card` and `memory`.
        present: IDs of the people in the room who would hear it; the speaker's own is ignored.
        now: Game time, for opinions.

    Returns:
        (kind, target ID or None), the first that fits: a confession (drunk or worse, a secret on the card, none
        confessed tonight); a roast of the most disliked person present at `ROASTED_AT` or worse; a toast, when tipsy
        or worse, to the best liked present at `TOAST_LIKED` or better; else a pitch. Ties go to the lower ID.
    """
    stage = drunk_stage(speaker.get("drunkenness", 0.0)).name
    if stage in CONFESSING and (speaker.get("card") or {}).get("secret") and not _confessed(speaker):
        return "confession", None
    # Sorted, so that a tie on opinion goes to the lower ID whatever order the room lists them in.
    opinions = [(opinion_of(speaker, other, now), other) for other in sorted(set(present) - {speaker["id"]})]
    disliked = [item for item in opinions if item[0] <= ROASTED_AT]
    if disliked:
        return "roast", min(disliked)[1]
    liked = [(-opinion, other) for opinion, other in opinions if opinion >= TOAST_LIKED]
    if stage in TOASTING and liked:
        return "toast", min(liked)[1]
    return "pitch", None


def _confessed(speaker: Mapping[str, Any]) -> bool:
    return any(item["type"] == "gave_speech" and item.get("number") == "confession"
               for item in speaker.get("memory", []))


def scripted_number(speaker: Mapping[str, Any], kind: str, target: str | None, roll: float) -> list[str]:
    """Write a number's words without a writer: aimed, short, and never the guest's inner thought or secret.

    Args:
        speaker: Guest performing; their card's first catchphrase closes the number.
        kind: One of `NUMBERS`.
        target: The name the speaker knows the target by, for an aimed number; None otherwise.
        roll: A draw in [0, 1) that picks a pitch's opener.

    Returns:
        Two or three lines, said one after another.

    Raises:
        ValueError: The kind is unknown, or an aimed number has no target.
    """
    if kind not in NUMBERS:
        raise ValueError(f"Unknown number {kind!r}")
    if NUMBERS[kind].aimed and not target:
        raise ValueError(f"A {kind} is aimed at someone")
    catchphrases = (speaker.get("card") or {}).get("catchphrases") or []
    closer = catchphrases[0] if catchphrases else PLAIN_CLOSER
    lines = {"toast": [f"A toast! To {target}, the best company in this hall.", closer],
             "roast": [f"Look at {target}, everyone. Take a good long look.",
                       "I have seen more sense at the bottom of a mug.", closer],
             "pitch": [OPENERS[int(roll * len(OPENERS))], closer],
             "confession": ["I'll tell you something I never told a soul.", "No. No, forget it. More ale!"]}
    return lines[kind]
