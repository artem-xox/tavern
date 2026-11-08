"""The player's typed lines: the reader ports, and the boundary that makes a turn of a reading."""

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, TypedDict

from tavern.hall.memory import log_event
from tavern.hall.player import steered
from tavern.hall.state import World, find_actor
from tavern.mind.turn_view import next_speaker, turn_view
from tavern.social.scenes import conversation_of
from tavern.social.speeches import on_stage_for
from tavern.social.stage_lines import comeback_owed_to
from tavern.social.turns import check_turn

# Reads the act of words already written: the played guest's view (`turn_view` as them), the text, and `to`
# (`auto`, `everyone` or a guest's ID). Answers `{act, addressee, topic, invitation?, fact_id?}`, which
# `deliver_reading` checks like a guest's turn. Any failure it raises makes the line a remark.
ReadLine = Callable[[Mapping[str, Any], str, str], Coroutine[Any, Any, Mapping[str, Any]]]
_EXTRAS = ("invitation", "fact_id")
# Reads the number of words already written for the stage: the performer's view (`stage_lines.number_view`) and the
# text. Answers `{number, target}`: one of `numbers.NUMBERS` and a guest in the hall, or None for a number with no
# target. `stage_lines.deliver_number` checks it; any failure it raises makes the text a pitch to the hall.
ReadNumber = Callable[[Mapping[str, Any], str], Coroutine[Any, Any, Mapping[str, Any]]]


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


async def read_as_pitch(view: Mapping[str, Any], text: str) -> Mapping[str, Any]:
    """Read every number as a pitch to the hall: the offline reader.

    Args:
        view: The performer's view of the stage.
        text: What they typed.

    Returns:
        A pitch with no target.
    """
    return {"number": "pitch", "target": None}


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


class PlayerTurn(TypedDict):
    """What the played guest's scene waits for, as the chat shows it."""

    scene_id: str | None
    state: str  # "none" | "free" | "your_turn" | "reading" | "on_stage" | "comeback"
    silence_at: float | None  # game time the turn passes in silence; only for "your_turn"


def player_turn(world: World) -> PlayerTurn | None:
    """Tell what the played guest's scene waits for.

    Args:
        world: Current world.

    Returns:
        None without a player. Otherwise the guest's scene and the state: `none` (on autopilot or in no scene),
        `comeback` (a heckle is owed an answer), `on_stage` (up there with no number given; `silence_at` is when they
        step down), `reading` (their typed line is being read or waits to be spoken), `your_turn` (the scene waits for their
        line, which passes in silence at `silence_at`, as `turns` plays it) or `free` (someone else speaks next,
        and they can still cut in).
    """
    player = world["player"]
    if player is None:
        return None
    staged = _on_the_stage(world, player)
    if staged is not None:
        return staged
    scene = conversation_of(world, player["actor_id"])
    if scene is None or not steered(world, player["actor_id"]):
        return {"scene_id": None if scene is None else scene["id"], "state": "none", "silence_at": None}
    claim = scene["writing"]
    if claim is not None and claim["speaker"] == player["actor_id"]:
        return {"scene_id": scene["id"], "state": "reading", "silence_at": None}
    if next_speaker(scene) != player["actor_id"]:
        return {"scene_id": scene["id"], "state": "free", "silence_at": None}
    typed = player.get("typing_at")
    held_since = scene["next_turn_at"] if typed is None else max(scene["next_turn_at"], typed)
    return {"scene_id": scene["id"], "state": "your_turn",
            "silence_at": held_since + world["rules"]["player"]["silence"] * world["speed"]}


def _on_the_stage(world: World, player: Mapping[str, Any]) -> PlayerTurn | None:
    # The stage's states come before the scene's, as `say` tries the stage first. None when the guest is on neither errand.
    performer = find_actor(world, player["actor_id"])
    if performer is None or not steered(world, performer["id"]):
        return None
    if comeback_owed_to(world, performer["id"]) is not None:
        return {"scene_id": None, "state": "comeback", "silence_at": None}
    since = on_stage_for(world, performer)
    if since is None:
        return None
    action = performer["action"]  # on_stage_for found a give_speech under way
    assert action is not None
    climbed = action.get("climbed_at", world["time"] - since)
    held_since = max(climbed, player.get("typing_at") or 0.0)
    return {"scene_id": None, "state": "on_stage",
            "silence_at": held_since + world["rules"]["player"]["silence"] * world["speed"]}
