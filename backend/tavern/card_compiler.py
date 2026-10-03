"""The card compiler: a model reads a player's card and proposes its 0–1 params for confirmation."""

from typing import TypedDict

from tavern.cards import PARAMS, TEXT_FIELDS, CardText, parse_params
from tavern.questions import Ask, Question

# What each param means, with what 0 and 1 look like in a guest, for the model to judge by.
_MEANINGS = {
    "patience": "how long they wait calmly in a line or for a drink (0 storms off at once, 1 waits all night)",
    "temper": "how quickly they flare up at a slight (0 never angry, 1 explodes at a look)",
    "sociability": "how much they seek company and talk (0 a loner, 1 the life of the room)",
    "courage": "how readily they face danger or a threat (0 flees from any trouble, 1 fears nothing)",
    "strength": "bodily strength (0 frail, 1 a blacksmith or soldier in their prime)",
    "brawling": "skill and experience in a fist fight (0 has never thrown a punch, 1 a veteran brawler)",
    "tolerance": "how much ale they hold before it shows (0 tipsy after one mug, 1 drinks anyone under the table)",
    "comfort": "how much a cosy seat, warmth and a good table matter to them (0 not at all, 1 a great deal)",
    "curiosity": "how strongly news, strangers and noises draw them (0 incurious, 1 must know everything)",
}


class CompiledCard(TypedDict):
    """Params proposed for a player's card, for them to confirm.

    `compiled` is False when nobody read the text (`source` `offline`): the params are then
    defaults, and `note` says so.
    """

    params: dict[str, float]
    compiled: bool
    source: str
    note: str


class RejectedParams(ValueError):
    """The model's params were malformed or out of range, so none are proposed."""


def _instructions() -> str:
    meanings = "\n".join(f"- {name}: {_MEANINGS[name]}" for name in PARAMS)
    return ("You read character cards for guests of a medieval border inn and rate each guest on nine "
            "traits, each a number from 0 to 1, where 0.5 is an ordinary person. Judge only from what the card "
            "says or clearly implies; when it says nothing about a trait, answer 0.5. Use the whole range: an "
            "old soldier's strength and brawling are high, a frail scholar's low.\n\nThe traits:\n" + meanings)


def _schema() -> dict[str, object]:
    # Numeric bounds are checked after the answer arrives; the schema only fixes its shape.
    return {"type": "object", "properties": {name: {"type": "number", "description": _MEANINGS[name]}
                                             for name in PARAMS},
            "required": list(PARAMS), "additionalProperties": False}


def card_question(text: CardText) -> Question:
    """Ask for a card's params: fixed instructions first, the player's words after them.

    Args:
        text: The player's card in words.
    Returns:
        The question; its system prefix is the same for every card.
    """
    words = "\n".join(f"{field}: {text[field]}" for field in TEXT_FIELDS)  # type: ignore[literal-required]
    return Question(system=[_instructions()], content=f"The card:\n{words}", schema=_schema(), max_tokens=300)


async def compile_card(text: CardText, ask: Ask) -> CompiledCard:
    """Have the model read a player's card and propose its params.

    Args:
        text: Validated words of the card (see `cards.parse_card_text`).
        ask: The mind-layer model port.
    Returns:
        The proposed params, marked as compiled by Claude.
    Raises:
        RejectedParams: The answer misses, adds, or mistypes a param, or one is outside 0–1.
        Exception: Whatever recoverable error the port raises (`claude.ClaudeError`).
    """
    answer = await ask(card_question(text))
    try:
        params = parse_params(answer)
    except ValueError as error:
        raise RejectedParams(f"Rejected the model's params: {error}") from error
    return CompiledCard(params=params, compiled=True, source="claude",
                        note="Read from the card by Claude; confirm or adjust before the evening.")


def offline_card(text: CardText) -> CompiledCard:
    """Propose default params for a card nobody can read, labeled as not compiled.

    Args:
        text: Validated words of the card; they do not change the defaults.
    Returns:
        Every param at 0.5, an ordinary person.
    """
    return CompiledCard(params=dict.fromkeys(PARAMS, 0.5), compiled=False, source="offline",
                        note="Not compiled: no Claude key on the server, so these are default params.")
