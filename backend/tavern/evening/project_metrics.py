"""Projects in an evening: how many guests took one on, and how each ended."""

from collections.abc import Mapping, Sequence
import re
from typing import Any, TypedDict

from tavern.body.projects import PROJECTS

OUTCOMES = ("done", "failed", "dropped", "expired")


class ProjectCounts(TypedDict):
    """Projects that ended in the evening (`started` counts them, one still going at closing is not counted), and per
    kind in the order of `PROJECTS` how each ended."""

    started: int
    by_kind: dict[str, dict[str, int]]


# "Ada settled in with an ale (settle_in)", as `projects.honor_projects` logs an end.
_KIND = re.compile(r".* \((?P<kind>[a-z_]+)\)")


def project_counts(events: Sequence[Mapping[str, Any]]) -> ProjectCounts:
    """Count the projects of an evening by how they ended.

    Args:
        events: The complete event log.

    Returns:
        Counts from the `project_done`, `project_failed`, `project_dropped` and `project_expired` events.

    Raises:
        ValueError: A project event does not end in a kind of `PROJECTS`.
    """
    counts = {kind: dict.fromkeys(OUTCOMES, 0) for kind in PROJECTS}
    for event in events:
        outcome = event["type"].removeprefix("project_")
        if not event["type"].startswith("project_") or outcome not in OUTCOMES:
            continue
        match = _KIND.fullmatch(event["message"])
        if match is None or match["kind"] not in PROJECTS:
            raise ValueError(f"Cannot read the project in {event['message']!r}")
        counts[match["kind"]][outcome] += 1
    return {"started": sum(sum(item.values()) for item in counts.values()),
            "by_kind": {kind: item for kind, item in counts.items() if any(item.values())}}
