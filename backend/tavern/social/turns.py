"""Turns in a conversation scene: the turn writer port, the boundary that checks its answers, and when lines are spoken.

The world owns timing: a scene's next line is due at `next_turn_at`, the previous line's reading
time after it was spoken. A runner may claim the next turn (`claim_turns`) as soon as the previous
line is spoken, ask its writer asynchronously, and hand the answer back (`deliver_turn`); the world
speaks it when due. An unclaimed turn is written by the scripted writer on the spot, and a claimed
one that has no answer `rules.conversation.turn_timeout` seconds after it was due too.
"""

from collections.abc import Callable, Coroutine, Mapping
from typing import Any

from tavern.hall.memory import log_event
from tavern.hall.player import steered
from tavern.hall.state import World
from tavern.mind.scripted import scripted_turn
from tavern.mind.turn_view import next_speaker, turn_view
from tavern.social.aims import note_spoken
from tavern.social.conversation import ACTS
from tavern.social.heard import hear_line
from tavern.social.overhearing import overhear_turn
from tavern.social.scenes import Conversation, Turn, TurnResult, awaits_company_change

# Writes the next line of a scene from the speaker's view (see `turn_view`) and the AI config.
# `scripted.write_scripted_turn` is the offline writer; E16 adds Claude Haiku. Any failure it
# raises falls back to a scripted line.
TurnWriter = Callable[[Mapping[str, Any], Mapping[str, Any]], Coroutine[Any, Any, TurnResult]]

# The line of the turn that passes when a steered guest's player neither types nor speaks.
SILENCE_LINE = "…"
_FIELDS = {"line", "act", "addressee", "topic"}
_OPTIONAL = {"invitation", "fact_id"}


def reading_time(line: str, rules: Mapping[str, Any]) -> float:
    """Tell how long the others take to hear out a line before the next one.

    Args:
        line: Spoken words.
        rules: `min_gap` seconds and `chars_per_second` of `rules.conversation`.

    Returns:
        max(min_gap, characters / chars_per_second), in game seconds.
    """
    return max(rules["min_gap"], len(line) / rules["chars_per_second"])


def check_turn(view: Mapping[str, Any], result: Any) -> TurnResult:
    """Validate a writer's answer against the scene it was written for.

    Args:
        view: The view the writer was given.
        result: Its answer.

    Returns:
        The answer as a turn result.

    Raises:
        ValueError: It is not exactly a line, act, addressee and topic (plus an invitation for
            an `invite`); the line or topic is empty or not text; the act is unknown or not
            offered now; it addresses the speaker or someone not in the scene; an `invite` addresses
            someone on duty behind a bar (`on_duty` in the view); or an `invite`
            addresses nobody or names a kind not offered; a `promise` addresses nobody.
    """
    if not isinstance(result, Mapping) or set(result) - _OPTIONAL != _FIELDS:
        raise ValueError(f"A turn has exactly the fields {sorted(_FIELDS)}, not {result!r}")
    for key in ("line", "topic"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError(f"A turn's {key} must be nonempty text, not {result[key]!r}")
    if result["act"] not in view["acts"]:
        raise ValueError(f"Unknown speech act {result['act']!r}, or not one offered now")
    others = {item["id"] for item in view["conversation"]["participants"]} - {view["speaker"]["id"]}
    if result["addressee"] is not None and result["addressee"] not in others:
        raise ValueError(f"{result['addressee']!r} is not someone else in the conversation")
    on_duty = {item["id"] for item in view["conversation"]["participants"] if item.get("on_duty")}
    if result["act"] == "invite" and result["addressee"] in on_duty:
        raise ValueError(f"{result['addressee']!r} is on duty behind the bar and cannot be invited away")
    if result["act"] == "promise" and result["addressee"] is None:
        raise ValueError("A promise is made to someone in particular")
    turn: TurnResult = {"line": result["line"], "act": result["act"], "addressee": result["addressee"],
                        "topic": result["topic"]}
    if result["act"] == "invite" or "invitation" in result:
        turn["invitation"] = _invitation(view, result)
    if result["act"] == "share_news" or "fact_id" in result:
        turn["fact_id"] = _fact(view, result)
    return turn


def _invitation(view: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    # Only an invite carries an invitation, to someone in particular, of a kind on offer.
    if result["act"] != "invite" or result["addressee"] is None:
        raise ValueError("Only an invite to someone in particular carries an invitation")
    if result.get("invitation") not in view["invitations"]:
        raise ValueError(f"Invitation {result.get('invitation')!r} is not one on offer")
    return result["invitation"]


def _fact(view: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    # Only news-telling names a fact, and one the speaker holds.
    if result["act"] != "share_news":
        raise ValueError("Only telling news names a fact")
    if result.get("fact_id") not in {item["id"] for item in view["speaker"].get("news") or []}:
        raise ValueError(f"Fact {result.get('fact_id')!r} is not news the speaker holds")
    return result["fact_id"]


def claim_turns(world: Mapping[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    """Claim every scene's next turn that nobody is writing yet, for a runner's writer.

    Args:
        world: World whose scenes are marked as being written (`writing`).

    Returns:
        (scene ID, turn index, view) per claimed turn, in scene order: ask the writer with the
        view and hand its answer to `deliver_turn` with the scene ID and turn index.
    """
    claims = []
    for scene in world["conversations"]:
        # A line for a scene that is about to end, or to lose a guest, would never be spoken; none is asked for.
        # The player speaks for a steered guest, so no writer is asked (the scene waits: see `speak_turns`).
        if (scene["writing"] is None and scene["written"] is None and not awaits_company_change(world, scene)
                and not steered(world, next_speaker(scene))):
            view = turn_view(world, scene)
            scene["writing"] = {"turn": view["conversation"]["turn"], "speaker": view["speaker"]["id"],
                                "since": world["time"]}
            claims.append((scene["id"], view["conversation"]["turn"], view))
    return claims


def deliver_turn(world: World, scene_id: str, turn: int, outcome: Callable[[], Any]) -> None:
    """Hand a writer's answer to its scene, to be spoken when due.

    Args:
        world: Authoritative world.
        scene_id: Scene the turn was claimed in.
        turn: Index of the claimed turn.
        outcome: Returns the answer, or raises the writer's error, like an asyncio task's `result`.

    Returns:
        None. An answer for a scene that ended, or whose company changed since the claim, is
        dropped. An invalid answer or a failure is logged and replaced by a scripted line.
    """
    try:
        answer, failure = outcome(), None
    except Exception as error:  # Any writer failure falls back to a scripted line, as decisions do.
        answer, failure = None, error
    scene = next((item for item in world["conversations"] if item["id"] == scene_id), None)
    if scene is None or scene["writing"] is None or scene["writing"]["turn"] != turn:
        return
    view = turn_view(world, scene)
    try:
        if failure is not None:
            raise failure
        scene["written"] = check_turn(view, answer)
    except Exception as error:
        scene["written"] = scripted_turn(view)
        failed = log_event(world, None, "turn_failed",
                           f"A line for {view['speaker']['name']} failed ({error}); a scripted one stands in")
        failed["speaker_id"] = view["speaker"]["id"]


def speak_turns(world: World) -> None:
    """Speak every scene's line that is due, and let its act take effect.

    Args:
        world: World whose scenes, event log and visitors are updated in place.
    """
    rules = world["rules"]["conversation"]
    for scene in list(world["conversations"]):
        if scene not in world["conversations"] or world["time"] < scene["next_turn_at"]:
            continue
        speaker_id = next_speaker(scene)
        if steered(world, speaker_id):
            _await_player(world, scene, speaker_id)
            continue
        awaited = scene["writing"] is not None and scene["written"] is None
        # The model answers in real seconds, so a faster world waits proportionally more game seconds for it.
        if awaited and world["time"] < scene["next_turn_at"] + rules["turn_timeout"] * world["speed"]:
            continue
        view = turn_view(world, scene)
        _speak(world, scene, view["speaker"]["id"], scene["written"] or scripted_turn(view))


def _await_player(world: World, scene: Conversation, speaker_id: str) -> None:
    # A steered guest's due line is the player's to write (`scene["written"]`, once they have). Nobody else, scripted
    # writer included, speaks for them: when `rules.player.silence` real seconds (more game seconds at a faster speed)
    # pass with no line, the turn passes in silence.
    if scene["written"] is None and world["time"] >= scene["next_turn_at"] + (
            world["rules"]["player"]["silence"] * world["speed"]):
        _speak(world, scene, speaker_id, {"line": SILENCE_LINE, "act": "silence", "addressee": None,
                                          "topic": scene["topic"]})
    elif scene["written"] is not None:
        _speak(world, scene, speaker_id, scene["written"])


def _speak(world: World, scene: Conversation, speaker_id: str, result: Mapping[str, Any]) -> None:
    people = {item["id"]: item for item in world["actors"]}
    turn: Turn = {"speaker": speaker_id, "addressee": result["addressee"], "line": result["line"],
                  "act": result["act"], "time": world["time"]}
    if "invitation" in result:
        turn["invitation"] = result["invitation"]
    if "fact_id" in result:
        turn["fact_id"] = result["fact_id"]
    scene["turns"].append(turn)
    scene.update({"topic": result["topic"], "writing": None, "written": None,
                  "next_turn_at": world["time"] + reading_time(result["line"], world["rules"]["conversation"])})
    listener = people[result["addressee"]]["name"] if result["addressee"] else "everyone"
    spoken = log_event(world, speaker_id, "turn",
                       f"{people[speaker_id]['name']} to {listener} ({result['act']}): {result['line']}")
    spoken["act"], spoken["addressee"] = result["act"], result["addressee"]
    if result["act"] != "silence":  # Nothing was said, so nothing is noted, heard or overheard.
        note_spoken(world, scene, people[speaker_id])
        # Heard before the act takes effect, while the scene still holds everyone who spoke in it.
        hear_line(world, scene, turn)
        overhear_turn(world, scene, turn)
    effect = ACTS[result["act"]].effect
    if effect:
        effect(world, scene, people[speaker_id], people.get(result["addressee"]))
    if scene not in world["conversations"]:
        # The client shows a line over its speaker only while the scene stands; one that broke it up
        # (an insult answered with a quarrel) would vanish at once, so the log carries it instead.
        spoken["line"] = result["line"]

