"""Speech acts in a conversation scene, which of them a speaker may use now, and their outcomes.

The game-owned rule: words alone change nothing; only a line's act does (see `ACTS`).
"""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social import commitments, facts, invitations, social_acts
from tavern.social.names import called
from tavern.social.scenes import Conversation, end_conversation
from tavern.social.thoughts import CHAT, active_thoughts, opinion_of, think

# An act's effect receives the world, the scene, the speaker, and whom they addressed (None for everyone).
ActEffect = Callable[[World, Conversation, Actor, Actor | None], None]

# A speaker may insult only someone they think this little of; an insult is answered with a quarrel by
# a target who thinks as little of the speaker.
DISLIKED = -10.0


@dataclass(frozen=True)
class Act:
    """What a speech act does once spoken, and what it means to whoever writes the lines.

    Attributes:
        effect: Consequence in the world, or None for an act that changes nothing.
        meaning: When a speaker uses it and what follows, for a turn writer.
    """

    effect: ActEffect | None
    meaning: str


def _members(world: Mapping[str, Any], scene: Conversation) -> list[Actor]:
    return [item for item in world["actors"] if item["id"] in scene["participants"]]


def _relieve(world: World, scene: Conversation, speaker: Actor,
             addressee: Actor | None) -> None:
    # A friendly exchange eases everyone's wish for company, not only the speaker's, and the
    # listeners warm to the speaker (stacking is capped in `thoughts`).
    message = f"{speaker['name']} chatted about {scene['topic']}"
    for member in _members(world, scene):
        member["needs"]["social"] = max(0.0, member["needs"]["social"] - world["rules"]["conversation"]["relief"])
        if member["id"] != speaker["id"]:
            think(member, "chat", world["time"], CHAT.format(who=called(member, speaker), topic=scene["topic"]),
                  message, about=speaker)


def _tell_places(world: World, scene: Conversation, speaker: Actor,
                 addressee: Actor | None) -> None:
    for listener in _members(world, scene):
        if listener["id"] != speaker["id"]:
            _share_places(speaker, listener)
    _relieve(world, scene, speaker, addressee)


def _tell_news(world: World, scene: Conversation, speaker: Actor,
               addressee: Actor | None) -> None:
    facts.tell(world, scene, speaker, addressee)
    _relieve(world, scene, speaker, addressee)


def _insult(world: World, scene: Conversation, speaker: Actor,
            addressee: Actor | None) -> None:
    # An insult to everyone lands on whoever the speaker thinks least of; the rest of the company
    # resents it if they like the target. A target who already thinks ill of the speaker answers in kind,
    # which is a quarrel; one who does not is only stung (the insult itself is the next grudge).
    others = [item for item in _members(world, scene) if item["id"] != speaker["id"]]
    target = addressee or min(others, key=lambda item: opinion_of(speaker, item["id"], world["time"]))
    answers_back = opinion_of(target, speaker["id"], world["time"]) <= DISLIKED
    message = f"{speaker['name']} insulted {target['name']}"
    record_event(world, target, "insulted", message)
    think(target, "insulted", world["time"], f"{called(target, speaker)} insulted me", message, about=speaker)
    for member in others:
        social_acts.take_offence(world, member, speaker, target)
    if answers_back:
        _quarrel(world, speaker, target, scene["topic"])
        end_conversation(world, scene, pleasant=False)


ACTS: Mapping[str, Act] = MappingProxyType({
    "greet": Act(None, "open the conversation, or welcome someone who joined it"),
    "remark": Act(None, "say something that needs no consequence, such as a question, an answer or an aside; "
                        "words alone change nothing, so it changes nothing"),
    "small_talk": Act(_relieve, "pass the time pleasantly; it eases everyone's wish for company"),
    "share_place": Act(_tell_places, "tell the others where the tap, the WC or the darts are; they learn "
                                     "every such place the speaker knows, and it eases the wish for company"),
    "share_news": Act(_tell_news, "tell the others a piece of news the speaker holds, naming it in `fact_id`; the "
                                  "words spoken are the version the others will carry on, so retell it in the "
                                  "speaker's own words without adding facts. It eases everyone's wish for company"),
    "joke": Act(_relieve, "make the others laugh; it eases everyone's wish for company, and the laughter "
                          "carries across the hall"),
    "complain": Act(None, "grumble about something; it changes nothing by itself, though a grumble about someone "
                          "may be followed by an insult"),
    # The speaker leaves once the line is heard (`scenes.check_conversations`), not as it is spoken.
    "leave_conversation": Act(None, "say goodbye and leave; the others carry on while two remain"),
    "introduce": Act(social_acts.introduce, "tell the others the speaker's name; until then strangers know "
                                            "them only by their looks. Strangers become acquaintances"),
    "compliment": Act(social_acts.compliment, "praise the addressee (everyone, if nobody in particular); it "
                                              "lifts their mood and warms them to the speaker"),
    "boast": Act(social_acts.boast, "brag about the speaker's own deeds; patient listeners, and those who "
                                    "like the speaker, are mildly impressed, impatient ones mildly put off"),
    "insult": Act(_insult, "insult the addressee, someone the speaker dislikes; it sours their mood and their "
                           "opinion of the speaker, offends anyone nearby who likes them, rings out across "
                           "the hall; if the addressee already thinks ill of the speaker it is answered in kind, "
                           "a quarrel that ends the conversation"),
    "apologize": Act(social_acts.apologize, "apologize to the addressee (everyone, if nobody in particular) "
                                            "for a wrong; it halves the latest grudge each holds against the "
                                            "speaker and warms them a little to the speaker"),
    "agree": Act(social_acts.agree, "agree with the addressee (or whoever spoke last); they think a little "
                                    "better of the speaker"),
    "disagree": Act(social_acts.disagree, "disagree with the addressee (or whoever spoke last); they think a "
                                          "little worse of the speaker"),
    "invite": Act(invitations.invite, "invite the addressee to do something together, naming one of the "
                                      "offered `invitation` kinds: join_table (come and sit at the speaker's "
                                      "table), darts_together (play darts together), dice_together (play a "
                                      "game of dice at the dice table), buy_drink (the speaker "
                                      "fetches them an ale), leave_together (walk home together), move_together "
                                      "(move to a free table of their own together). It waits "
                                      "for the addressee's answer"),
    "promise": Act(commitments.promise, "promise the addressee, someone with a table of their own, to come and sit "
                                        "with them there soon; the game checks it, and the addressee thinks the better "
                                        "of the speaker for a promise kept and the worse for one broken. Make it "
                                        "only if the speaker means to do it, and say it plainly"),
    "accept": Act(invitations.accept, "accept the invitation waiting for the speaker; the game then sets "
                                      "both moving, which ends their part in the conversation"),
    "decline": Act(invitations.decline, "decline the invitation waiting for the speaker; nothing follows"),
})


def offered_acts(world: Mapping[str, Any], scene: Conversation, speaker: Mapping[str, Any]) -> dict[str, str]:
    """List the acts a speaker may use on their turn, with their meanings, for a turn writer.

    Args:
        world: Current world.
        scene: Speaker's scene.
        speaker: Visitor about to speak.

    Returns:
        Meaning per act, in `ACTS` order. Always offered: greet, remark, small talk, places,
        jokes, complaints, goodbye, compliments, boasts, agreeing and disagreeing. `introduce`
        while someone present knows the speaker only by their looks; `insult` while the
        speaker thinks `DISLIKED` or less of someone present; `apologize` while someone holds
        a grudge against them; `invite` while an invitation kind is possible and none is
        pending; `promise` while someone present has a table the speaker is not at and nothing is promised them; `accept` and `decline` while an invitation waits for their answer; `share_news`
        while they hold any news.
    """
    others = [item for item in _members(world, scene) if item["id"] != speaker["id"]]
    now, waiting = world["time"], invitations.pending_for(scene, speaker["id"])
    if waiting is not None and "answer" in waiting:
        # The invitee has decided (`invitations.answer_options`): the line says it, and nothing else.
        act = invitations.answer_act(waiting["answer"])
        return {act: ACTS[act].meaning}
    asked = waiting is not None
    situational = {
        "introduce": any(called(item, speaker) != speaker["name"] for item in others),
        "insult": any(opinion_of(speaker, item["id"], now) <= DISLIKED for item in others),
        "apologize": any(thought["about"] == speaker["id"] and thought["opinion"] < 0
                         for item in others for thought in active_thoughts(item["thoughts"], now)),
        "share_news": bool(speaker["knowledge"]["facts"]),
        "invite": bool(invitations.offered_kinds(world, scene, speaker)),
        "promise": any(commitments.promisable(world, speaker, item) for item in others),
        "accept": asked, "decline": asked}
    return {name: act.meaning for name, act in ACTS.items() if situational.get(name, True)}


def _quarrel(world: World, actor: Actor, partner: Actor, topic: str) -> None:
    message = f"{actor['name']} and {partner['name']} quarreled about {topic}"
    for visitor, other in ((actor, partner), (partner, actor)):
        record_event(world, visitor, "quarrel", message)
        think(visitor, "quarrel", world["time"], f"Quarreled with {called(visitor, other)} about {topic}", message,
              about=other)


def _share_places(speaker: Mapping[str, Any], listener: Actor) -> None:
    for identifier, known in speaker["knowledge"]["objects"].items():
        if known["kind"] not in ("tap", "toilet", "darts") or identifier in listener["knowledge"]["objects"]:
            continue
        listener["knowledge"]["objects"][identifier] = {**deepcopy(known), "heard_from": speaker["id"]}
