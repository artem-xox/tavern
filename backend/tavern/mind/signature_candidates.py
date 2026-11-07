"""What a guest's signature items offer them to do: the acts, their targets, and the guest a protest or threat would name."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.body.items import ITEMS
from tavern.social.signature_acts import accused_of, brandished_lately, raised_lately, threatened_by


def _offered_verbs(actor: Mapping[str, Any]) -> set[str]:
    """List the verbs the things a guest carries give them (`Item.offers`).

    Args:
        actor: The guest, with their `inventory` (kinds missing from it count as none).

    Returns:
        The verbs of every carried item that offers any.
    """
    return {verb for kind, item in ITEMS.items() if actor["inventory"].get(kind) for verb in item.offers}


def rivals_in_sight(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """List the guests a protest could name: everyone in sight who is not staff (as `signature_acts._in_sight` does).

    Args:
        observation: The guest's observation, with the `people` in sight.

    Returns:
        Those people, in the order observed.
    """
    return [person for person in observation.get("people", []) if not person.get("post")]


def accused_in_sight(observation: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Tell whom a protest would be aimed at from where the guest stands (`signature_acts.accused_of`).

    Args:
        observation: The guest's observation.

    Returns:
        The person in sight the guest thinks worst of, or None when nobody is.
    """
    return accused_of(observation["actor"], rivals_in_sight(observation), observation.get("time", 0.0))


def threatened_in_sight(observation: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Tell whom a flag would be brandished at from where the guest stands (`signature_acts.threatened_by`).

    Args:
        observation: The guest's observation.

    Returns:
        The person in sight the guest dislikes enough to threaten, or None when there is none.
    """
    return threatened_by(observation["actor"], rivals_in_sight(observation), observation.get("time", 0.0))


def signature_actions(observation: Mapping[str, Any], walk_overs: Sequence[str | None]) -> list[tuple[str, str | None]]:
    """List the signature acts a guest may take now.

    Args:
        observation: The guest's observation.
        walk_overs: IDs of the guests the guest is already offered a walk over to; an interview is offered toward each.

    Returns:
        `(verb, target_id)` pairs: filming when they carry a phone; a protest sign, once rivals are in sight and the
        last raising is long enough ago; a flag, once someone in sight is disliked enough and the last brandishing is
        long enough ago; an interview toward each guest they could walk over to when they carry a
        microphone.
    """
    verbs = _offered_verbs(observation["actor"])
    acts: list[tuple[str, str | None]] = []
    if "livestream" in verbs:
        acts.append(("livestream", None))
    if "raise_sign" in verbs and rivals_in_sight(observation) and not raised_lately(observation):
        acts.append(("raise_sign", None))
    if "brandish_flag" in verbs and threatened_in_sight(observation) and not brandished_lately(observation):
        acts.append(("brandish_flag", None))
    if "interview_guest" in verbs:
        acts.extend(("interview_guest", person_id) for person_id in walk_overs)
    return acts
