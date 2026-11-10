"""export_played: a played evening's full event log is stitched together from the snapshots' sliding windows."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_SPEC = importlib.util.spec_from_file_location("export_played", Path(__file__).parent.parent / "scripts" / "export_played.py")
assert _SPEC is not None and _SPEC.loader is not None
export_played = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(export_played)


def events(*times: float) -> list[dict[str, Any]]:
    return [{"time": time, "type": "turn", "message": f"at {time}"} for time in times]


@pytest.mark.parametrize(
    ("kept", "window", "expected"),
    [
        pytest.param([], events(1, 2), events(1, 2), id="first-window"),
        pytest.param(events(1, 2), events(1, 2), events(1, 2), id="nothing-new"),
        pytest.param(events(1, 2), events(2, 3, 4), events(1, 2, 3, 4), id="window-slid"),
        pytest.param(events(1, 2, 3), events(3, 4), events(1, 2, 3, 4), id="window-shorter-than-kept"),
        pytest.param(events(1, 2), events(5, 6), events(1, 2, 5, 6), id="gap-keeps-both"),
        pytest.param(events(1, 1), events(1, 1, 2), events(1, 1, 2), id="equal-events-repeat"),
        pytest.param(events(1), [], events(1), id="empty-window"),
    ],
)
def test_merge_events_keeps_every_event_once(kept: list[dict[str, Any]], window: list[dict[str, Any]],
                                             expected: list[dict[str, Any]]) -> None:
    assert export_played.merge_events(kept, window) == expected
