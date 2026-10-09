"""Scripted conversation lines: the offline turn writer, choosing a speech act by a seeded rule."""

from collections.abc import Mapping
from random import Random
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # turns imports this module, so the types cross the cycle only for the checker.
    from tavern.social.turns import TurnResult

# Lines stay under 38 characters, so each reads in the minimum gap; {name} is the addressee and
# {me} the speaker.
LINES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "greet": ("Evening, {name}!", "Well met, {name}.", "Room for one more, {name}?"),
    "small_talk": ("Cold on the road tonight.", "Busy night for the inn.", "Long climb up to this inn.",
                   "Fine fire they keep here."),
    "joke": ("My mule drinks less than me.", "This ale could raise the dead.", "Came for one. Still here."),
    "complain": ("This ale tastes of old boots.", "Too loud in here, {name}.", "You never listen, {name}."),
    "content": ("Good talk. I'll let you be.", "Well, I'll leave you to it."),
    "pressed": ("Excuse me, I must step out.", "Pardon me a moment."),
    "introduce": ("I'm {me}, by the way.", "Name's {me}.", "They call me {me}."),
    "insult": ("You're a fool, {name}.", "Nobody asked you, {name}.", "You smell of the stable."),
    "apologize": ("Sorry about earlier, {name}.", "No hard feelings, {name}?"),
    "compliment": ("Good company, {name}.", "You tell a fine tale, {name}."),
    "agree": ("Aye, that's the truth.", "Right you are, {name}."),
    "boast": ("I once outdrank a miller.", "Best shot in my village, me."),
    "accept": ("Gladly!", "Why not, {name}."),
    "decline": ("Not tonight, thanks.", "Maybe later, {name}."),
})
PLACE_LINES: Mapping[str, str] = MappingProxyType({
    "tap": "The ale's at the tap, by the bar.", "toilet": "The WC is past the tables.",
    "darts": "There's a darts board here."})
INVITE_LINES: Mapping[str, str] = MappingProxyType({
    "join_table": "Come sit at my table, {name}.", "move_together": "Shall we find a table of our own, {name}?",
    "darts_together": "Fancy a round of darts?",
    "dice_together": "Care for a game of dice, {name}?",
    "buy_drink": "Let me buy you an ale.", "leave_together": "Shall we walk home together?"})

MAX_LINE = 160  # Characters of a line: the style asks for about 120, and a little over still reads in a bubble.
_HEARD_FROM = re.compile(r"^Heard from [^:]*: ")  # A retold version starts like this; it is never nested.

PRESSING = 75.0  # A thirst, tiredness or bladder this strong takes a guest out of any conversation.
CONTENT = 25.0  # Below this wish for company, a guest has had enough talk.
JOKES = 0.3  # Share of friendly lines that are jokes.
WARM = 0.1  # Share of friendly lines that are compliments, and again that agree.
BOASTS = 0.05  # Share of friendly lines that are boasts.
INVITES = 0.25  # Chance per line that a guest who could invite someone does, once a scene.
DISLIKED = -10.0  # An insult is only for someone the speaker thinks this little of.
LONG_STAY = 300.0  # Game seconds after which a guest is ready to walk home with someone.
BORED = 50.0  # A guest this bored asks for a game, of darts or of dice.
BOLD = 0.5  # A guest this brave (courage trait) prefers dice, a game of chance, to darts.


def scripted_turn(view: Mapping[str, Any]) -> "TurnResult":
    """Write the next line of a scene by a seeded rule, without a model.

    The first line greets. An invitee answers a pending invitation first (see `_answer`). A
    speaker pressed by a need says goodbye, and so does one with company enough once they have
    said something besides a greeting. Otherwise, using only acts the view offers, a stranger
    introduces themselves once; a tipsy, impatient speaker may insult someone they dislike once,
    or complain once; a patient one apologizes once to whoever holds a grudge; they tell a piece
    of news they hold that the scene has not heard from them, once (see `_retold`); they tell where
    the places they know are, once; they may invite the addressee once (see `_invitation`);
    then they make small talk, joke, compliment, agree or boast.

    Args:
        view: Scene view of `turns.turn_view`.

    Returns:
        A turn result (`turns.TurnResult`) addressing the next participant in the circle (the
        inviter, for an answer), on the scene's topic. The draw is seeded by the evening, the
        scene and the turn index, so a replay writes the same line.

    Raises:
        KeyError: The view lacks a field the rule reads.
    """
    scene, me = view["conversation"], view["speaker"]
    rng = Random(f"{view['seed']}:{scene['id']}:{scene['turn']}")
    act, kind = _act(view, rng)
    addressee = _addressee(scene, me, act)
    name = addressee["name"] if addressee.get("known", True) else "friend"
    if kind == "share_news":
        fact = _aimed_fact(me) or rng.choice(_untold(scene, me))
        line = _retold(fact)
    elif kind == "share_place":
        line = PLACE_LINES[rng.choice(me["places"])["kind"]]  # Every known place is shared; the line names one.
    elif act == "invite":
        line = INVITE_LINES[kind]
    else:
        line = rng.choice(LINES[kind])
    result: "TurnResult" = {"line": line.format(name=name, me=me["name"]), "act": act,
                            "addressee": addressee["id"], "topic": scene["topic"]}
    if act == "invite":
        result["invitation"] = kind
    if kind == "share_news":
        result["fact_id"] = fact["id"]
    return result


def _untold(scene: Mapping[str, Any], me: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    # The speaker's news not yet told in this scene, so nobody is told back what they just told; the
    # copies are listed by ID, which keeps the seeded draw among them reproducible.
    told = {turn.get("fact_id") for turn in scene["turns"]}
    return [item for item in me["news"] if item["id"] not in told]


def _retold(fact: Mapping[str, Any]) -> str:
    # A first holder says the news as it is; anyone else names whom they heard it from, in their own
    # version, so scripted wording never drifts (and `Heard from` never nests).
    words = _HEARD_FROM.sub("", fact["told_as"])
    line = words if fact["heard_from"] is None else f"Heard from {fact['heard_from']}: {words}"
    return line[:MAX_LINE]


def _addressee(scene: Mapping[str, Any], me: Mapping[str, Any], act: str) -> Mapping[str, Any]:
    people = [item for item in scene["participants"] if item["id"] != me["id"]]
    if act in ("accept", "decline") or (act == "invite" and (scene["invitation"] or {}).get("to") == me["id"]):
        return next(item for item in people if item["id"] == scene["invitation"]["from"])
    ids = [item["id"] for item in scene["participants"]]
    return scene["participants"][(ids.index(me["id"]) + 1) % len(ids)] if me["id"] in ids else people[0]


def _act(view: Mapping[str, Any], rng: Random) -> tuple[str, str]:
    # Returns the act and which lines voice it (an invitation's kind, for an invite).
    scene, me, acts = view["conversation"], view["speaker"], view["acts"]
    if not scene["turns"]:
        return "greet", "greet"
    if view.get("answer"):
        # The invitee decided (`invitations.answer_options`): the line says it, a counter with an invitation of its own.
        decided = view["answer"]
        return ("invite", decided.partition(":")[2]) if decided.startswith("counter:") else (decided, decided)
    if "accept" in acts:
        answer = _answer(scene["invitation"]["kind"], me)
        return answer, answer
    needs = me["needs"]
    if max(needs["thirst"], needs["fatigue"], needs["bladder"]) >= PRESSING:
        return "leave_conversation", "pressed"
    aimed = _aimed(view)
    if aimed:
        return aimed
    said = {turn["act"] for turn in scene["turns"] if turn["speaker"] == me["id"]}
    # Even a guest with company enough answers once before taking their leave. A barkeep on duty never
    # does: his needs read as content (all at 0), but he stays while the guest does.
    if needs["social"] < CONTENT and said - {"greet"} and not me.get("on_duty"):
        return "leave_conversation", "content"
    return _opening_up(view, said, rng) or _friendly(view, said, rng)


def _aimed(view: Mapping[str, Any]) -> tuple[str, str] | None:
    # What the speaker came for, in the first of the aim's acts that is on offer and has lines to voice it: an invite
    # names its invitation, news the fact the aim names. Passing the time is what scripted lines do anyway.
    me, aim = view["speaker"], view["speaker"].get("aim")
    if aim is None or aim["done"] or aim["id"] == "pass_time":
        return None
    for act in aim["acts"]:
        if act not in view["acts"]:
            continue
        if act == "invite" and aim["detail"] in view.get("invitations", []):
            return "invite", aim["detail"]
        if act == "share_news" and _aimed_fact(me, aim) is not None and _aimed_fact(me, aim) in _untold(view["conversation"], me):
            return "share_news", "share_news"
        if act in LINES:
            return act, act
    return None


def _aimed_fact(me: Mapping[str, Any], aim: Mapping[str, Any] | None = None) -> Mapping[str, Any] | None:
    # The piece of news a tell-news aim names, if the speaker holds it.
    aim = aim or me.get("aim")
    if aim is None or not aim["id"].startswith("tell_news:"):
        return None
    return next((item for item in me["news"] if item["id"] == aim["detail"]), None)


def _opening_up(view: Mapping[str, Any], said: set[str], rng: Random) -> tuple[str, str] | None:
    # Once-a-scene acts, in order: a name, a grudge aired, an apology, places, an invitation.
    me, acts = view["speaker"], view["acts"]
    if "introduce" in acts and "introduce" not in said:
        return "introduce", "introduce"
    if "insult" in acts and "insult" not in said and _disliked(view) and rng.random() < _temper(me):
        return "insult", "insult"
    if "complain" not in said and rng.random() < _temper(me):
        return "complain", "complain"
    if "apologize" in acts and "apologize" not in said and me["traits"].get("patience", 0.5) >= 0.5:
        return "apologize", "apologize"
    if "share_news" in acts and "share_news" not in said and _untold(view["conversation"], me):
        return "share_news", "share_news"
    if "share_place" not in said and me["places"]:
        return "share_place", "share_place"
    kind = _invitation(view)
    if kind and "invite" not in said and said and rng.random() < INVITES:
        return "invite", kind
    return None


def _friendly(view: Mapping[str, Any], said: set[str], rng: Random) -> tuple[str, str]:
    # One draw splits friendly lines among the acts on offer; the rest is small talk.
    acts, draw = view["acts"], rng.random()
    shares = (("joke", JOKES), ("compliment", WARM), ("agree", WARM), ("boast", BOASTS))
    bound = 0.0
    for act, share in shares:
        bound += share
        if draw < bound and act in acts:
            return act, act
    return "small_talk", "small_talk"


def _disliked(view: Mapping[str, Any]) -> bool:
    # Whether the speaker thinks poorly of whoever they would address (see `_addressee`).
    addressee = _addressee(view["conversation"], view["speaker"], "insult")
    return view["speaker"]["opinions"][addressee["id"]] <= DISLIKED


def _invitation(view: Mapping[str, Any]) -> str | None:
    # What the speaker would like company for, among the kinds on offer: walking home after a long
    # stay, dice when bored and bold, darts when merely bored, a table (theirs, or one of their own) when lonely, else an
    # ale for the other. Views written for
    # scenes before invitations existed offer none.
    offered, me = view.get("invitations", []), view["speaker"]
    wishes = [("leave_together", me["visit"]["seconds"] >= LONG_STAY),
              ("dice_together", me["needs"]["boredom"] >= BORED and me["traits"].get("courage", 0.5) >= BOLD),
              ("darts_together", me["needs"]["boredom"] >= BORED),
              ("join_table", me["needs"]["social"] >= 50), ("move_together", me["needs"]["social"] >= 50),
              ("buy_drink", True)]
    return next((kind for kind, wished in wishes if wished and kind in offered), None)


def _answer(kind: str, me: Mapping[str, Any]) -> str:
    # An ale is always welcome; the rest are accepted when the invitee wants what they offer.
    needs = me["needs"]
    wanted = {"buy_drink": True, "darts_together": needs["boredom"] >= 30, "dice_together": needs["boredom"] >= 30,
              "join_table": needs["social"] >= CONTENT, "move_together": needs["social"] >= CONTENT,
              "leave_together": me["visit"]["seconds"] >= LONG_STAY}
    return "accept" if wanted[kind] else "decline"


def _temper(me: Mapping[str, Any]) -> float:
    # Sober guests never grumble; each beer past the first makes an impatient one likelier to.
    patience = me["traits"].get("patience", 0.5)
    return min(1.0, 0.5 * max(0, me["visit"]["beers"] - 1) * (1 - patience))


async def write_scripted_turn(view: Mapping[str, Any], config: Mapping[str, Any]) -> "TurnResult":
    """Write a scripted line through the turn writer port (`turns.TurnWriter`), offline.

    Args:
        view: Scene view of `turns.turn_view`.
        config: AI config; unused, as no model is asked.

    Returns:
        The result of `scripted_turn`.
    """
    return scripted_turn(view)
