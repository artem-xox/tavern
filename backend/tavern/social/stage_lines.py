"""Lines on and at the stage: what waits for a writer, the writer port, and speaking what it wrote.

Nothing here is saved: what is owed is read from the world each tick. A performer on the stage with no number given
since they climbed up is owed one (`speeches.on_stage_for`); a number that names a `heckler_id` is owed a heckle for
`HECKLE_WITHIN` seconds, and a heckle is owed a comeback as long. A runner asks its writer once per claim key and
hands the answer to `deliver_stage`, which speaks it if it is still owed, or scripted words if the writer failed.
"""

from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any, TypedDict

from tavern.body.dozing import asleep
from tavern.body.drunkenness import speech_instruction
from tavern.hall.chance import roll
from tavern.hall.state import Actor, World
from tavern.mind.briefing import recollections
from tavern.mind.cards import TEXT_FIELDS, persona_words
from tavern.mind.feelings import feelings
from tavern.mind.portrait import portrait
from tavern.social.heckles import answer_heckle, heckle, scripted_comeback, scripted_heckle
from tavern.social.names import as_known, called
from tavern.social.numbers import NUMBERS, scripted_number
from tavern.social.speeches import number_for, on_stage_for, perform
from tavern.social.thoughts import opinion_of

# Game seconds after a number during which its heckler may still shout, and after a heckle during which the performer
# may still answer: past that the room has moved on.
HECKLE_WITHIN = 12.0
# The latest of the speaker's own memories a writer is shown, oldest first.
RECALLED = 8

# Asks for the lines of a claim from its view and the runner's config; the words, one or more lines.
StageWriter = Callable[[Mapping[str, Any], Mapping[str, Any]], Coroutine[Any, Any, list[str]]]


class StageClaim(TypedDict):
    """Words owed on or at the stage: what for (`number`, `heckle`, `comeback`), a key that names it for as long as it
    is owed, and the view a writer answers."""

    key: tuple[str, str, float]
    kind: str
    view: dict[str, Any]


def stage_claims(world: Mapping[str, Any]) -> list[StageClaim]:
    """List the words owed on and at the stage now: numbers, then heckles, then comebacks.

    Args:
        world: Current world; it is not modified.

    Returns:
        One claim per performer waiting on the stage, per number whose heckler has not shouted yet, and per heckle
        not answered yet, while the one to speak is in the hall and awake.
    """
    people = {item["id"]: item for item in world["actors"]}
    owed: list[StageClaim] = []
    for actor in world["actors"]:
        since = on_stage_for(world, actor)
        if since is not None:
            owed.append(_number_claim(world, actor, round(world["time"] - since, 3)))
    for event in _recent(world, "gave_speech"):
        heckler, performer = people.get(event.get("heckler_id") or ""), people.get(event["actor_id"])
        if heckler and performer and not asleep(heckler) and not _answered(world, event, "heckled", "performer_id"):
            owed.append(_answer_claim(world, "heckle", heckler, performer, event))
    for event in _recent(world, "heckled"):
        heckler, performer = people.get(event["actor_id"]), people.get(event["performer_id"])
        if heckler and performer and not asleep(performer) and not _answered(world, event, "heckle_answered",
                                                                             "heckler_id"):
            owed.append(_answer_claim(world, "comeback", performer, heckler, event))
    return owed


def _recent(world: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    return [item for item in world["events"] if item["type"] == kind and world["time"] - item["time"] <= HECKLE_WITHIN]


def _answered(world: Mapping[str, Any], event: Mapping[str, Any], answer: str, field: str) -> bool:
    # Whether the event got its answer: one of the given type after it that names the event's speaker in `field`.
    return any(item["type"] == answer and item["time"] >= event["time"] and item.get(field) == event["actor_id"]
               for item in world["events"])


def _number_claim(world: Mapping[str, Any], speaker: Actor, climbed_at: float) -> StageClaim:
    # The number a performer owes: which one and at whom (`speeches.number_for`), what the writer is asked, and the
    # scripted words should it fail.
    kind, target_id = number_for(world, speaker)
    target = next((item for item in world["actors"] if item["id"] == target_id), None)
    name = called(speaker, target) if target else None
    return {"key": ("number", speaker["id"], climbed_at), "kind": "number",
            "view": {"kind": "number", "speaker": _speaker(world, speaker), "room": _room(world, speaker),
                     "number": {"kind": kind, "target_id": target_id, "target": name,
                                "brief": NUMBERS[kind].brief.format(target=name)},
                     "scripted": scripted_number(speaker, kind, name, roll(world, "speech", speaker["id"]))}}


def _answer_claim(world: Mapping[str, Any], kind: str, speaker: Actor, other: Actor,
                  event: Mapping[str, Any]) -> StageClaim:
    # A heckle owed to a number, or a comeback owed to a heckle: whom it answers and the words it answers.
    scripted = scripted_heckle(speaker, other) if kind == "heckle" else scripted_comeback(speaker, other)
    return {"key": (kind, speaker["id"], event["time"]), "kind": kind,
            "view": {"kind": kind, "speaker": _speaker(world, speaker), "room": _room(world, speaker),
                     "at": {"id": other["id"], "name": called(speaker, other),
                            "opinion": opinion_of(speaker, other["id"], world["time"])},
                     "heard": event["line"], "scripted": [scripted]}}


def _speaker(world: Mapping[str, Any], speaker: Mapping[str, Any]) -> dict[str, Any]:
    # Who speaks and how they feel, in the shape a line writer's card block reads (`haiku_turns.card_block`).
    now, card = world["time"], speaker["card"]
    return {"id": speaker["id"], "name": speaker["name"],
            "card": None if card is None else {**{key: card[key] for key in TEXT_FIELDS}, **persona_words(card)},
            "portrait": portrait(speaker), "feelings": feelings({"actor": {**speaker, "drunkenness": 0.0}, "time": now}),
            "drink": speech_instruction(speaker["drunkenness"]) or "They are sober.",
            "intention": None if speaker["intention"] is None else speaker["intention"]["intention"],
            "seen": [as_known(speaker, [*world["actors"], *world["departed"]], item)
                     for item in recollections(speaker["memory"], now)][-RECALLED:]}


def _room(world: Mapping[str, Any], speaker: Actor) -> list[dict[str, Any]]:
    # Everyone else in the hall, as the speaker knows them, and what the speaker thinks of them.
    return [{"name": called(speaker, item), "opinion": opinion_of(speaker, item["id"], world["time"])}
            for item in world["actors"] if item["id"] != speaker["id"]]


def deliver_stage(world: World, claim: StageClaim, outcome: Callable[[], Sequence[str]]) -> None:
    """Speak the words a writer wrote for a claim, if they are still owed; scripted ones if the writer failed.

    Args:
        world: World updated in place.
        claim: The claim the words answer (`stage_claims`).
        outcome: Returns the writer's lines, or raises the request's error.
    """
    due = next((item for item in stage_claims(world) if item["key"] == claim["key"]), None)
    try:
        lines = list(outcome())
    except Exception:  # Any failure of the writer leaves the scripted words, as a turn falls back to a scripted line.
        lines = due["view"]["scripted"] if due else []
    if due is None:
        return
    people = {item["id"]: item for item in world["actors"]}
    speaker = people[claim["key"][1]]
    if claim["kind"] == "number":
        # Written for the number the claim named; if the room changed it meanwhile, the scripted words of the new one.
        number, wanted = due["view"]["number"], claim["view"]["number"]
        same = (number["kind"], number.get("target_id")) == (wanted["kind"], wanted.get("target_id"))
        perform(world, speaker, number["kind"], number.get("target_id"), lines if same else due["view"]["scripted"])
    elif claim["kind"] == "heckle":
        heckle(world, speaker, people[due["view"]["at"]["id"]], lines[0])
    else:
        answer_heckle(world, speaker, people[due["view"]["at"]["id"]], lines[0])


async def write_scripted_stage(view: Mapping[str, Any], config: Mapping[str, Any]) -> list[str]:
    """Answer a stage claim with its scripted words: the writer offline, or without a key.

    Args:
        view: A claim's view (`stage_claims`).
        config: The runner's AI config; unused.

    Returns:
        The view's `scripted` lines.
    """
    return list(view["scripted"])
