"""Whose table is whose, who is welcome at it, and what sitting down there uninvited does."""

from collections.abc import Mapping
from typing import Any

from tavern.social.social_acts import LIKED
from tavern.social.thoughts import familiarity_of, opinion_of


def liked(actor: Mapping[str, Any], other_id: str, now: float) -> bool:
    """Tell whether a guest is glad of someone's company at their own table.

    Args:
        actor: Visitor with `relations` and `thoughts` (a hand-made one may lack either).
        other_id: Person they think of.
        now: Current game time.

    Returns:
        True when they count the other a friend, or think at least `social_acts.LIKED` of them.
    """
    return familiarity_of(actor, other_id) == "friend" or opinion_of(actor, other_id, now) >= LIKED
