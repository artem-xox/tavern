"""Aims: what a guest means by a social option (talking, walking over, joining), and when the talk has carried it out.

An aim is a kind from `AIMS`, plus a detail for the kinds that need one (which news, which invitation). The choice picks
one when it picks a social option, so the line writer knows what the guest came for; the world only checks, from what the
speaker says, whether they got round to it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.body.items import ITEMS
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.mind.hall_view import home_table_of, in_use
from tavern.mind.observation import known_objects
from tavern.social.giving import empty_handed_company
from tavern.social.invitations import KINDS
from tavern.social.names import called
from tavern.social.responses import answering
from tavern.social.scenes import Conversation, conversation_of
from tavern.social.thoughts import familiarity_of, opinion_of

# The verbs that reach a person to talk to: the ones whose choice carries an aim.
AIM_VERBS = ("talk", "approach", "join_conversation")
# An opinion this low earns a needle. It is `conversation.DISLIKED`, which this module cannot import: that module
# imports the scenes, and the scenes check their aims here (`tests/test_aims.py` pins the two together).
NEEDLED = -10.0
# Most pieces of news offered as an aim at once, the ones the guest believes most.
MOST_NEWS = 2


class SceneAim(TypedDict):
    """What a member of a scene came for: the aim, the person it is about, and whether they have said it."""

    aim: str
    about: str
    kept: bool


@dataclass(frozen=True)
class AimKind:
    """One kind of aim.

    Attributes:
        wording: How it is told; `{name}` is the person and `{what}` the detail in words.
        acts: Speech acts (`conversation.ACTS`) that carry it out.
        guidance: When the evaluator should find it natural.
        detail: What follows the kind in an aim, after a colon: `fact` (a news ID), `invitation` (a kind of
            `invitations.KINDS`), or None for none.
        invitation: The invitation an `invite` must name to carry it out, for a kind with a fixed one.
    """

    wording: str
    acts: tuple[str, ...]
    guidance: str
    detail: str | None = None
    invitation: str | None = None


AIMS: Mapping[str, AimKind] = MappingProxyType({
    "pass_time": AimKind("pass the time with {name}", ("small_talk", "joke", "remark"),
                         "The ordinary reason to talk: nothing in particular, and company."),
    "tell_news": AimKind("tell {name} the news of {what}", ("share_news",),
                         "Natural for someone who carries news and has not yet passed it on; more so to a listener "
                         "who would care.", detail="fact"),
    "invite": AimKind("invite {name} to {what}", ("invite",),
                      "Natural when they want what the invitation offers, and the person is someone they get on with.",
                      detail="invitation"),
    "win_over": AimKind("make a good impression on {name}", ("introduce", "compliment", "small_talk"),
                        "Natural with someone they hardly know and have no quarrel with."),
    "needle": AimKind("needle {name}, whom they dislike", ("insult", "complain", "disagree"),
                      "Only for someone they think ill of, and more for the hot-tempered and the drunk."),
    "have_it_out": AimKind("have it out with {name}", ("complain", "insult", "disagree"),
                           "Natural when that person has just done them wrong and they are not ready to let it pass."),
    "thank": AimKind("thank {name}", ("compliment", "agree"),
                     "Natural when that person has just been kind to them."),
    "rematch": AimKind("ask {name} for a rematch at dice", ("invite",),
                       "Natural for someone who has just lost at dice and wants another go.",
                       invitation="dice_together"),
})

# What a fresh thought that calls for an answer (`responses.RESPONSES`) makes a guest mean by it.
ANSWER_AIMS: Mapping[str, str] = MappingProxyType({
    **dict.fromkeys(("seat_taken", "table_intruded", "line_cut", "insulted", "quarrel", "friend_insulted", "let_down",
                     "shoved"), "have_it_out"),
    "lost_at_dice": "rematch",
    **dict.fromkeys(("treated", "gifted", "cared_for", "kept_word"), "thank"),
})


def offered_aims(observation: Mapping[str, Any], action: Mapping[str, Any]) -> list[str]:
    """List what a guest might mean by a social option.

    Args:
        observation: The guest's observation, with the people in sight and the time.
        action: A `talk`, `approach` or `join_conversation` action aimed at someone.

    Returns:
        Aims, `pass_time` first: the news they hold (the two they believe most), what they could invite the person
        to, winning over a stranger or acquaintance they do not dislike, a needle for someone they do, and, while
        a fresh thought about that person calls for an answer, what they mean by answering it.

    Raises:
        ValueError: The action is not an aim verb.
    """
    if action["verb"] not in AIM_VERBS:
        raise ValueError(f"Only {', '.join(AIM_VERBS)} carry an aim, not {action['verb']!r}")
    actor, now, other = observation["actor"], observation.get("time", -math.inf), action["target_id"]
    facts = actor.get("knowledge", {}).get("facts", {})
    news = sorted(facts, key=lambda fact_id: (-facts[fact_id]["confidence"], fact_id))[:MOST_NEWS]
    opinion = opinion_of(actor, other, now)
    aims = ["pass_time", *(f"tell_news:{fact_id}" for fact_id in news),
            *(f"invite:{kind}" for kind in _invitations(observation, other))]
    if opinion <= NEEDLED:
        aims.append("needle")
    elif opinion >= 0 and familiarity_of(actor, other) != "friend":
        aims.append("win_over")
    return [*aims, *_answers(observation, action, now)]


def _answers(observation: Mapping[str, Any], action: Mapping[str, Any], now: float) -> list[str]:
    thought = answering(observation["actor"], now, action)
    if thought is None:
        return []
    aim = ANSWER_AIMS[thought["kind"]]
    return [aim] if aim != "rematch" or _free_dice(observation) else []


def _free_dice(observation: Mapping[str, Any]) -> bool:
    # A dice table they know, with no game seen under way.
    return any(item["kind"] == "dice_table" and len((item.get("game") or {}).get("players", [])) < 2
               for item in known_objects(observation))


def _invitations(observation: Mapping[str, Any], other: str) -> list[str]:
    # What they could ask this person to do, as far as they can tell; the scene decides whether it may be said.
    actor, objects = observation["actor"], known_objects(observation)
    known = {item["kind"] for item in objects}
    home = home_table_of(observation)
    person: Mapping[str, Any] = next((item for item in observation.get("people", []) if item["id"] == other), {})
    free_hand = actor["inventory"].get("beer", 0) < ITEMS["beer"].hands
    stocked = any(item["kind"] == "tap" and item.get("stock") for item in objects)
    room = home is not None and any(item.get("table_id") == home and item["kind"] == "chair"
                                    and not in_use(observation, item) for item in objects)
    wishes = (("darts_together", "darts" in known), ("dice_together", _free_dice(observation)),
              ("buy_drink", free_hand and stocked and other in empty_handed_company(observation)),
              ("join_table", room and person.get("table_id") != home))
    return [kind for kind, possible in wishes if possible]


def aim_words(aim: str, name: str, topics: Mapping[str, str]) -> str:
    """Tell an aim in words.

    Args:
        aim: A checked aim.
        name: The person, as the guest calls them.
        topics: The topic of each piece of news the guest holds, by ID.

    Returns:
        For example "ask Bea for a rematch at dice".
    """
    kind, _, detail = aim.partition(":")
    what = topics[detail] if AIMS[kind].detail == "fact" else KINDS[detail] if AIMS[kind].detail else ""
    return AIMS[kind].wording.format(name=name, what=what)


def aim_candidates(action: Mapping[str, Any], aims: Sequence[str]) -> list[dict[str, Any]]:
    """List the options of the third stage of a choice, one per aim.

    Args:
        action: The social action chosen.
        aims: Its aims, from `offered_aims`.

    Returns:
        Candidates `{id, verb, target_id, aim}`, with the ID `<aim>@<action ID>`, which the evaluator scores.
    """
    return [{"id": f"{aim}@{action['id']}", "verb": action["verb"], "target_id": action["target_id"], "aim": aim}
            for aim in aims]


def carried_out(aim: str, speaker_id: str, turns: Sequence[Mapping[str, Any]]) -> bool:
    """Tell whether a speaker has said what their aim set out to.

    Args:
        aim: A checked aim.
        speaker_id: The speaker.
        turns: The scene's lines so far.

    Returns:
        True when one of their lines uses an act of the aim; for news, naming that fact, and for an invitation,
        that kind.
    """
    kind, _, detail = aim.partition(":")
    spec = AIMS[kind]
    wanted = detail if spec.detail == "invitation" else spec.invitation
    return any(turn["speaker"] == speaker_id and turn["act"] in spec.acts
               and (spec.detail != "fact" or turn.get("fact_id") == detail)
               and (wanted is None or turn.get("invitation") == wanted) for turn in turns)


def check_aim(aim: Any) -> None:
    """Check an aim from outside the choice (a saved action, a scene).

    Args:
        aim: The aim.

    Raises:
        ValueError: It is not text of a kind in `AIMS`, with a detail exactly when the kind takes one and the detail
            an invitation kind where it must be.
    """
    kind, _, detail = aim.partition(":") if isinstance(aim, str) else ("", "", "")
    spec = AIMS.get(kind)
    if spec is None or bool(detail) != (spec.detail is not None) or (spec.detail == "invitation" and detail not in KINDS):
        raise ValueError(f"Invalid aim {aim!r}")



def _topics(actor: Mapping[str, Any]) -> dict[str, str]:
    return {fact_id: fact["topic"] for fact_id, fact in actor.get("knowledge", {}).get("facts", {}).items()}


def _words(world: Mapping[str, Any], guest: Mapping[str, Any], entry: SceneAim) -> str:
    about = find_actor(world, entry["about"])
    if about is None:
        raise ValueError(f"{guest['name']}'s aim is about {entry['about']!r}, who is not in the hall")
    return aim_words(entry["aim"], called(guest, about), _topics(guest))


def begin_aim(world: World, actor: Actor, about: Mapping[str, Any]) -> None:
    """Note what a visitor came to a scene for, when their action carried an aim.

    Args:
        world: World whose event log is appended to.
        actor: Visitor who has just opened or joined a scene by `talk`, `approach` or `join_conversation`; the scene
            keeps the aim beside the others (`aims`, by speaker).
        about: The person the action was aimed at.

    Raises:
        ValueError: The action carries an aim but the visitor is in no scene.
    """
    aim = (actor.get("action") or {}).get("aim")
    if aim is None:
        return
    scene = conversation_of(world, actor["id"])
    if scene is None:
        raise ValueError(f"{actor['name']} came for {aim!r} but is in no conversation")
    entry = SceneAim(aim=aim, about=about["id"], kept=False)
    scene.setdefault("aims", {})[actor["id"]] = entry
    record_event(world, actor, "aim_set", f"{actor['name']} means to {_words(world, actor, entry)} ({aim})")


def aim_of(scene: Mapping[str, Any], actor_id: str) -> SceneAim | None:
    """Find what a member of a scene came for.

    Args:
        scene: A scene.
        actor_id: A visitor.

    Returns:
        Their aim in this scene, or None for no aim or someone who is not a member.
    """
    return scene.get("aims", {}).get(actor_id) if actor_id in scene["participants"] else None


def aim_view(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> dict[str, Any] | None:
    """Describe a speaker's aim for a line writer.

    Args:
        world: Current world.
        scene: The speaker's scene.
        speaker: The speaker.

    Returns:
        `id`, `words` (as the speaker would say what they came for), the `acts` that carry it out, the `detail` an
        act must name (the news ID or the invitation kind, else None) and whether it is `done`; None when they came
        with no aim.
    """
    entry = aim_of(scene, speaker["id"])
    if entry is None:
        return None
    kind, _, detail = entry["aim"].partition(":")
    return {"id": entry["aim"], "words": _words(world, speaker, entry), "acts": list(AIMS[kind].acts),
            "detail": detail or AIMS[kind].invitation, "done": entry["kept"]}


def note_spoken(world: World, scene: Conversation, speaker: Actor) -> None:
    """Note, once, that a speaker has said what they came for.

    Args:
        world: World whose event log is appended to.
        scene: The scene, whose latest line has just been spoken.
        speaker: Who spoke it.
    """
    entry = aim_of(scene, speaker["id"])
    if entry is None or entry["kept"] or not carried_out(entry["aim"], speaker["id"], scene["turns"]):
        return
    entry["kept"] = True
    record_event(world, speaker, "aim_kept", f"{speaker['name']} got round to it: {_words(world, speaker, entry)} "
                                              f"({entry['aim']})")


def check_saved_aims(world: Mapping[str, Any]) -> None:
    """Check the aims in a saved world: the actions that carry one and the scenes that keep them.

    Args:
        world: Decoded save.

    Raises:
        ValueError: An aim is not one, is on an action that takes none, or a scene's aims are malformed or name
            someone who is not a member or not in the hall.
    """
    people = {actor["id"] for actor in world["actors"]}
    for actor in world["actors"]:
        action = actor.get("action")
        if action is not None and "aim" in action:
            check_aim(action["aim"])
            if action["verb"] not in AIM_VERBS:
                raise ValueError(f"Invalid saved aim on {action['verb']!r}")
    for scene in world["conversations"]:
        aims = scene.get("aims", {})
        if not isinstance(aims, dict):
            raise ValueError("Invalid saved scene aims")
        for speaker, entry in aims.items():
            if speaker not in scene["participants"] or not isinstance(entry, dict) \
                    or set(entry) != set(SceneAim.__annotations__) or entry["about"] not in people \
                    or not isinstance(entry["kept"], bool):
                raise ValueError(f"Invalid saved scene aim of {speaker!r}")
            check_aim(entry["aim"])
