"""The options open to a guest now, from what they observe."""

from collections.abc import Mapping, Sequence
import math
from typing import Any, NotRequired, TypedDict

from tavern.body.items import ITEMS
from tavern.mind.families import group_families
from tavern.mind.fight_candidates import is_hurt, room_reactions, treatments
from tavern.mind.hall_view import in_use, line_place
from tavern.mind.local_policy import conviviality
from tavern.mind.observation import known_objects, own_actor
from tavern.mind.signature_candidates import signature_actions
from tavern.social.giving import empty_handed_company, empty_handed_tablemates, gift_targets
from tavern.social.responses import calling
from tavern.social.speeches import performs, spoke_lately
from tavern.social.hostility import HOSTILITY, hostile_targets
from tavern.social.tables import liked


# The thirst (0–100) from which a guest keeps their own mug of ale: a mild thirst (under the briefing's 50) gives way.
KEEPS_OWN_MUG = 50
# The tiredness (0–100) from which a guest in their seat may choose to sleep there.
SLEEPY = 60
# The thirst (0–100) from which a seatless guest may settle in with an ale: the briefing's "mild", as for the tap itself.
SETTLES_IN = 35


class Action(TypedDict):
    """An executable world command with a stable candidate identifier."""

    id: str
    verb: str
    target_id: str | None
    # The item from the actor's hands that a verb such as `give` names; absent for the others.
    item: NotRequired[str]
    # What a social verb (`aims.AIM_VERBS`) is for, once the third stage of the choice has picked it.
    aim: NotRequired[str]


def action(verb: str, target: str | None = None, item: str | None = None) -> Action:
    """Name an executable world command.

    Args:
        verb: The activity's name.
        target: The id of the object or visitor it is aimed at, if any.
        item: The item from the actor's hands that the verb names, if any.

    Returns:
        The `Action`, its id the verb, item and target joined by colons.
    """
    result: Action = {"id": ":".join(part for part in (verb, item, target) if part is not None),
                      "verb": verb, "target_id": target}
    return result if item is None else {**result, "item": item}


def build_candidates(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    """List a visitor's first-stage options: one per activity family.

    Args:
        observation: Own actor state and known/visible object records.

    Returns:
        The concrete actions of `_concrete_candidates`, grouped by `families.group_families`:
        a family with a single action is offered as that action, one with several as a
        family option holding its members, resolved by a second stage of the choice.

    Raises:
        ValueError: Observation, needs, inventory, closing flag or object records are malformed.
    """
    return group_families(_concrete_candidates(observation))


def _concrete_candidates(observation: Mapping[str, Any]) -> list[Action]:
    """Generate actions from personal inventory and individually observed objects.

    Args:
        observation: Own actor state and known/visible object records.

    Returns:
        Stable, unique action dictionaries. Inspection and waiting are always offered.
        Table chairs appear as one `seating` wish until the visitor owns a seat; their
        own free seat appears as `sit`, with `seating` again only while company they could
        join is in sight. A tired guest in their seat (`SLEEPY`) may also `doze` there. Leaving needs a known door; a door is shared (see
        `Activity.shared_target`), so it is never busy. Once the inn has closed, going home is
        the only option, or waiting a turn when no door is known.

    Raises:
        ValueError: Observation, needs, inventory, closing flag or object records are malformed.
    """
    actor, objects = own_actor(observation), known_objects(observation)
    talks = _social_candidates(observation, actor, objects)  # also validates the visible visitors
    if _closed(observation):
        return _going_home(observation, objects)
    if is_hurt(observation):
        # A hurt guest's business is to mend: a remedy, a healer to ask, or home to bed; nothing else is offered.
        return [*(action(verb, target) for verb, target in treatments(observation)), *_going_home(observation, objects)]
    # A mug is carried to a seat and drunk there, unless there is no seat to be had.
    seatless = not actor.get("seat_id") and not _free_seats(observation, objects)
    actions = [action("drink")] if actor["inventory"]["beer"] and (actor.get("seat_id") or seatless) else []
    verbs = {"tap": "take_beer", "chair": "rest", "toilet": "use_toilet", "darts": "play_darts", "door": "leave",
             "stage": "give_speech"}
    for item in sorted(objects, key=lambda item: item["id"]):
        if item["kind"] not in verbs or item.get("table_id"):
            continue
        if item["kind"] == "stage" and (spoke_lately(observation) or not performs(observation)):
            continue
        if item["kind"] == "tap" and (not item.get("stock") or actor["inventory"]["beer"] or _called(observation)):
            continue
        # Not thirsty enough to fetch an ale, unless the table is good company (`local_policy.conviviality`).
        if item["kind"] == "tap" and "social" in actor["needs"] and actor["needs"]["thirst"] < 35 \
                and not conviviality(observation):
            continue
        actions.extend(_line_options(observation, item, action(verbs[item["kind"]], item["id"])))
    return [*actions, *_seat_wish(observation, objects), *_views(observation, objects), *_games(objects),
            *_bar_stand(observation, actor, objects), *talks, *_gifts(observation, actor),
            *_fetches(observation, actor, objects), *_round(observation, actor, objects),
            *_rematches(observation, actor, objects), *_nap(observation, actor), *_settling(observation, actor, objects),
            action("inspect"), action("wait"), *_hostile(observation),
            *(action(verb, target) for verb, target in room_reactions(observation)),
            *(action(verb, target) for verb, target in
              signature_actions(observation, [item["target_id"] for item in talks if item["verb"] == "approach"]))]


def _line_options(observation: Mapping[str, Any], item: Mapping[str, Any], plain: Action) -> list[Action]:
    # A busy place with a line is still offered: choosing it means waiting in line, or keeping
    # one's place in it. Cutting in is offered while others wait ahead, unless the line is full.
    if "queue_spots" not in item:
        return [] if in_use(observation, item) else [plain]
    ahead, joined = line_place(observation, item)
    if not joined and ahead >= len(item["queue_spots"]):
        return []
    return [plain, *([action("cut_in_line", item["id"])] if ahead else [])]


def _closed(observation: Mapping[str, Any]) -> bool:
    # Observations built outside the world may omit the flag; that reads as an open inn.
    closed = observation.get("closed", False)
    if not isinstance(closed, bool):
        raise ValueError("Closing flag must be a boolean")
    return closed


def _called(observation: Mapping[str, Any]) -> bool:
    # The barkeep's call came `called_closing` seconds ago; the bar serves no new order after it, and nobody naps.
    # Observations built outside the world may omit it, which reads as no call yet.
    since = observation.get("called_closing")
    if since is not None and (isinstance(since, bool) or not isinstance(since, (int, float)) or since < 0):
        raise ValueError("Closing call age must be a nonnegative number or None")
    return since is not None


def _going_home(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    doors = [action("leave", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
             if item["kind"] == "door" and not in_use(observation, item)]
    return doors or [action("wait")]


def _views(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Any window shows the same road, so only the nearest free one is offered beside the fireplace;
    # a view needs somewhere to stand.
    actor = observation["actor"]
    free = [item for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] in ("window", "fireplace") and item.get("interaction_spots")
            and not in_use(observation, item)]
    nearest = min((item for item in free if item["kind"] == "window"), default=None,
                  key=lambda item: abs(item["x"] - actor["x"]) + abs(item["y"] - actor["y"]))
    return [action("watch", item["id"]) for item in free if item["kind"] == "fireplace" or item is nearest]


def _games(objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # A game under way, as the visitor last saw it (two players seated), draws onlookers to its table.
    return [action("watch_dice", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "dice_table" and len((item.get("game") or {}).get("players", [])) == 2]


def _bar_stand(observation: Mapping[str, Any], actor: Mapping[str, Any],
               objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Leaning on a bar is worth offering while a barkeep is in sight to chat with, the guest does not
    # already stand on one of its spots, and one of them has nobody on it.
    people = observation.get("people", [])
    if not any(person.get("post") for person in people):
        return []
    taken = {(person["x"], person["y"]) for person in people}
    return [action("stand_at_bar", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "bar" and [actor["x"], actor["y"]] not in item["interaction_spots"]
            and any(tuple(spot) not in taken for spot in item["interaction_spots"])]


def _gifts(observation: Mapping[str, Any], actor: Mapping[str, Any]) -> list[Action]:
    # Handing over what the guest carries is offered to the company near who could take it (`gift_targets`).
    # A thirsty guest drinks their own mug rather than give it away; what is in a pocket is theirs to give.
    thirsty = actor["needs"].get("thirst", 0) >= KEEPS_OWN_MUG
    return [action("give", target, kind) for kind in ITEMS if actor["inventory"].get(kind) and ITEMS[kind].giftable
            and not (kind == "beer" and thirsty) for target in gift_targets(observation, kind)]


def _fetches(observation: Mapping[str, Any], actor: Mapping[str, Any],
             objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # A guest with a free hand who knows a tap that has ale may fetch a drink for company with empty hands,
    # unless they are on an errand already.
    free_hand = actor["inventory"].get("beer", 0) < ITEMS["beer"].hands
    able = free_hand and actor["id"] not in observation.get("on_errands", []) and not _called(observation)
    stocked = any(item["kind"] == "tap" and item.get("stock") for item in objects)
    return [action("bring_drink", target) for target in empty_handed_company(observation)] if able and stocked else []


def _nap(observation: Mapping[str, Any], actor: Mapping[str, Any]) -> list[Action]:
    # A tired guest in their seat may sleep there, unless they are out on an errand for someone.
    sleepy = (actor["needs"]["fatigue"] >= SLEEPY and actor["id"] not in observation.get("on_errands", [])
              and not _called(observation))
    return [action("doze")] if sleepy and actor.get("seat_id") else []


def _settling(observation: Mapping[str, Any], actor: Mapping[str, Any],
              objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # A thirsty guest with no seat and no mug may take on the whole of coming in: an ale from the tap, a chair, the drink.
    # Only where the world has projects (`observation["projects"]`), and not for one out on an errand for someone.
    stocked = any(item["kind"] == "tap" and item.get("stock") for item in objects)
    able = (not actor.get("seat_id") and not actor["inventory"]["beer"] and actor["needs"]["thirst"] >= SETTLES_IN
            and actor["id"] not in observation.get("on_errands", []))
    return [action("settle_in")] if "settle_in" in observation.get("projects", []) and able and stocked \
        and _free_seats(observation, objects) else []


def _round(observation: Mapping[str, Any], actor: Mapping[str, Any],
           objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Standing the whole table a round: a seated guest with a free hand and a tap that has ale, and at least two
    # tablemates visibly holding no mug (a single one is just brought a drink).
    able = (actor["inventory"].get("beer", 0) < ITEMS["beer"].hands and actor["id"] not in observation.get("on_errands", [])
            and any(item["kind"] == "tap" and item.get("stock") for item in objects))
    return [action("stand_a_round")] if "stand_a_round" in observation.get("projects", []) and able \
        and len(empty_handed_tablemates(observation)) >= 2 else []


def _rematches(observation: Mapping[str, Any], actor: Mapping[str, Any],
               objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Asking someone who just beat them at dice for another game: while the loss still calls for an answer, the
    # winner is in sight and a dice table they know is free as far as they can tell.
    if "rematch" not in observation.get("projects", []) or actor["id"] in observation.get("on_errands", []):
        return []
    free = any(item["kind"] == "dice_table" and len((item.get("game") or {}).get("players", [])) < 2 for item in objects)
    lost = {item["about"] for item in calling(actor, observation.get("time", -math.inf)) if item["kind"] == "lost_at_dice"}
    # Only a winner they can get to: seated at a table, or standing beside them.
    return [action("rematch", person["id"]) for person in observation.get("people", [])
            if free and person["id"] in lost and not person.get("post")
            and (person.get("seat_id") or person.get("beside"))]


def _hostile(observation: Mapping[str, Any]) -> list[Action]:
    # Turning on someone is offered only to a guest with a grudge, a temper and the nerve (`hostility`);
    # a fight asks more than a shove, so every target of one is also a target of the other.
    return [action(verb, target) for verb in HOSTILITY.urge for target in hostile_targets(observation, verb)]


def _free_seats(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "chair" and item.get("table_id") and not in_use(observation, item)]


def _seat_wish(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Choosing a table seat takes two decisions: first whether to sit, then which chair.
    # Once seated, that chair is the visitor's own and they return to it; they choose again
    # only if it was taken, or to join company seen at a table with a free chair.
    actor, people = observation["actor"], observation.get("people", [])
    free = _free_seats(observation, objects)
    own = next((item for item in free if item["id"] == actor.get("favorite_seat_id")), None)
    if own is None:
        return [action("seating")] if free else []
    # Only company they like is worth moving to: a stranger's table is not theirs to sit at (walk over instead).
    now = observation.get("time", -math.inf)
    company = {item.get("table_id") for item in people if item.get("seat_id")
               and liked(actor, item["id"], now)} - {own["table_id"]}
    joinable = any(item["table_id"] in company for item in free)
    return [action("sit", own["id"]), *([action("seating")] if joinable else [])]


def build_seat_candidates(observation: Mapping[str, Any]) -> list[Action]:
    """List the chairs a visitor who decided to sit down can choose between.

    Args:
        observation: Own actor state and known/visible object records.

    Returns:
        A `sit` action for every known table chair nobody else holds, in stable ID order.

    Raises:
        ValueError: Observation, visit or object records are malformed.
    """
    own_actor(observation)
    return [action("sit", item["id"]) for item in _free_seats(observation, known_objects(observation))]


def _social_candidates(observation: Mapping[str, Any], actor: Mapping[str, Any],
                       objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Seated tablemates, or anyone standing beside them (`people`, when observed): talk to whoever
    # is free, or join a conversation already going, once per scene through its first member seen.
    # Anyone seated at another table, and anyone standing in the open in company or busy, can be walked over to.
    people = observation.get("people", [])
    if not isinstance(people, list):
        raise ValueError("Visible visitors must be a list")
    seat = next((item for item in objects if item["id"] == actor.get("seat_id")), None)
    table = seat.get("table_id") if seat else None
    options: dict[str, Action] = {}
    walks: dict[str, Action] = {}
    # Company they like at a table with a free chair is joined by sitting down (`_seat_wish`), not by a walk over.
    now, open_tables = observation.get("time", -math.inf), {item["table_id"] for item in _free_seats(observation, objects)}
    # Somewhere to stand at that table: a walk over is pointless while every spot has someone on it.
    taken = {(person["x"], person["y"]) for person in people if isinstance(person, Mapping)
             and "x" in person and "y" in person}
    standing_room = {item["id"]: not item.get("interaction_spots")
                     or any(tuple(spot) not in taken for spot in item["interaction_spots"])
                     for item in objects if item["kind"] == "table"}
    # Seated company comes first, then the rest, each in sight order: the first person seen for a scene or
    # a table sets the option, so this order decides which option the request lists first.
    for visitor in sorted(people, key=lambda item: not (isinstance(item, Mapping) and item.get("seat_id"))):
        if not isinstance(visitor, Mapping) or not isinstance(visitor.get("id"), str) or not visitor["id"]:
            raise ValueError("Visible visitors must have nonempty IDs")
        near = (table and visitor.get("seat_id") and visitor.get("table_id") == table) or visitor.get("beside")
        if visitor["id"] == actor["id"]:
            continue
        if not near:
            # Someone seated at another table: walk over for a word, one way in for each table.
            if visitor.get("seat_id") and visitor.get("table_id") and (visitor.get("available") or visitor.get("conversation")) \
                    and standing_room.get(visitor["table_id"], True) \
                    and not (liked(actor, visitor["id"], now) and visitor["table_id"] in open_tables):
                walks.setdefault(visitor["table_id"], action("approach", visitor["id"]))
            elif _worth_walking_up_to(visitor):
                walks.setdefault(visitor.get("conversation") or visitor["id"], action("approach", visitor["id"]))
            continue
        if visitor.get("available"):
            options.setdefault(visitor["id"], action("talk", visitor["id"]))
        elif visitor.get("conversation"):
            options.setdefault(visitor["conversation"], action("join_conversation", visitor["id"]))
    return [*options.values(), *walks.values()]


def _worth_walking_up_to(visitor: Mapping[str, Any]) -> bool:
    # Someone on their feet in the open, who is in company or visibly busy where they stand: an idle stander is about to
    # decide and move off, and a guest at a table's spot is reached through the table.
    return (not visitor.get("seat_id") and visitor.get("at_table") is None and not visitor.get("walking")
            and not visitor.get("post") and not visitor.get("asleep") and not visitor.get("fighting")
            and bool(visitor.get("conversation") or (visitor.get("available") and visitor.get("doing"))))
