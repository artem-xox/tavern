"""What visitors think and feel tonight: timed thoughts, mood, and opinions of each other."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, NotRequired, TypedDict

from tavern.hall.state import Actor, World
from tavern.hall.validation import number
from tavern.social.names import called


@dataclass(frozen=True)
class ThoughtKind:
    """How one kind of event weighs on a visitor, RimWorld-style.

    Attributes:
        mood: Mood change while the thought lasts.
        opinion: Opinion change toward the person it is about while it lasts.
        seconds: Game seconds it lasts.
        stack: Most thoughts of this kind about one person that count at once.
        reason: How the briefing explains an opinion it causes: "who {reason}".
        acquaints: Whether it means the two have talked, so strangers become acquaintances.
    """

    mood: float
    opinion: float
    seconds: float
    stack: int
    reason: str
    acquaints: bool = False


THOUGHTS: Mapping[str, ThoughtKind] = MappingProxyType({
    "seat_taken": ThoughtKind(-6.0, -15.0, 300.0, 3, "took their seat"),
    # Held by the host of a table, about the guest who sat down there without being welcome (`tavern.social.tables`).
    "table_intruded": ThoughtKind(-3.0, -10.0, 240.0, 2, "sat down at their table uninvited"),
    # Held by the one an apology mended, about whoever made it (`tavern.social.social_acts`).
    "apologized": ThoughtKind(1.0, 6.0, 300.0, 1, "apologized to them", acquaints=True),
    "line_cut": ThoughtKind(-4.0, -10.0, 180.0, 3, "cut in line ahead of them"),
    "quarrel": ThoughtKind(-8.0, -20.0, 300.0, 3, "quarreled with them", acquaints=True),
    "chat": ThoughtKind(3.0, 6.0, 240.0, 3, "had a pleasant chat with them", acquaints=True),
    # Speech acts (`conversation.ACTS`) and what follows them.
    "compliment": ThoughtKind(4.0, 8.0, 240.0, 2, "paid them a compliment", acquaints=True),
    "boast_admired": ThoughtKind(1.0, 3.0, 180.0, 2, "told a fine tale of themselves", acquaints=True),
    "boast_tiresome": ThoughtKind(-1.0, -4.0, 180.0, 2, "boasted at them", acquaints=True),
    "insulted": ThoughtKind(-6.0, -20.0, 300.0, 3, "insulted them", acquaints=True),
    "agreed": ThoughtKind(0.0, 3.0, 240.0, 3, "agreed with them", acquaints=True),
    "disagreed": ThoughtKind(0.0, -3.0, 240.0, 3, "disagreed with them", acquaints=True),
    "treated": ThoughtKind(3.0, 10.0, 300.0, 2, "bought them a drink", acquaints=True),
    "friend_insulted": ThoughtKind(-3.0, -12.0, 300.0, 3, "insulted someone they like"),
    # A promise made to the guest, kept or broken (`tavern.social.commitments`), about the one who made it.
    "promised": ThoughtKind(1.0, 4.0, 120.0, 1, "promised to come and sit with them", acquaints=True),
    "kept_word": ThoughtKind(2.0, 10.0, 300.0, 2, "kept their word to them", acquaints=True),
    "let_down": ThoughtKind(-3.0, -12.0, 300.0, 2, "broke their word to them", acquaints=True),
    # Held by the receiver of a gift (`tavern.social.giving`), about the giver; `treated` is the one for a drink.
    "cared_for": ThoughtKind(4.0, 12.0, 300.0, 2, "gave them a remedy", acquaints=True),
    "gifted": ThoughtKind(3.0, 10.0, 300.0, 2, "gave them a keepsake", acquaints=True),
    # Held by a guest who came in unwell, about whoever gave them the remedy that cured them (`tavern.body.ailment`).
    "cured": ThoughtKind(6.0, 20.0, 600.0, 1, "cured them of their fever", acquaints=True),
    # Held by a giver, about the one who took what they gave: it is how they remember having given it.
    "generous": ThoughtKind(1.0, 0.0, 300.0, 2, "accepted a gift from them"),
    # Held by a giver whose gift was refused, about the one who refused it.
    "rebuffed": ThoughtKind(-3.0, -8.0, 180.0, 2, "refused what they offered"),
    # Held by the victim of a hostile act (`tavern.body.activities`), about whoever did it.
    "shoved": ThoughtKind(-8.0, -25.0, 300.0, 3, "shoved them", acquaints=True),
    "attacked": ThoughtKind(-10.0, -35.0, 300.0, 3, "attacked them", acquaints=True),
    # Held after a fight (`tavern.social.aftermath`): by the fighters about each other, and by those who saw it begin
    # about whoever started it.
    "won_fight": ThoughtKind(5.0, -5.0, 300.0, 2, "lost a fight to them", acquaints=True),
    "lost_fight": ThoughtKind(-8.0, -30.0, 600.0, 2, "beat them in a fight", acquaints=True),
    "knocked_out_by": ThoughtKind(-12.0, -40.0, 600.0, 2, "knocked them out", acquaints=True),
    "fought": ThoughtKind(-3.0, -10.0, 300.0, 2, "came to blows with them", acquaints=True),
    "saw_fight": ThoughtKind(-3.0, -10.0, 240.0, 2, "started a brawl in front of them"),
    # Held by a fighter about whoever pulled them apart, and by one helped up off the floor about their helper.
    "separated_us": ThoughtKind(1.0, 5.0, 300.0, 1, "pulled them apart", acquaints=True),
    "helped_up": ThoughtKind(4.0, 15.0, 600.0, 1, "helped them up off the floor", acquaints=True),
    # Held by a fighter about a bystander who cheered them on.
    "cheered_on": ThoughtKind(2.0, 8.0, 240.0, 1, "cheered them on", acquaints=True),
    # Held by a guest dosed with a remedy for their wounds, about whoever gave it.
    "tended": ThoughtKind(5.0, 15.0, 600.0, 1, "saw to their wounds", acquaints=True),
    # Held by the winner and the loser of a game of dice (`tavern.social.dice`), about each other.
    "won_at_dice": ThoughtKind(5.0, 2.0, 300.0, 3, "lost to them at dice", acquaints=True),
    "lost_at_dice": ThoughtKind(-4.0, -6.0, 300.0, 3, "beat them at dice", acquaints=True),
})

FAMILIARITY = ("stranger", "acquaintance", "friend")
_BASE_RELATION = {"name", "opinion", "familiarity"}

# Starting relationships a scenario may name, as (base opinion, familiarity), held both ways.
_STARTING: Mapping[str, tuple[float, str]] = MappingProxyType({
    "old friends": (50.0, "friend"), "rivals": (-40.0, "acquaintance"),
    "bad blood": (-60.0, "acquaintance")})


class Thought(TypedDict):
    """One timed thought: what it is, whom it is about, its effects, and what caused it."""

    kind: str
    about: str | None
    text: str
    mood: float
    opinion: float
    expires_at: float
    source_event: str
    # Whether the guest has set out to answer it (`tavern.social.responses`); absent until they do.
    answered: NotRequired[bool]


class Relation(TypedDict):
    """How a visitor regards one other person, before tonight's thoughts.

    `name` is what the visitor calls them: their looks until `knows_name` (see `tavern.social.names`).
    Relations from `seed_relations` leave the flag to the caller.
    """

    name: str
    opinion: float
    familiarity: str
    knows_name: NotRequired[bool]


# The words of the thought a chat leaves behind, kept in one place so that `words_on_mind` can read it back.
CHAT = "Chatted with {who} about {topic}"
_CHAT = re.compile(r"Chatted with .+? about (.+)")


def words_on_mind(thoughts: Sequence[Mapping[str, Any]], who: str) -> list[str]:
    """Word the thoughts a guest holds about one person, for a line writer.

    Args:
        thoughts: The guest's active thoughts about that person, oldest first.
        who: How the guest calls them now (`names.called`), which may be a name learnt since a thought was
            had, when the thought's own words named them by their looks.

    Returns:
        Each thought's words, except that the chats (`CHAT`) are one line, at the place of the first, naming
        who and each topic once. A chat in other words is left as it is.
    """
    def chat(item: Mapping[str, Any]) -> "re.Match[str] | None":
        return _CHAT.fullmatch(item["text"]) if item["kind"] == "chat" else None
    topics = list(dict.fromkeys(match.group(1) for item in thoughts if (match := chat(item))))
    words: list[str] = []
    chatted = False
    for item in thoughts:
        if not chat(item):
            words.append(item["text"])
        elif not chatted:
            heard = f"{', '.join(topics[:-1])} and {topics[-1]}" if len(topics) > 1 else topics[0]
            words.append(CHAT.format(who=who, topic=heard))
            chatted = True
    return words


def think(actor: Actor, kind: str, now: float, text: str, source_event: str,
          about: Mapping[str, Any] | None = None) -> Thought:
    """Give a visitor a timed thought, stacking repeats up to the kind's cap.

    Repeats of one kind about one person stack, since being wronged twice is worse than
    once, but only `stack` of them count: a further one replaces the oldest, refreshing
    the feeling rather than deepening it without end.

    Args:
        actor: Visitor with `thoughts` and `relations`, updated in place.
        kind: One of `THOUGHTS`.
        now: Current game time.
        text: The thought in the visitor's own words, such as "Bea took my seat".
        source_event: Message of the logged event that caused it.
        about: Visitor it is about, or None.

    Returns:
        The new thought.

    Raises:
        ValueError: The kind is unknown.
    """
    if kind not in THOUGHTS:
        raise ValueError(f"Unknown thought kind {kind!r}")
    rule, about_id = THOUGHTS[kind], about["id"] if about else None
    same = [item for item in active_thoughts(actor["thoughts"], now)
            if item["kind"] == kind and item["about"] == about_id]
    if len(same) >= rule.stack:
        actor["thoughts"].remove(min(same, key=lambda item: item["expires_at"]))
    thought = Thought(kind=kind, about=about_id, text=text, mood=rule.mood, opinion=rule.opinion,
                      expires_at=now + rule.seconds, source_event=source_event)
    actor["thoughts"].append(thought)
    if about is not None:
        _meet(actor, about, rule.acquaints)
    return thought


def _meet(actor: Actor, other: Mapping[str, Any], talked: bool) -> Relation:
    # Familiarity only ever grows; talking makes strangers acquaintances.
    relation = actor["relations"].setdefault(other["id"], Relation(
        name=called(actor, other), opinion=0.0, familiarity="stranger", knows_name=False))
    if talked and relation["familiarity"] == "stranger":
        relation["familiarity"] = "acquaintance"
    return relation


def learn_name(actor: Actor, other: Mapping[str, Any], met: bool,
               friends: Sequence[Actor] = ()) -> None:
    """Let a visitor learn someone's name; their old friends present learn it from them.

    Args:
        actor: Visitor learning it, whose relation to `other` is created or updated in place.
        other: Person whose name it is.
        met: Whether the two met to learn it (an introduction), which makes strangers
            acquaintances; an overheard or passed-on name does not.
        friends: Everyone else in the hall; those who count the visitor as a `friend` learn it
            too, once, without meeting `other`.
    """
    if actor["id"] == other["id"]:
        return
    relation = _meet(actor, other, met)
    known = relation.get("knows_name", False)
    relation.update({"name": other["name"], "knows_name": True})
    if known:
        return
    for friend in friends:
        if friend["id"] != other["id"] and familiarity_of(friend, actor["id"]) == "friend":
            learn_name(friend, other, False)


def soften(actor: Actor, about_id: str, now: float) -> bool:
    """Halve the latest active grudge a visitor holds against someone, once, as an apology does.

    Args:
        actor: Visitor whose thoughts are updated in place.
        about_id: Person who apologized.
        now: Current game time.

    Returns:
        Whether there was an unsoftened grudge (an active thought lowering the opinion).
    """
    grudges = [item for item in active_thoughts(actor["thoughts"], now) if item["about"] == about_id
               and item["opinion"] < 0 and item["opinion"] == THOUGHTS[item["kind"]].opinion]
    if not grudges:
        return False
    grudges[-1].update({"mood": grudges[-1]["mood"] / 2, "opinion": grudges[-1]["opinion"] / 2})
    return True


def rankling(actor: Mapping[str, Any], now: float) -> list[str]:
    """List what still rankles a visitor.

    Args:
        actor: Visitor; one without `thoughts` has none.
        now: Current game time.

    Returns:
        The texts of the latest five active thoughts that lower the mood, oldest first.
    """
    return [item["text"] for item in active_thoughts(actor.get("thoughts", []), now) if item["mood"] < 0][-5:]


def active_thoughts(thoughts: Sequence[Thought], now: float) -> list[Thought]:
    """List the thoughts that still count.

    Args:
        thoughts: A visitor's thoughts, oldest first.
        now: Current game time.

    Returns:
        Those expiring after `now`, in their order; one stops counting at its `expires_at`.
    """
    return [item for item in thoughts if item["expires_at"] > now]


def mood(actor: Mapping[str, Any], now: float) -> float:
    """Derive a visitor's mood: their active thoughts plus their pressing needs.

    Args:
        actor: Visitor with `needs` and, once in the world, `thoughts`.
        now: Current game time.

    Returns:
        The sum of active thoughts' mood, minus 1 for every 25 points a need stands above
        50, so a calm visitor without thoughts is at 0. Unbounded; words come in the briefing.
    """
    pressing = sum(max(0.0, value - 50) for value in actor["needs"].values()) / 25
    return thought_mood(actor, now) - pressing


def thought_mood(actor: Mapping[str, Any], now: float) -> float:
    """Sum the mood of a visitor's active thoughts, without their needs.

    Args:
        actor: Visitor; one without `thoughts` has none.
        now: Current game time.

    Returns:
        Total mood change of the active thoughts.
    """
    return sum(item["mood"] for item in active_thoughts(actor.get("thoughts", []), now))


def opinion_of(actor: Mapping[str, Any], other_id: str, now: float) -> float:
    """Derive what a visitor thinks of someone: base opinion plus active thoughts about them.

    Args:
        actor: Visitor with `relations` and `thoughts`.
        other_id: Person they think of.
        now: Current game time.

    Returns:
        Opinion from −100 to 100; 0 for someone they have no relation with or thought about.
    """
    base = actor.get("relations", {}).get(other_id, {}).get("opinion", 0.0)
    change = sum(item["opinion"] for item in active_thoughts(actor.get("thoughts", []), now)
                 if item["about"] == other_id)
    return max(-100.0, min(100.0, base + change))


def familiarity_of(actor: Mapping[str, Any], other_id: str) -> str:
    """Tell how well a visitor knows someone.

    Args:
        actor: Visitor with `relations`.
        other_id: Person they may know.

    Returns:
        `stranger`, `acquaintance` or `friend`; anyone without a relation is a stranger.
    """
    return actor.get("relations", {}).get(other_id, {}).get("familiarity", "stranger")


def friends_of(actor: Mapping[str, Any]) -> list[str]:
    """List the people a visitor counts as friends, for hearing's relevance.

    Args:
        actor: Visitor with `relations`.

    Returns:
        IDs whose familiarity is `friend`, in relation order; liking alone makes no friend.
    """
    return [other for other, relation in actor.get("relations", {}).items() if relation["familiarity"] == "friend"]


def forget_expired(world: Mapping[str, Any]) -> None:
    """Drop the thoughts that stopped counting from every visitor in the hall.

    Args:
        world: World with the current `time`; visitors are updated in place.
    """
    for actor in world["actors"]:
        actor["thoughts"] = active_thoughts(actor["thoughts"], world["time"])


def seed_relations(pairs: Sequence[Mapping[str, Any]], names: Mapping[str, str]) -> dict[str, dict[str, Relation]]:
    """Turn starting relationships into each visitor's base opinions and familiarity.

    Args:
        pairs: Records `{a, b, kind}` with `kind` of `ties.KINDS`; each holds both ways.
        names: Name of every guest of the evening, by ID.

    Returns:
        Relations by visitor ID, then by the other person's ID.

    Raises:
        ValueError: A record is malformed, names an unknown guest or kind, pairs a guest with
            themselves, or repeats a pair.
    """
    relations: dict[str, dict[str, Relation]] = {}
    for pair in pairs:
        left, right, kind = pair.get("a"), pair.get("b"), pair.get("kind")
        if not (isinstance(left, str) and isinstance(right, str) and isinstance(kind, str)) or (
                left not in names or right not in names or left == right or kind not in _STARTING):
            raise ValueError(f"Invalid starting relationship {dict(pair)!r}")
        if right in relations.get(left, {}):
            raise ValueError(f"Starting relationship of {left!r} and {right!r} given twice")
        opinion, familiarity = _STARTING[kind]
        for one, other in ((left, right), (right, left)):
            relations.setdefault(one, {})[other] = Relation(name=names[other], opinion=opinion,
                                                            familiarity=familiarity)
    return relations


def check_mind(actor: Mapping[str, Any]) -> None:
    """Check a saved visitor's thoughts and relations.

    Args:
        actor: Untrusted saved visitor record.

    Raises:
        ValueError: Thoughts or relations are missing or malformed.
    """
    thoughts, relations = actor.get("thoughts"), actor.get("relations")
    if not isinstance(thoughts, list) or not isinstance(relations, dict):
        raise ValueError("Saved thoughts must be a list and relations a mapping")
    for item in thoughts:
        if not isinstance(item, dict) or set(item) - {"answered"} != set(Thought.__annotations__) - {"answered"} \
                or item["kind"] not in THOUGHTS or not isinstance(item.get("answered", False), bool):
            raise ValueError(f"Invalid saved thought {item!r}")
        if not isinstance(item["text"], str) or not isinstance(item["source_event"], str) \
                or not isinstance(item["about"], (str, type(None))):
            raise ValueError(f"Invalid saved thought {item!r}")
        for key in ("mood", "opinion", "expires_at"):
            number(item[key], f"Saved thought {key}", -math.inf, math.inf)
    for other, relation in relations.items():
        if not isinstance(relation, dict) or set(relation) - {"knows_name"} != _BASE_RELATION \
                or relation["familiarity"] not in FAMILIARITY or not isinstance(relation["name"], str) \
                or not isinstance(relation.get("knows_name", False), bool):
            raise ValueError(f"Invalid saved relation with {other!r}")
        number(relation["opinion"], "Saved base opinion", -100, 100)
