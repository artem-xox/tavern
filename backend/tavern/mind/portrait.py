"""A guest's portrait in plain words, from their character card and starting ties."""

from collections.abc import Mapping
from typing import Any

# How a guest's side of each tie kind reads: "<name> is <phrase> of theirs".
_TIE_PHRASES = {"old friends": "an old friend", "rivals": "a rival", "bad blood": "someone they have bad blood with"}


def portrait(actor: Mapping[str, Any]) -> str:
    """Describe who a guest is: occupation, temperament and goal from their card, then their ties.

    Args:
        actor: The guest's own record; `card` is None for a guest not cast from a card, and
            `ties` (missing on older or bare records) lists their starting relationships.
    Returns:
        A few sentences, or "" for a guest with neither card nor ties.
    Raises:
        KeyError: A tie has a kind without a phrase.
    """
    card = actor.get("card")
    parts = [] if card is None else [
        f"Occupation: {card['occupation']}.", f"Temperament in words: {card['temperament']}",
        f"Their goal tonight: {card['goal']}"]
    parts += [f"{item['name']} is {_TIE_PHRASES[item['kind']]} of theirs ({item['note']})."
              for item in actor.get("ties", [])]
    return " ".join(parts)
