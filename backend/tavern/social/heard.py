"""Heard lines: what each guest said and heard in tonight's conversations, and how a writer is shown it."""

from collections.abc import Mapping
from itertools import groupby
import math
from typing import Any, TypedDict

from tavern.hall.state import World
from tavern.hall.validation import number
from tavern.social.conversation import ACTS
from tavern.social.names import called
from tavern.social.scenes import Conversation, Turn


class Heard(TypedDict):
    """A line a guest spoke or heard: when, in which scene, who said it (`speaker_id`, and `speaker`
    as the listener called them at that moment, see `names.called`), the words and the speech act."""

    time: float
    scene_id: str
    speaker_id: str
    speaker: str
    line: str
    act: str


class EarlierLine(TypedDict):
    """One remembered line in a writer's view: who said it, as the guest called them, and the words."""

    speaker: str
    line: str


# `with` is a keyword, so the scene's other voices need the functional form.
EarlierScene = TypedDict("EarlierScene", {"scene_id": str, "with": list[str], "lines": list[EarlierLine]})


def hear_line(world: World, scene: Conversation, turn: Turn) -> None:
    """Let every member of a scene remember a line just spoken, the speaker too.

    Args:
        world: World whose guests' `heard` lists are updated in place; `rules.conversation.recall_lines`
            of them are kept, the newest.
        scene: Scene the line was spoken in, before its act takes effect, so the members are those who
            heard it: a guest who joins later lacks the earlier lines.
        turn: The spoken line.
    """
    people = {item["id"]: item for item in world["actors"]}
    speaker, keep = people[turn["speaker"]], world["rules"]["conversation"]["recall_lines"]
    for member_id in scene["participants"]:
        listener = people[member_id]
        listener["heard"].append(Heard(time=turn["time"], scene_id=scene["id"], speaker_id=speaker["id"],
                                       speaker=called(listener, speaker), line=turn["line"], act=turn["act"]))
        del listener["heard"][:-keep]


def earlier_lines(actor: Mapping[str, Any], limit: int, excluding: str | None = None) -> list[EarlierScene]:
    """Show a guest's latest remembered lines, grouped by the scene they were spoken in.

    Args:
        actor: Guest whose `heard` lines are shown.
        limit: Most lines shown in all; the newest are kept.
        excluding: A scene whose lines are left out, such as the one the writer already sees in full.

    Returns:
        Scenes oldest first, each with the other voices in it (as the guest called them, in order of
        first speaking) and its lines, newest last. A guest who heard nothing gets an empty list.
    """
    lines = [item for item in actor["heard"] if item["scene_id"] != excluding][-limit:]
    scenes: list[EarlierScene] = []
    for scene_id, run in groupby(lines, key=lambda item: item["scene_id"]):
        group = list(run)
        others = list(dict.fromkeys(item["speaker"] for item in group if item["speaker_id"] != actor["id"]))
        scenes.append({"scene_id": scene_id, "with": others,
                       "lines": [{"speaker": item["speaker"], "line": item["line"]} for item in group]})
    return scenes


def check_heard(actor: Mapping[str, Any], rules: Mapping[str, Any]) -> None:
    """Check a saved visitor's remembered lines.

    Args:
        actor: Untrusted saved visitor record.
        rules: The saved rules, whose `conversation.recall_lines` caps the list.

    Raises:
        ValueError: `heard` is missing, longer than the cap, or holds a malformed line.
    """
    heard = actor.get("heard")
    if not isinstance(heard, list) or len(heard) > rules["conversation"]["recall_lines"]:
        raise ValueError("Saved heard lines must be a list within the recall cap")
    for item in heard:
        if not isinstance(item, dict) or set(item) != set(Heard.__annotations__):
            raise ValueError(f"Invalid saved heard line {item!r}")
        for key in ("scene_id", "speaker_id", "speaker", "line"):
            if not isinstance(item[key], str) or not item[key]:
                raise ValueError(f"Saved heard line {key} must be nonempty text, not {item[key]!r}")
        if item["act"] not in ACTS:
            raise ValueError(f"Saved heard line has an unknown speech act {item['act']!r}")
        number(item["time"], "Saved heard line time", 0, math.inf)
