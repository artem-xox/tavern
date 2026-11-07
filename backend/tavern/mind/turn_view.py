"""What a line writer sees of a scene: the speaker, the company, the invitations and acts on offer."""

from collections.abc import Mapping
from copy import deepcopy
import re
from typing import Any

from tavern.body.wounds import hurt
from tavern.hall.closing import closing_called
from tavern.hall.staff import on_staff, post_of
from tavern.mind.briefing import recollections
from tavern.mind.cards import card_words
from tavern.mind.feelings import feelings
from tavern.mind.portrait import portrait
from tavern.social.aims import aim_view
from tavern.social.conversation import offered_acts
from tavern.social.facts import carried
from tavern.social.heard import earlier_lines, said_lines
from tavern.social.invitations import offered_kinds, pending_for
from tavern.social.names import as_known, called, knows_name, looks
from tavern.social.quarrels import heat
from tavern.social.scenes import Conversation
from tavern.social.thoughts import active_thoughts, familiarity_of, opinion_of

_QUOTED = re.compile(r": “.*”$", re.DOTALL)  # The words a thought quotes (`conversation._insult`), at its end.


# Lines in a row a member may stay out of before they cut in on those talking past them.
CUT_IN_AFTER = 2


def _cutting_in(scene: Conversation) -> str | None:
    """Tell who cuts in on the talk now, if anyone.

    Args:
        scene: Scene with at least one participant.

    Returns:
        The first member, in order of joining, who spoke in none of the last `CUT_IN_AFTER` lines and is
        neither their last speaker nor whom the last line addressed; None while no one is left out that long.
    """
    turns = scene["turns"]
    if len(turns) < CUT_IN_AFTER:
        return None
    recent = {turn["speaker"] for turn in turns[-CUT_IN_AFTER:]}
    last = turns[-1]
    return next((member for member in scene["participants"]
                 if member not in recent and member != last["addressee"]), None)


def next_speaker(scene: Conversation) -> str:
    """Tell who speaks next in a scene.

    Args:
        scene: Scene with at least one participant.

    Returns:
        Whoever cuts in (see `_cutting_in`); otherwise whoever the last line addressed, if still there and not
        its speaker; otherwise the participant after the last speaker, in order of joining; and the starter
        for the first line, or after the last speaker left.
    """
    people = scene["participants"]
    if not scene["turns"]:
        return people[0]
    interrupter = _cutting_in(scene)
    if interrupter is not None:
        return interrupter
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
        `_participants`), every turn spoken in it so far, whether the speaker `_cutting_in` on others talking past
        them, how hot a quarrel runs (`quarrels.heat`), and the pending `invitation`, if any;
        `speaker`: their ID, name, needs, traits, visit, the places they could tell about (tap,
        WC, darts), their `opinions` of the others, `earlier`, everything they still remember saying and hearing
        in other scenes tonight (`heard.earlier_lines`), `said`, every line of their own they remember, this scene's
        included (`heard.said_lines`), and `seen`, what they did and what befell them
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
                             "turns": deepcopy(scene["turns"]), "cutting_in": _cutting_in(scene) == speaker["id"],
                             "heat": heat(scene)},
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
    # unwell, and the speaker's opinion of, familiarity with, and grudges about them (counted, never quoted), in order of joining.
    now, card = world["time"], speaker["card"]
    others = [item for item in world["actors"] if item["id"] in scene["participants"] and item["id"] != speaker["id"]]
    others.sort(key=lambda item: scene["participants"].index(item["id"]))
    thoughts = active_thoughts(speaker["thoughts"], now)
    return {"card": None if card is None else card_words(card),
            "portrait": portrait(speaker),
            "feelings": feelings({"actor": {**speaker, "drunkenness": 0.0}, "time": now}),
            "drunkenness": speaker["drunkenness"], "ailing": speaker["ailing"], "hurt": hurt(speaker),
            "just_fought": _just_fought(world, speaker, others),
            "intention": None if speaker["intention"] is None else speaker["intention"]["intention"],
            "aims_at": _aims_at(speaker),
            "earlier": earlier_lines(speaker, world["rules"]["conversation"]["recall_lines"], scene["id"]),
            "said": said_lines(speaker),
            "seen": [as_known(speaker, [*world["actors"], *world["departed"]], item) for item in recollections(speaker["memory"], now)],
            "news": carried(world, speaker),
            "company": [{"id": other["id"], "name": other["name"], "ailing": other["ailing"], "hurt": hurt(other),
                         "opinion": opinion_of(speaker, other["id"], now),
                         "familiarity": familiarity_of(speaker, other["id"]),
                         "thoughts": _grudges([item for item in thoughts if item["about"] == other["id"]])}
                        for other in others]}


def _grudges(thoughts: list[Mapping[str, Any]]) -> list[str]:
    # One entry per kind, in the order the speaker first had them: the latest wording without the words it quotes, and
    # how often. Quoted insults handed to a line writer come straight back as its next line, so the talk circles.
    kinds: dict[str, list[Mapping[str, Any]]] = {}
    for item in thoughts:
        kinds.setdefault(item["kind"], []).append(item)
    return [_QUOTED.sub("", items[-1]["text"]) + (f" ({len(items)} times)" if len(items) > 1 else "")
            for items in kinds.values()]


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
