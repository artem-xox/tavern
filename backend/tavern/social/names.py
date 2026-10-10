"""What guests call each other: a name once it is known, otherwise how the other looks."""

from collections.abc import Mapping, Sequence
import re
from typing import Any


def looks(actor: Mapping[str, Any]) -> str | None:
    """Tell how a guest looks to someone who does not know them.

    Args:
        actor: Visitor; one cast from a character card may carry its `looks`.

    Returns:
        The card's looks, such as "the grey-bearded man in a green cloak", or None for a guest
        without a card or without looks on it.
    """
    card = actor.get("card") or {}
    return card.get("looks")


def knows_name(viewer: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Tell whether a guest knows another's name.

    Args:
        viewer: Visitor with `relations`.
        other: Person they look at.

    Returns:
        True for themselves, and for someone whose relation says `knows_name`. A relation
        without the flag (made by hand, or before names were tracked) does not know it.
    """
    return viewer["id"] == other["id"] or viewer.get("relations", {}).get(other["id"], {}).get("knows_name", False)


def called(viewer: Mapping[str, Any], other: Mapping[str, Any]) -> str:
    """Name someone the way a guest would: by name if known, otherwise by their looks.

    Args:
        viewer: Visitor with `relations`.
        other: Person named, with `id`, `name` and maybe a `card`.

    Returns:
        Their name when the viewer knows it or there are no looks to describe them by;
        otherwise their looks.
    """
    appearance = looks(other)
    return other["name"] if appearance is None or knows_name(viewer, other) else appearance


def as_known(viewer: Mapping[str, Any], people: Sequence[Mapping[str, Any]], text: str) -> str:
    """Rewrite a message so that everyone in it is named the way a guest would name them.

    Args:
        viewer: Visitor reading the message, with `relations`.
        people: Everyone who may be named in it, with `id`, `name` and maybe a `card`.
        text: A message that names people by their names, as the event log does.

    Returns:
        The text with each whole-word mention of someone else's name replaced by `called`; the viewer's own
        name stays. One pass, so a replacement is never rewritten again.
    """
    labels = {other["name"]: called(viewer, other) for other in people if other["id"] != viewer["id"]}
    if not labels:
        return text
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in labels) + r")\b")
    return pattern.sub(lambda match: labels[match.group(1)], text)
