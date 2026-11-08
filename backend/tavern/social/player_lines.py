"""The player's typed lines: the reader port, and the boundary that makes a turn of a reading."""

from collections.abc import Callable, Coroutine, Mapping
from typing import Any

from tavern.hall.memory import log_event
from tavern.hall.player import steered
from tavern.hall.state import World
from tavern.mind.turn_view import turn_view
from tavern.social.turns import check_turn

# Reads the act of words already written: the played guest's view (`turn_view` as them), the text, and `to`
# (`auto`, `everyone` or a guest's ID). Answers `{act, addressee, topic, invitation?, fact_id?}`, which
# `deliver_reading` checks like a guest's turn. Any failure it raises makes the line a remark.
ReadLine = Callable[[Mapping[str, Any], str, str], Coroutine[Any, Any, Mapping[str, Any]]]
_EXTRAS = ("invitation", "fact_id")


async def read_as_remark(view: Mapping[str, Any], text: str, to: str) -> Mapping[str, Any]:
    """Read every line as a remark: the offline reader.

    Args:
        view: The played guest's view of their scene.
        text: What they typed.
        to: `auto`, `everyone` or a guest's ID.

    Returns:
        A remark to the guest named; for `auto`, to whoever spoke the last line addressed to the player, or to
        everyone (None) when no one did; for `everyone`, to no one in particular.
    """
    me = view["speaker"]["id"]
    if to == "auto":
        addressee = next((turn["speaker"] for turn in reversed(view["conversation"]["turns"])
                          if turn["addressee"] == me), None)
    else:
        addressee = None if to == "everyone" else to
    return {"act": "remark", "addressee": addressee, "topic": view["conversation"]["topic"]}


def deliver_reading(world: World, scene_id: str, turn: int, text: str, to: str, outcome: Callable[[], Any]) -> None:
    """Hand a reader's answer to the scene as the player's turn, to be spoken when due.

    The line is always the player's text. A reading that fails or that `check_turn` refuses becomes a remark, and
    the reason is logged as `misread`: never a scripted line.

    Args:
        world: Authoritative world.
        scene_id: Scene the line was typed in.
        turn: Index of the turn the player's claim holds.
        text: What the player typed.
        to: `auto`, `everyone` or a guest's ID; a guest or `everyone` overrides the reading's addressee.
        outcome: Returns the reading, or raises the reader's error, like an asyncio task's `result`.

    Returns:
        None. An answer for a scene that ended, or whose claim is no longer the player's turn, is dropped.
    """
    try:
        answer, failure = outcome(), None
    except Exception as error:  # Any reader failure makes the line a remark, as a writer's makes a scripted line.
        answer, failure = None, error
    scene = next((item for item in world["conversations"] if item["id"] == scene_id), None)
    player = world["player"]
    claim = scene["writing"] if scene is not None else None
    if (scene is None or player is None or claim is None or claim["turn"] != turn
            or claim["speaker"] != player["actor_id"] or not steered(world, player["actor_id"])
            or scene["written"] is not None):
        return
    view = turn_view(world, scene, player["actor_id"])
    explicit = None if to == "everyone" else to if to in scene["participants"] else None
    try:
        if failure is not None:
            raise failure
        scene["written"] = check_turn(view, _candidate(answer, text, to))
    except Exception as error:
        scene["written"] = {"line": text, "act": "remark", "addressee": explicit, "topic": scene["topic"]}
        refused = log_event(world, player["actor_id"], "misread",
                            f"{view['speaker']['name']}'s line was read as a remark ({error})")
        refused["speaker_id"] = player["actor_id"]


def _candidate(answer: Any, text: str, to: str) -> dict[str, Any]:
    # The reading as a turn for `check_turn`: the player's words, and `to` over the reading's addressee unless auto.
    if not isinstance(answer, Mapping):
        raise ValueError(f"A reading is an object, not {answer!r}")
    turn = {"line": text, "act": answer["act"], "addressee": answer["addressee"], "topic": answer["topic"],
            **{key: answer[key] for key in _EXTRAS if answer.get(key) is not None}}
    if to != "auto":
        turn["addressee"] = None if to == "everyone" else to
    return turn
