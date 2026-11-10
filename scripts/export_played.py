"""Export an evening played in the browser: its full event log, player counts and retelling, into a run directory."""

import argparse
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence
from urllib.request import urlopen

from tavern.evening.player_metrics import player_counts


def merge_events(kept: Sequence[dict[str, Any]], window: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add the events of a snapshot's latest-200 window that `kept` does not hold.

    Args:
        kept: Every event gathered so far, oldest first.
        window: The world's event log in a newer snapshot.

    Returns:
        `kept` plus what follows the longest overlap of its tail with the window's head. Equal events repeat,
        so the overlap is taken as the longest one; a window that no longer reaches `kept` is added whole.
    """
    for size in range(min(len(kept), len(window)), 0, -1):
        if list(kept[-size:]) == list(window[:size]):
            return [*kept, *window[size:]]
    return [*kept, *window]


def write_run(out: Path, events: Sequence[dict[str, Any]], snapshot: Mapping[str, Any]) -> None:
    """Write `events.jsonl`, `metrics.json` (player counts and story), `retelling.md` and `snapshot.json` into `out`."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))
    player = snapshot["state"]["player"]
    metrics = {"player": player_counts(events, None if player is None else player["actor_id"]), "story": snapshot["story"]}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out / "snapshot.json").write_text(json.dumps({key: value for key, value in snapshot.items() if key != "state"}, indent=2))
    retelling = snapshot["retelling"]
    if retelling is not None:
        chapters = "".join(f"{chapter['text']}\n\n> told from events {', '.join(f'#{index}' for index in chapter['events'])}\n\n"
                           for chapter in retelling["chapters"])
        (out / "retelling.md").write_text(f"# {retelling['title']}\n\n{chapters}")


def main() -> None:
    """Poll a running server's snapshot and keep the whole event log until the evening is retold."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="browser console: localStorage.getItem('tavern.session')")
    parser.add_argument("--out", type=Path, required=True, help="e.g. runs/s3-12-played-1")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--every", type=float, default=3.0, help="seconds between polls; the world keeps 200 events")
    args = parser.parse_args()
    events: list[dict[str, Any]] = []
    while True:
        with urlopen(f"{args.url}/api/state?session={args.session}") as response:
            snapshot = json.load(response)
        events = merge_events(events, snapshot["state"]["events"])
        write_run(args.out, events, snapshot)
        if snapshot["retelling"] is not None:
            print(f"retold: wrote {len(events)} events to {args.out}")
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
