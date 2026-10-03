"""Character cards: a guest described in words, plus the 0–1 params the rules read."""

from collections.abc import Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from tavern.validation import number, unique_ids

PARAMS = ("patience", "temper", "sociability", "courage", "strength", "brawling", "tolerance", "comfort",
          "curiosity")
TEXT_FIELDS = ("name", "occupation", "background", "temperament", "speech", "quirks", "secret", "goal")
# A player's card is sent to a model as-is, so each field is bounded to keep a call's cost bounded.
_MAX_TEXT = 2000
# Looks name a stranger in every briefing and line about them, so they stay a short phrase.
_MAX_LOOKS = 200


class CardText(TypedDict):
    """Who a guest is, in the player's or the author's words."""

    name: str
    occupation: str
    background: str
    temperament: str
    speech: str
    quirks: str
    secret: str
    goal: str


class Card(CardText):
    """A complete card: `id`, the `sprite` it is drawn with, its words, and `params` (each of PARAMS, 0–1).

    `looks` is how strangers see the guest, such as "the grey-bearded man in a green cloak"
    (see `tavern.names`); a guest whose card has none is known by name to everyone.
    """

    id: str
    sprite: str
    params: dict[str, float]
    looks: NotRequired[str]


def _exact_fields(data: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    missing, unknown = fields - data.keys(), data.keys() - fields
    if missing or unknown:
        raise ValueError(f"{label} is missing {sorted(missing)} or has unknown {sorted(unknown)}")
    return data


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Card {label} must be nonempty text")
    if len(value) > _MAX_TEXT:
        raise ValueError(f"Card {label} must be at most {_MAX_TEXT} characters")
    return value


def parse_card_text(data: Any) -> CardText:
    """Validate the words of a card, as a player writes them.

    Args:
        data: Mapping with exactly the TEXT_FIELDS, each nonempty text of at most 2000 characters.
    Returns:
        The words, unchanged.
    Raises:
        ValueError: A field is missing, unknown, blank, too long or not text.
    """
    fields = _exact_fields(data, set(TEXT_FIELDS), "Card text")
    return CardText(**{key: _text(fields[key], key) for key in TEXT_FIELDS})


def parse_params(data: Any) -> dict[str, float]:
    """Validate a card's params.

    Args:
        data: Mapping with exactly the PARAMS, each a number from 0 to 1.
    Returns:
        The params as floats, in PARAMS order.
    Raises:
        ValueError: A param is missing, unknown, not a number or out of range.
    """
    fields = _exact_fields(data, set(PARAMS), "Card params")
    return {key: number(fields[key], f"Card param {key}", 0, 1) for key in PARAMS}


def parse_card(data: Any) -> Card:
    """Validate one complete card.

    Args:
        data: Mapping with exactly `id`, `sprite`, the TEXT_FIELDS and `params`, and optionally
            `looks` (nonempty text of at most 200 characters).
    Returns:
        The card.
    Raises:
        ValueError: A field is missing, unknown or malformed.
    """
    optional = {"looks"} & set(data) if isinstance(data, Mapping) else set()
    fields = _exact_fields(data, {"id", "sprite", "params", *TEXT_FIELDS, *optional}, "Card")
    words = parse_card_text({key: fields[key] for key in TEXT_FIELDS})
    for key in ("id", "sprite"):
        if not isinstance(fields[key], str) or not fields[key]:
            raise ValueError(f"Card {key} must be a nonempty string")
    card = Card(id=fields["id"], sprite=fields["sprite"], **words, params=parse_params(fields["params"]))
    if optional:
        if len(_text(fields["looks"], "looks")) > _MAX_LOOKS:
            raise ValueError(f"Card looks must be at most {_MAX_LOOKS} characters")
        card["looks"] = fields["looks"]
    return card


def parse_cards(records: Sequence[Any]) -> dict[str, Card]:
    """Validate a library of cards.

    Args:
        records: Card records, e.g. one per file under `data/characters/`.
    Returns:
        Cards by ID.
    Raises:
        ValueError: A card is invalid or two share an ID.
    """
    cards = [parse_card(item) for item in records]
    unique_ids(cards, "card")
    return {item["id"]: item for item in cards}
