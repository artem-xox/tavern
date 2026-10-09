"""Aims in an evening: what guests came to talk for, and how often they got round to saying it."""

from collections.abc import Mapping, Sequence
import re
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


# "Ada means to pass the time with Bea (pass_time)" and "Ada got round to it: ... (tell_news:fever)", as
# `aims.begin_aim` and `aims.note_spoken` log them.
_AIM = re.compile(r".* \((?P<aim>[a-z_]+(?::[a-z_]+)?)\)")


def aim_counts(events: Sequence[Mapping[str, Any]]) -> AimCounts:
    """Count the aims of an evening.

    Args:
        events: The complete event log.

    Returns:
        The aims set (`aim_set` events) and kept (`aim_kept`), in all and per kind.

    Raises:
        ValueError: An aim event does not end in an aim, or names a kind that is not in `AIMS`.
    """
    counts: dict[str, AimKindCounts] = {kind: {"set": 0, "kept": 0} for kind in AIMS}
    for event in events:
        if event["type"] not in ("aim_set", "aim_kept"):
            continue
        match = _AIM.fullmatch(event["message"])
        kind = match["aim"].partition(":")[0] if match else ""
        if kind not in AIMS:
            raise ValueError(f"Cannot read the aim in {event['message']!r}")
        counts[kind]["set" if event["type"] == "aim_set" else "kept"] += 1
    return {"set": sum(item["set"] for item in counts.values()), "kept": sum(item["kept"] for item in counts.values()),
            "by_kind": {kind: item for kind, item in counts.items() if item["set"] or item["kept"]}}
