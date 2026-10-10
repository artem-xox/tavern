"""The sentence for each option a visitor may take, told from their own view."""

from collections.abc import Callable, Mapping
import math
from typing import Any

from tavern.body.activities import FAMILIES
from tavern.body.items import ITEMS
from tavern.mind.fight_words import TEXTS as FIGHT_TEXTS
from tavern.social.aims import aim_words
from tavern.social.giving import empty_handed_tablemates
from tavern.social.invitations import KINDS, known_place
from tavern.social.tables import liked
from tavern.mind.hall_view import (company_at, headcount, hosts_words, in_use, known_object, label_of, line_place,
                                   place_words, setting_words, steps_to, visible_visitor, walk_words)

Observation = Mapping[str, Any]
Action = Mapping[str, Any]


def option_text(observation: Observation, action: Action) -> str:
    """Describe one concrete option in plain words, from the visitor's own view.

    Args:
        observation: The visitor's observation.
        action: A candidate with `verb` and `target_id`.

    Returns:
        A sentence; using a busy place with a line reads as waiting in it.

    Raises:
        ValueError: The verb has no sentence in `_OPTIONS`.
    """
    if action["verb"] not in _OPTIONS:
        raise ValueError(f"Cannot describe the action verb {action['verb']!r}")
    return _waiting(observation, action) or _OPTIONS[action["verb"]](observation, action)


def aim_text(observation: Observation, candidate: Action) -> str:
    """Describe an aim of a social option in plain words, from the visitor's own view.

    Args:
        observation: The visitor's observation.
        candidate: An aim candidate (`aims.aim_candidates`): the social action and its `aim`.

    Returns:
        The action's sentence and what the visitor means by it, for example "chat with Bea, meaning to ask Bea for a
        rematch at dice".

    Raises:
        ValueError: The person is not in sight, or the action cannot be described.
    """
    person = next((item for item in [*observation.get("visitors", []), *observation.get("people", [])]
                   if item["id"] == candidate["target_id"]), None)
    if person is None:
        raise ValueError(f"Cannot describe an aim towards {candidate['target_id']!r}, who is not in sight")
    topics = {fact_id: fact["topic"] for fact_id, fact in observation["actor"].get("knowledge", {}).get("facts", {}).items()}
    words = aim_words(candidate["aim"], label_of(person), topics)
    return f"{option_text(observation, candidate)}, meaning to {words}"


def answer_text(observation: Observation, invitation: Mapping[str, Any], answer: str) -> str:
    """Describe one way of answering an invitation, from the invitee's view.

    Args:
        observation: The invitee's observation.
        invitation: The pending invitation (`kind`, `from`).
        answer: `accept`, `decline` or `counter:<kind>`.

    Returns:
        For example "turn down Ada's invitation to play a game of dice and invite them to play darts together instead".

    Raises:
        ValueError: The inviter is not in sight, or the answer is none of the three.
    """
    inviter = next((item for item in [*observation.get("visitors", []), *observation.get("people", [])]
                    if item["id"] == invitation["from"]), None)
    if inviter is None:
        raise ValueError(f"Cannot describe an answer to {invitation['from']!r}, who is not in sight")
    asked = f"{label_of(inviter)}'s invitation to {KINDS[invitation['kind']]}"
    if answer == "accept":
        return f"accept {asked}"
    if answer == "decline":
        return f"turn down {asked}"
    if answer.startswith("counter:") and answer.partition(":")[2] in KINDS:
        return f"turn down {asked} and invite them to {KINDS[answer.partition(':')[2]]} instead"
    raise ValueError(f"Cannot describe the answer {answer!r}")


def _waiting(observation: Observation, action: Action) -> str:
    # Using a busy place with a line means waiting in it; staying in line is the same choice again.
    item = known_object(observation, action.get("target_id"))
    if item is None or "queue_spots" not in item or action["verb"] == "cut_in_line":
        return ""
    ahead, joined = line_place(observation, item)
    used, place = in_use(observation, item), place_words(item)
    if joined and not ahead:
        return f"keep waiting in line for {place} (they are next{', while someone uses it' if used else ''})"
    parts = [f"{headcount(ahead)} {'is' if ahead == 1 else 'are'} waiting for {place}"
             f"{' ahead of them' if joined else ''}"] if ahead else []
    note = ", and ".join([*parts, *(["someone is using it"] if used else [])])
    if joined:
        return f"keep waiting in line for {place} ({note})"
    return f"walk {walk_words(steps_to(observation, item))} to {place} and wait in line ({note})" if note else ""


def _cut(observation: Observation, action: Action) -> str:
    item = _target(observation, action)
    ahead = line_place(observation, item)[0]
    return (f"push to the front of the line for {place_words(item)}, ahead of the {headcount(ahead)} waiting, "
            "who will resent it")


def _target(observation: Observation, action: Action) -> Mapping[str, Any]:
    target = known_object(observation, action["target_id"])
    if target is None:
        raise ValueError(f"Cannot describe an unknown target {action['target_id']!r}")
    return target


def _pour(observation: Observation, action: Action) -> str:
    tap = _target(observation, action)
    # With a barkeep in sight the guest asks for the mug, as he pours them; otherwise they pour their own.
    barkeep = next((person for person in observation.get("people", []) if person.get("post")), None)
    pour = f"ask {label_of(barkeep)} for a mug of ale" if barkeep else "pour a mug of ale"
    return f"walk {walk_words(steps_to(observation, tap))} to the tap and {pour} ({tap.get('stock')} servings when last seen)"


def _settle(observation: Observation, action: Action) -> str:
    tap = known_object(observation, known_place(observation["actor"], "tap"))
    where = f"walk {walk_words(steps_to(observation, tap))} to the tap, get a mug of ale, and take a chair at a table to " \
        "drink it there" if tap else "get a mug of ale and take a chair at a table to drink it there"
    return f"{where} (they choose the chair next)"


def _round(observation: Observation, action: Action) -> str:
    people = {item["id"]: item for item in observation.get("people", [])}
    names = [label_of(people[item]) for item in empty_handed_tablemates(observation) if item in people]
    return (f"stand the table a round: fetch {', '.join(names)} an ale each from the tap, one after the other "
            "(they sit there with empty hands)")


def _rematch(observation: Observation, action: Action) -> str:
    other = next((item for item in observation.get("people", []) if item["id"] == action["target_id"]), None)
    if other is None:
        raise ValueError(f"Cannot describe a rematch with {action['target_id']!r}, who is not in sight")
    return f"go to {label_of(other)}, who beat them at dice, and ask for a rematch"


def _drink(observation: Observation, action: Action) -> str:
    if observation["actor"].get("seat_id"):
        return "sip the mug of ale they are holding, right here in their seat"
    return "drink the mug of ale they are holding where they stand, as there is no seat to be had"


def _rest(observation: Observation, action: Action) -> str:
    chair = _target(observation, action)
    return f"walk {walk_words(steps_to(observation, chair))} to {label_of(chair)} and rest there"


def _seat_note(observation: Observation, chair: Mapping[str, Any]) -> str:
    table = known_object(observation, chair.get("table_id"))
    details = [setting_words(chair), hosts_words(observation, chair.get("table_id")), _welcome(observation, table),
               company_at(observation, chair.get("table_id")), f"{walk_words(steps_to(observation, chair))} away"]
    return f"{label_of(table) if table else label_of(chair)} ({'; '.join(part for part in details if part)})"


def _welcome(observation: Observation, table: Mapping[str, Any] | None) -> str:
    # Whether the table's hosts would be glad of them, as far as the visitor can tell: if they like one of them.
    hosts = table.get("hosts", []) if table else []
    if not hosts:
        return ""
    fond = next((item for item in hosts if liked(observation["actor"], item["id"], observation.get("time", -math.inf))), None)
    return f"they get on with {fond['name']}" if fond else "they would be sitting down there uninvited"


def _seating(observation: Observation, action: Action) -> str:
    actor = observation["actor"]
    free = [item for item in observation["objects"] if item["kind"] == "chair" and item.get("table_id")
            and not in_use(observation, item) and item["id"] != actor.get("favorite_seat_id")]
    tables = {item["table_id"]: _seat_note(observation, item) for item in free}
    choice = "; ".join(tables.values()) or "none"
    if actor.get("favorite_seat_id"):
        return (f"leave their own seat for a free chair at another table, for instance to join company they like or to "
                f"take a table nobody holds (free: {choice})")
    return f"look for a seat and sit down (tables with a free chair: {choice})"


def _sit(observation: Observation, action: Action) -> str:
    actor, chair = observation["actor"], _target(observation, action)
    company = company_at(observation, chair.get("table_id"))
    if chair["id"] == actor.get("seat_id"):
        return f"stay in their seat, {label_of(chair)}, a while longer to rest, sip and chat ({company})"
    if chair["id"] == actor.get("favorite_seat_id"):
        return f"walk {walk_words(steps_to(observation, chair))} back to their own seat, {label_of(chair)}, and sit down ({company})"
    owner = chair.get("owner")
    if owner:
        return (f"take {owner['name']}'s own seat, {label_of(chair)}, while {owner['name']} is away: "
                f"{_seat_note(observation, chair)} (it would wrong {owner['name']})")
    return f"take the chair {label_of(chair)}: {_seat_note(observation, chair)}"


def _doze(observation: Observation, action: Action) -> str:
    return ("put their head down on the table and sleep a while, right here in their seat (it restores some energy; "
            "nobody at an inn minds, and a loud noise will wake them)")


def _someone(observation: Observation, visitor_id: Any) -> Mapping[str, Any] | None:
    # Everyone in sight when observed (`people`), else only seated company.
    return next((item for item in observation.get("people", []) if item["id"] == visitor_id),
                None) or visible_visitor(observation, visitor_id)


def _placed(observation: Observation, person: Mapping[str, Any] | None) -> str:
    # Where someone within reach is, from the viewer's own spot. A guest standing by their table reaches
    # those seated at it; to anyone else a stander is simply beside them.
    if person and person.get("seat_id"):
        return "sits at their table" if observation["actor"].get("seat_id") else "sits at the table they stand by"
    return "stands beside them"


def _talk(observation: Observation, action: Action) -> str:
    partner = _someone(observation, action["target_id"])
    name = label_of(partner) if partner else action["target_id"]
    if partner and partner.get("post"):
        return f"chat with {name} across the bar"
    if partner and not partner.get("seat_id"):
        return f"start a conversation with {name}, who stands beside them"
    if observation["actor"].get("seat_id"):
        return f"chat with {name}, who sits across the table from them"
    return f"chat with {name}, who sits at the table they stand by"


def _approach(observation: Observation, action: Action) -> str:
    partner = _someone(observation, action["target_id"])
    name = label_of(partner) if partner else action["target_id"]
    table = known_object(observation, partner.get("table_id")) if partner else None
    pale = (f" ({name} looks pale and feverish)" if partner and partner.get("ailing")
            else f" ({name} is battered and hurt)" if partner and partner.get("hurt") else "")
    if table is None:
        return f"walk over to {name}'s table and talk with them{pale}, standing beside it"
    return (f"walk {walk_words(steps_to(observation, table))} over to the {label_of(table)} and talk with {name}{pale}, "
            f"standing beside it ({company_at(observation, table['id'])})")


def _confrontee(observation: Observation, action: Action) -> tuple[str, str]:
    victim = _someone(observation, action["target_id"])
    return (label_of(victim) if victim else action["target_id"]), _placed(observation, victim)


def _shove(observation: Observation, action: Action) -> str:
    name, where = _confrontee(observation, action)
    return f"shove {name}, who {where}, hard enough that the whole room turns to look (a rough act, and {name} will not forget it)"


def _fight(observation: Observation, action: Action) -> str:
    name, where = _confrontee(observation, action)
    return (f"pick a fight with {name}, who {where}: a brawl the whole room will hear, which {name} will not "
            "forget and which may leave someone hurt")


def _give(observation: Observation, action: Action) -> str:
    receiver = _someone(observation, action["target_id"])
    name = label_of(receiver) if receiver else action["target_id"]
    where = _placed(observation, receiver)
    item = ITEMS[action["item"]]
    cure = ("they look pale and feverish: this would cure them; " if item.cures and receiver and receiver.get("ailing")
            else "they are battered and hurt: this would mend them; " if item.cures and receiver and receiver.get("hurt")
            else "")
    return (f"hand {item.one} they are carrying to {name}, who {where} ({cure}it is theirs to give up, "
            f"and {name} may refuse it if there is bad blood between them)")


def _bring(observation: Observation, action: Action) -> str:
    receiver = _someone(observation, action["target_id"])
    name = label_of(receiver) if receiver else action["target_id"]
    where = _placed(observation, receiver)
    return (f"fetch a mug of ale from the tap and bring it to {name}, who {where} with nothing in their hands "
            f"(it takes a trip, and {name} may refuse it if there is bad blood between them)")


def _join(observation: Observation, action: Action) -> str:
    member = _someone(observation, action["target_id"])
    if member is None:
        raise ValueError(f"Cannot describe joining an unseen visitor {action['target_id']!r}")
    company = observation.get("people") or observation.get("visitors", [])
    names = [label_of(item) for item in company if item.get("conversation") == member.get("conversation")]
    where = ("at their table" if observation["actor"].get("seat_id") else "at the table they stand by") \
        if member.get("seat_id") else "beside them"
    return f"join the conversation {' and '.join(names) or label_of(member)} are having {where}"


def _darts(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the darts board and play a round"


def _bar(observation: Observation, action: Action) -> str:
    barkeep = next((person for person in observation.get("people", []) if person.get("post")), None)
    return (f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the bar and lean on it, "
            f"where {label_of(barkeep) if barkeep else 'the barkeep'} tends it")


def _watch(observation: Observation, action: Action) -> str:
    view = _target(observation, action)
    sight = "the flames in the fireplace" if view["kind"] == "fireplace" else "the road outside a window"
    return f"walk {walk_words(steps_to(observation, view))} and watch {sight} for a while"


def _watch_dice(observation: Observation, action: Action) -> str:
    table = _target(observation, action)
    players = [_someone(observation, identifier) for identifier in (table.get("game") or {}).get("players", [])]
    names = [label_of(item) for item in players if item is not None]
    game = f"{' and '.join(names)} play dice" if len(names) == 2 else "a game of dice"
    return f"walk {walk_words(steps_to(observation, table))} to the dice table and watch {game}"


def _toilet(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the WC"


def _inspect(observation: Observation, action: Action) -> str:
    if all(item["kind"] != "toilet" for item in observation["objects"]):
        return "look around the room for places they have not found yet, such as the WC"
    return "wander around to re-check places they already know (there is nothing new to find)"


def _wait(observation: Observation, action: Action) -> str:
    return "wait where they are and do nothing for a moment"


def _leave(observation: Observation, action: Action) -> str:
    return f"walk {walk_words(steps_to(observation, _target(observation, action)))} to the front door and go home for the night"


def family_text(observation: Observation, option: Action) -> str:
    """Describe a family option: its wish, with three examples of what it could be.

    Args:
        observation: The visitor's observation.
        option: A family option holding its `members`.

    Returns:
        "<family>: <example>; or <example>..." with any further members only counted.
    """
    members = option["members"]
    shown = "; or ".join(option_text(observation, item) for item in members[:3])
    more = f"; or one of {len(members) - 3} more like these" if len(members) > 3 else ""
    return f"{FAMILIES[option['verb']]}: {shown}{more}"


# Each verb's option sentence; a new verb needs an entry here (and one in `activities.ACTIVITIES`).
_OPTIONS: Mapping[str, Callable[[Observation, Action], str]] = {
    "take_beer": _pour, "settle_in": _settle, "stand_a_round": _round, "rematch": _rematch, "drink": _drink, "rest": _rest, "seating": _seating, "sit": _sit, "doze": _doze, "talk": _talk,
    "approach": _approach, "join_conversation": _join, "play_darts": _darts, "stand_at_bar": _bar, "watch": _watch,
    "watch_dice": _watch_dice,
    "use_toilet": _toilet, "give": _give, "bring_drink": _bring,
    "inspect": _inspect, "wait": _wait, "leave": _leave, "cut_in_line": _cut, "shove": _shove, "start_fight": _fight,
    **FIGHT_TEXTS}
