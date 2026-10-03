"""Turns in a conversation scene: the turn writer port, what a writer sees, and when lines are spoken.

The world owns timing: a scene's next line is due at `next_turn_at`, the previous line's reading
time after it was spoken. A runner may claim the next turn (`claim_turns`) as soon as the previous
line is spoken, ask its writer asynchronously, and hand the answer back (`deliver_turn`); the world
speaks it when due. An unclaimed turn is written by the scripted writer on the spot, and a claimed
one that has no answer `rules.conversation.turn_timeout` seconds after it was due too.
"""

from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from typing import Any, NotRequired, TypedDict

from tavern.cards import TEXT_FIELDS
from tavern.conversation import ACTS, offered_acts
from tavern.feelings import feelings
from tavern.invitations import offered_kinds
from tavern.names import called, knows_name, looks
from tavern.overhearing import overhear_turn
from tavern.portrait import portrait
from tavern.scenes import Conversation, Turn
from tavern.scripted import scripted_turn
from tavern.thoughts import active_thoughts, familiarity_of, opinion_of


class TurnResult(TypedDict):
    """A written line: the words, the speech act (one of `conversation.ACTS`), whom it addresses
    (another participant, or None for everyone), and the topic the scene moves on to. An
    `invite` also names its `invitation` kind (one of the view's `invitations`)."""

    line: str
    act: str
    addressee: str | None
    topic: str
    invitation: NotRequired[str]


# Writes the next line of a scene from the speaker's view (see `turn_view`) and the AI config.
# `scripted.write_scripted_turn` is the offline writer; E16 adds Claude Haiku. Any failure it
# raises falls back to a scripted line.
TurnWriter = Callable[[Mapping[str, Any], Mapping[str, Any]], Awaitable[TurnResult]]

_FIELDS = {"line", "act", "addressee", "topic"}


def reading_time(line: str, rules: Mapping[str, Any]) -> float:
    """Tell how long the others take to hear out a line before the next one.

    Args:
        line: Spoken words.
        rules: `min_gap` seconds and `chars_per_second` of `rules.conversation`.

    Returns:
        max(min_gap, characters / chars_per_second), in game seconds.
    """
    return max(rules["min_gap"], len(line) / rules["chars_per_second"])


def next_speaker(scene: Conversation) -> str:
    """Tell who speaks next in a scene.

    Args:
        scene: Scene with at least one participant.

    Returns:
        Whoever the last line addressed, if still there and not its speaker; otherwise the
        participant after the last speaker, in order of joining; and the starter for the first
        line, or after the last speaker left.
    """
    people = scene["participants"]
    if not scene["turns"]:
        return people[0]
    last = scene["turns"][-1]
    if last["addressee"] in people and last["addressee"] != last["speaker"]:
        return last["addressee"]
    if last["speaker"] in people:
        return people[(people.index(last["speaker"]) + 1) % len(people)]
    return people[0]


def turn_view(world: Mapping[str, Any], scene: Conversation) -> dict[str, Any]:
    """Describe a scene from the next speaker's point of view, for a turn writer.

    Args:
        world: Current world.
        scene: Scene whose next turn is written.

    Returns:
        `conversation`: ID, topic, index of the turn being written, participants (see
        `_participants`), the latest eight turns and the pending `invitation`, if any;
        `speaker`: their ID, name, needs, traits, visit, the places they could tell about (tap,
        WC, darts) and their `opinions` of the others; `acts`: the meaning of each act offered
        now (`conversation.offered_acts`); `invitations`: the kinds an `invite` may name;
        `seed`: the evening's seed, for a writer's seeded choices. Also who they are and how they feel (see `_mind`).

    Raises:
        KeyError: The speaker's record lacks a field the view reads.
    """
    people = {item["id"]: item for item in world["actors"]}
    speaker = people[next_speaker(scene)]
    places = [{key: item[key] for key in ("id", "kind", "name")} for _, item in
              sorted(speaker["knowledge"]["objects"].items()) if item["kind"] in ("tap", "toilet", "darts")]
    view = {"conversation": {"id": scene["id"], "topic": scene["topic"], "turn": len(scene["turns"]),
                             "participants": _participants(world, scene, speaker),
                             "turns": deepcopy(scene["turns"][-8:])},
            "speaker": {"id": speaker["id"], "name": speaker["name"], **deepcopy(
                {key: speaker[key] for key in ("needs", "traits", "visit")}), "places": places,
                         **_mind(world, scene, speaker)},
            "acts": offered_acts(world, scene, speaker), "seed": world["seed"]}
    _add_invitations(view, world, scene, speaker)
    return view


def _participants(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> list[dict[str, Any]]:
    # Everyone in the scene as the speaker knows them: `name` is their looks until the speaker
    # knows their name (`known`), see `tavern.names`.
    people = {item["id"]: item for item in world["actors"]}
    return [{"id": actor_id, "name": called(speaker, people[actor_id]),
             "known": knows_name(speaker, people[actor_id]) or looks(people[actor_id]) is None}
            for actor_id in scene["participants"]]


def _add_invitations(view: dict[str, Any], world: Mapping[str, Any], scene: Conversation,
                     speaker: Mapping[str, Any]) -> None:
    # The pending invitation, the kinds the speaker may offer, and how they regard the others,
    # which invitations and insults depend on.
    view["conversation"]["invitation"] = deepcopy(scene["invitation"])
    view["invitations"] = offered_kinds(world, scene, speaker)
    view["speaker"]["opinions"] = {item: opinion_of(speaker, item, world["time"])
                                   for item in scene["participants"] if item != speaker["id"]}


def _mind(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> dict[str, Any]:
    # Who the speaker is and how they feel, for a model writer: `card` (the card's words, or None),
    # `portrait`, `feelings` in words, `drunkenness` (0–1; kept out of `feelings`, so a writer
    # words it once), and `company`: their opinion of, familiarity with, and active thoughts
    # about each other participant, in order of joining.
    now, card = world["time"], speaker["card"]
    others = [item for item in world["actors"] if item["id"] in scene["participants"] and item["id"] != speaker["id"]]
    others.sort(key=lambda item: scene["participants"].index(item["id"]))
    thoughts = active_thoughts(speaker["thoughts"], now)
    return {"card": None if card is None else {key: card[key] for key in TEXT_FIELDS},
            "portrait": portrait(speaker),
            "feelings": feelings({"actor": {**speaker, "drunkenness": 0.0}, "time": now}),
            "drunkenness": speaker["drunkenness"],
            "company": [{"id": other["id"], "name": other["name"], "opinion": opinion_of(speaker, other["id"], now),
                         "familiarity": familiarity_of(speaker, other["id"]),
                         "thoughts": [item["text"] for item in thoughts if item["about"] == other["id"]]}
                        for other in others]}


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
            offered now; it addresses the speaker or someone not in the scene; or an `invite`
            addresses nobody or names a kind not offered.
    """
    if not isinstance(result, Mapping) or set(result) - {"invitation"} != _FIELDS:
        raise ValueError(f"A turn has exactly the fields {sorted(_FIELDS)}, not {result!r}")
    for key in ("line", "topic"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError(f"A turn's {key} must be nonempty text, not {result[key]!r}")
    if result["act"] not in view["acts"]:
        raise ValueError(f"Unknown speech act {result['act']!r}, or not one offered now")
    others = {item["id"] for item in view["conversation"]["participants"]} - {view["speaker"]["id"]}
    if result["addressee"] is not None and result["addressee"] not in others:
        raise ValueError(f"{result['addressee']!r} is not someone else in the conversation")
    turn: TurnResult = {"line": result["line"], "act": result["act"], "addressee": result["addressee"],
                        "topic": result["topic"]}
    if result["act"] == "invite" or "invitation" in result:
        turn["invitation"] = _invitation(view, result)
    return turn


def _invitation(view: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    # Only an invite carries an invitation, to someone in particular, of a kind on offer.
    if result["act"] != "invite" or result["addressee"] is None:
        raise ValueError("Only an invite to someone in particular carries an invitation")
    if result.get("invitation") not in view["invitations"]:
        raise ValueError(f"Invitation {result.get('invitation')!r} is not one on offer")
    return result["invitation"]


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
        if scene["writing"] is None and scene["written"] is None:
            view = turn_view(world, scene)
            scene["writing"] = {"turn": view["conversation"]["turn"], "speaker": view["speaker"]["id"],
                                "since": world["time"]}
            claims.append((scene["id"], view["conversation"]["turn"], view))
    return claims


def deliver_turn(world: dict[str, Any], scene_id: str, turn: int, outcome: Callable[[], Any]) -> None:
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
        _log(world, None, "turn_failed",
             f"A line for {view['speaker']['name']} failed ({error}); a scripted one stands in")


def speak_turns(world: dict[str, Any]) -> None:
    """Speak every scene's line that is due, and let its act take effect.

    Args:
        world: World whose scenes, event log and visitors are updated in place.
    """
    rules = world["rules"]["conversation"]
    for scene in list(world["conversations"]):
        if scene not in world["conversations"] or world["time"] < scene["next_turn_at"]:
            continue
        awaited = scene["writing"] is not None and scene["written"] is None
        if awaited and world["time"] < scene["next_turn_at"] + rules["turn_timeout"]:
            continue
        view = turn_view(world, scene)
        _speak(world, scene, view["speaker"]["id"], scene["written"] or scripted_turn(view))


def _speak(world: dict[str, Any], scene: Conversation, speaker_id: str, result: Mapping[str, Any]) -> None:
    people = {item["id"]: item for item in world["actors"]}
    turn: Turn = {"speaker": speaker_id, "addressee": result["addressee"], "line": result["line"],
                  "act": result["act"], "time": world["time"]}
    if "invitation" in result:
        turn["invitation"] = result["invitation"]
    scene["turns"].append(turn)
    scene.update(topic=result["topic"], writing=None, written=None,
                 next_turn_at=world["time"] + reading_time(result["line"], world["rules"]["conversation"]))
    listener = people[result["addressee"]]["name"] if result["addressee"] else "everyone"
    _log(world, speaker_id, "turn", f"{people[speaker_id]['name']} to {listener} ({result['act']}): {result['line']}")
    # Heard before the act takes effect, while the scene still holds everyone who spoke in it.
    overhear_turn(world, scene, turn)
    effect = ACTS[result["act"]].effect
    if effect:
        effect(world, scene, people[speaker_id], people.get(result["addressee"]))


def _log(world: dict[str, Any], actor_id: str | None, kind: str, message: str) -> None:
    # Lines go to the event log only: a guest's own memory keeps what the scene came to.
    world["events"].append({"time": world["time"], "actor_id": actor_id, "type": kind, "message": message})
    del world["events"][:-200]
