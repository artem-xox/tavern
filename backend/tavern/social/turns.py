"""Turns in a conversation scene: the turn writer port, what a writer sees, and when lines are spoken.

The world owns timing: a scene's next line is due at `next_turn_at`, the previous line's reading
time after it was spoken. A runner may claim the next turn (`claim_turns`) as soon as the previous
line is spoken, ask its writer asynchronously, and hand the answer back (`deliver_turn`); the world
speaks it when due. An unclaimed turn is written by the scripted writer on the spot, and a claimed
one that has no answer `rules.conversation.turn_timeout` seconds after it was due too.
"""

from collections.abc import Callable, Coroutine, Mapping
from copy import deepcopy
from typing import Any, NotRequired, TypedDict

from tavern.body.wounds import hurt
from tavern.hall.closing import closing_called
from tavern.hall.memory import log_event
from tavern.hall.staff import on_staff, post_of
from tavern.hall.state import World
from tavern.mind.briefing import recollections
from tavern.mind.cards import TEXT_FIELDS
from tavern.mind.feelings import feelings
from tavern.mind.portrait import portrait
from tavern.mind.scripted import scripted_turn
from tavern.social.aims import aim_view, note_spoken
from tavern.social.conversation import ACTS, offered_acts
from tavern.social.facts import carried
from tavern.social.heard import earlier_lines, hear_line
from tavern.social.invitations import offered_kinds, pending_for
from tavern.social.names import as_known, called, knows_name, looks
from tavern.social.overhearing import overhear_turn
from tavern.social.scenes import Conversation, Turn, awaits_company_change
from tavern.social.thoughts import active_thoughts, familiarity_of, opinion_of, words_on_mind


class TurnResult(TypedDict):
    """A written line: the words, the speech act (one of `conversation.ACTS`), whom it addresses
    (another participant, or None for everyone), and the topic the scene moves on to. An
    `invite` also names its `invitation` kind (one of the view's `invitations`), and a `share_news` the
    `fact_id` of the news it tells (one of the speaker's `news`)."""

    line: str
    act: str
    addressee: str | None
    topic: str
    invitation: NotRequired[str]
    fact_id: NotRequired[str]


# Writes the next line of a scene from the speaker's view (see `turn_view`) and the AI config.
# `scripted.write_scripted_turn` is the offline writer; E16 adds Claude Haiku. Any failure it
# raises falls back to a scripted line.
TurnWriter = Callable[[Mapping[str, Any], Mapping[str, Any]], Coroutine[Any, Any, TurnResult]]

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
        `_participants`), every turn spoken in it so far and the pending `invitation`, if any;
        `speaker`: their ID, name, needs, traits, visit, the places they could tell about (tap,
        WC, darts), their `opinions` of the others, `earlier`, everything they still remember saying and hearing
        in other scenes tonight (`heard.earlier_lines`), and `seen`, what they did and what befell them
        (`briefing.recollections`, naming people as they know them); `acts`: the meaning of each act offered
        now (`conversation.offered_acts`); `invitations`: the kinds an `invite` may name;
        `seed`: the evening's seed, for a writer's seeded choices; `closing_called`: whether the barkeep has called
        closing time, so a speaker winds the talk down. Also who they are and how they feel (see `_mind`).

    Raises:
        KeyError: The speaker's record lacks a field the view reads.
    """
    people = {item["id"]: item for item in world["actors"]}
    speaker = people[next_speaker(scene)]
    places = [{key: item[key] for key in ("id", "kind", "name")} for _, item in
              sorted(speaker["knowledge"]["objects"].items()) if item["kind"] in ("tap", "toilet", "darts")]
    view = {"conversation": {"id": scene["id"], "topic": scene["topic"], "turn": len(scene["turns"]),
                             "participants": _participants(world, scene, speaker),
                             "turns": deepcopy(scene["turns"])},
            "speaker": {"id": speaker["id"], "name": speaker["name"], **deepcopy(
                {key: speaker[key] for key in ("needs", "traits", "visit")}), "places": places,
                         **_mind(world, scene, speaker)},
            "acts": offered_acts(world, scene, speaker), "seed": world["seed"],
            "closing_called": closing_called(world)}
    if on_staff(speaker):
        view["speaker"]["on_duty"] = post_of(world["map"], speaker)["name"]
    view["speaker"]["aim"] = aim_view(world, scene, speaker)
    _add_invitations(view, world, scene, speaker)
    return view


def _participants(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> list[dict[str, Any]]:
    # Everyone in the scene as the speaker knows them: `name` is their looks until the speaker
    # knows their name (`known`), see `tavern.social.names`.
    people = {item["id"]: item for item in world["actors"]}
    return [{"id": actor_id, "name": called(speaker, people[actor_id]),
             "known": knows_name(speaker, people[actor_id]) or looks(people[actor_id]) is None,
             # Only staff carry the flag: someone at work behind a bar, who invites and is invited by nobody.
             **({"on_duty": True} if on_staff(people[actor_id]) else {})}
            for actor_id in scene["participants"]]


def _add_invitations(view: dict[str, Any], world: Mapping[str, Any], scene: Conversation,
                     speaker: Mapping[str, Any]) -> None:
    # The pending invitation, the kinds the speaker may offer, and how they regard the others,
    # which invitations and insults depend on.
    view["conversation"]["invitation"] = deepcopy(scene["invitation"])
    waiting = pending_for(scene, speaker["id"])
    answer = None if waiting is None else waiting.get("answer")
    # An invitee who decided to counter may offer that kind and no other.
    view["invitations"] = ([answer.partition(":")[2]] if answer and answer.startswith("counter:")
                           else [] if answer else offered_kinds(world, scene, speaker))
    view["answer"] = answer
    view["speaker"]["opinions"] = {item: opinion_of(speaker, item, world["time"])
                                   for item in scene["participants"] if item != speaker["id"]}


def _mind(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> dict[str, Any]:
    # Who the speaker is and how they feel, for a model writer: `card` (the card's words, or None),
    # `portrait`, `feelings` in words, their current `intention` (the mind's words, or None), `aims_at` (whom their active goal is about, or None), `drunkenness` (0–1; kept out of `feelings`, so a writer
    # words it once), whether they came in unwell (`ailing`), and `company`: whether each other participant looks
    # unwell, and the speaker's opinion of, familiarity with, and active thoughts about them, in order of joining.
    now, card = world["time"], speaker["card"]
    others = [item for item in world["actors"] if item["id"] in scene["participants"] and item["id"] != speaker["id"]]
    others.sort(key=lambda item: scene["participants"].index(item["id"]))
    thoughts = active_thoughts(speaker["thoughts"], now)
    return {"card": None if card is None else {key: card[key] for key in TEXT_FIELDS},
            "portrait": portrait(speaker),
            "feelings": feelings({"actor": {**speaker, "drunkenness": 0.0}, "time": now}),
            "drunkenness": speaker["drunkenness"], "ailing": speaker["ailing"], "hurt": hurt(speaker),
            "just_fought": _just_fought(world, speaker, others),
            "intention": None if speaker["intention"] is None else speaker["intention"]["intention"],
            "aims_at": _aims_at(speaker),
            "earlier": earlier_lines(speaker, world["rules"]["conversation"]["recall_lines"], scene["id"]),
            "seen": [as_known(speaker, [*world["actors"], *world["departed"]], item) for item in recollections(speaker["memory"], now)],
            "news": carried(world, speaker),
            "company": [{"id": other["id"], "name": other["name"], "ailing": other["ailing"], "hurt": hurt(other),
                         "opinion": opinion_of(speaker, other["id"], now),
                         "familiarity": familiarity_of(speaker, other["id"]),
                         "thoughts": words_on_mind([item for item in thoughts if item["about"] == other["id"]],
                                                   called(speaker, other))}
                        for other in others]}


def _just_fought(world: Mapping[str, Any], speaker: Mapping[str, Any], others: list[Mapping[str, Any]]) -> list[str]:
    # The IDs, in the scene's order, of those here whom the speaker fought within the last two minutes.
    ids = {other["id"] for other in others}
    return [other["id"] for other in others if any(
        fight["outcome"] is not None and speaker["id"] in (fight["a"], fight["b"]) and other["id"] in (fight["a"], fight["b"])
        and other["id"] in ids and world["time"] - fight["ended_at"] <= 120.0 for fight in world["fights"])]


def _aims_at(speaker: Mapping[str, Any]) -> str | None:
    # The guest the speaker's active goal is about, or None.
    goal = speaker["intention"]["goal"] if speaker["intention"] is not None else None
    return goal["target"] if goal is not None and goal["status"] == "active" else None


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
        if scene["writing"] is None and scene["written"] is None and not awaits_company_change(world, scene):
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
        log_event(world, None, "turn_failed",
             f"A line for {view['speaker']['name']} failed ({error}); a scripted one stands in")


def speak_turns(world: World) -> None:
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
    log_event(world, speaker_id, "turn", f"{people[speaker_id]['name']} to {listener} ({result['act']}): {result['line']}")
    note_spoken(world, scene, people[speaker_id])
    # Heard before the act takes effect, while the scene still holds everyone who spoke in it.
    hear_line(world, scene, turn)
    overhear_turn(world, scene, turn)
    effect = ACTS[result["act"]].effect
    if effect:
        effect(world, scene, people[speaker_id], people.get(result["addressee"]))

