"""Starting relationships: the ties two guests bring into the evening, before anything happens."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict, cast

KINDS = ("old friends", "rivals")


class Tie(TypedDict):
    """Two guests' starting relationship: guest IDs `a` and `b`, a kind of KINDS, and a note in words."""

    a: str
    b: str
    kind: str
    note: str


# A tie as one guest holds it: the other guest's ID and name, the kind and the note. `with` is a
# Python keyword, hence the functional form.
OwnTie = TypedDict("OwnTie", {"with": str, "name": str, "kind": str, "note": str})


def parse_ties(value: Any, guests: Sequence[str]) -> tuple[Tie, ...]:
    """Validate a scenario's starting relationships.

    Args:
        value: List of `{a, b, kind, note}` records.
        guests: IDs of tonight's guests.
    Returns:
        The ties in listed order.
    Raises:
        ValueError: The list or a tie is malformed, names an unknown guest or the same guest
            twice, has an unknown kind or an empty note, or a pair of guests is tied twice
            (in either order).
    """
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Scenario relationships must be a list")
    ties = tuple(_tie(item, guests) for item in value)
    pairs = [frozenset((item["a"], item["b"])) for item in ties]
    if len(set(pairs)) != len(pairs):
        raise ValueError("Two guests may share only one starting relationship")
    return ties


def _tie(data: Any, guests: Sequence[str]) -> Tie:
    if not isinstance(data, Mapping) or set(data) != {"a", "b", "kind", "note"}:
        raise ValueError("A relationship has exactly a, b, kind and note")
    if data["a"] not in guests or data["b"] not in guests or data["a"] == data["b"]:
        raise ValueError(f"A relationship ties two different guests of tonight, not {data['a']!r} and {data['b']!r}")
    if data["kind"] not in KINDS:
        raise ValueError(f"Relationship kind must be one of {', '.join(KINDS)}, not {data['kind']!r}")
    if not isinstance(data["note"], str) or not data["note"].strip():
        raise ValueError("A relationship needs a note in words")
    return Tie(a=data["a"], b=data["b"], kind=data["kind"], note=data["note"])


def own_ties(guest_id: str, ties: Sequence[Tie], names: Mapping[str, str]) -> list[OwnTie]:
    """List the ties one guest holds, from their side.

    Args:
        guest_id: The guest.
        ties: Validated starting relationships; each is held by both of its guests.
        names: Each guest's name by ID.
    Returns:
        The guest's ties in listed order.
    """
    return [{"with": other, "name": names[other], "kind": item["kind"], "note": item["note"]}
            for item in ties if guest_id in (item["a"], item["b"])
            for other in (item["b"] if item["a"] == guest_id else item["a"],)]


def parse_own_ties(value: Any) -> list[OwnTie]:
    """Validate the ties a guest holds, as kept in a saved world.

    Args:
        value: List of `{with, name, kind, note}` records.
    Returns:
        The ties.
    Raises:
        ValueError: The list or a tie is malformed or has an unknown kind.
    """
    if not isinstance(value, list) or any(
            not isinstance(item, Mapping) or set(item) != {"with", "name", "kind", "note"}
            or not all(isinstance(field, str) and field for field in item.values()) for item in value):
        raise ValueError("A guest's ties are a list of {with, name, kind, note} texts")
    if any(item["kind"] not in KINDS for item in value):
        raise ValueError("A guest's tie has an unknown kind")
    return [cast(OwnTie, dict(item)) for item in value]
