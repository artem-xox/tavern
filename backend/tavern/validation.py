"""Validators for numbers, cells, and IDs read from room and save data."""

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any


def number(value: Any, label: str, minimum: float, maximum: float) -> float:
    """Check a finite number within inclusive bounds.

    Args:
        value: Untrusted value.
        label: Name used in the error.
        minimum: Lowest allowed value.
        maximum: Highest allowed value.
    Returns:
        The value as a float.
    Raises:
        ValueError: The value is not a finite number in range.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return float(value)


def coordinate(value: Any, limit: int) -> int:
    """Check one cell coordinate.

    Args:
        value: Untrusted coordinate.
        limit: Map width or height.
    Returns:
        The coordinate.
    Raises:
        ValueError: The value is not an integer inside the map.
    """
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError("Cell coordinates must be integers inside the map")
    return value


def position(record: Mapping[str, Any], width: int, height: int) -> tuple[int, int]:
    """Read a record's cell.

    Args:
        record: Record with `x` and `y`.
        width: Map width.
        height: Map height.
    Returns:
        The (x, y) cell.
    Raises:
        ValueError: A coordinate is missing or outside the map.
    """
    return coordinate(record.get("x"), width), coordinate(record.get("y"), height)


def unique_ids(records: Sequence[Mapping[str, Any]], label: str) -> None:
    """Require nonempty, distinct string IDs.

    Args:
        records: Records with `id`.
        label: Plural noun used in the error.
    Raises:
        ValueError: An ID is missing, empty, or repeated.
    """
    identifiers = [item.get("id") for item in records]
    if any(not isinstance(item, str) or not item for item in identifiers):
        raise ValueError(f"{label} require nonempty string IDs")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"Duplicate {label} IDs")
