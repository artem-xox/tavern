"""Aims in an evening: what guests came to talk for, and how often they got round to saying it."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.social.aims import AIMS


class AimKindCounts(TypedDict):
    """Aims of one kind set when a guest opened or joined a scene, and kept when they said what they came for."""

    set: int
    kept: int


class AimCounts(TypedDict):
    """Aims set and kept in all, and per kind in the order of `AIMS` (kinds never set are left out)."""

    set: int
    kept: int
    by_kind: dict[str, AimKindCounts]


def aim_counts(events: Sequence[Mapping[str, Any]]) -> AimCounts:
    """Count the aims of an evening.

    Args:
        events: The complete event log.

    Returns:
        The aims set (`aim_set` events) and kept (`aim_kept`), in all and per kind.

    Raises:
        ValueError: An aim event has no `aim` field, or names a kind that is not in `AIMS`.
    """
    counts: dict[str, AimKindCounts] = {kind: {"set": 0, "kept": 0} for kind in AIMS}
    for event in events:
        if event["type"] not in ("aim_set", "aim_kept"):
            continue
        kind = event.get("aim", "").partition(":")[0]
        if kind not in AIMS:
            raise ValueError(f"The aim event {event['message']!r} has no known `aim` field: {event.get('aim')!r}")
        counts[kind]["set" if event["type"] == "aim_set" else "kept"] += 1
    return {"set": sum(item["set"] for item in counts.values()), "kept": sum(item["kept"] for item in counts.values()),
            "by_kind": {kind: item for kind, item in counts.items() if item["set"] or item["kept"]}}
