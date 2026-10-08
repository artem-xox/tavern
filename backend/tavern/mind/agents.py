"""Personal-observation candidates and explicitly labeled local/Jev decisions."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from random import Random
from typing import Any, NotRequired, TypedDict

from tavern.body.items import ITEMS
from tavern.mind.briefing import brief
from tavern.mind.families import family_scores, group_families
from tavern.mind.hall_view import in_use, line_place
from tavern.mind.local_policy import local_scores, local_seat_scores
from tavern.mind.observation import known_objects, own_actor
from tavern.mind.selection import bounded, drawable, read_temperature, select
from tavern.social.giving import empty_handed_company, gift_targets
from tavern.social.hostility import HOSTILITY, hostile_targets
from tavern.social.tables import liked


# The thirst (0–100) from which a guest keeps their own mug of ale: a mild thirst (under the briefing's 50) gives way.
KEEPS_OWN_MUG = 50


class EvaluatorError(RuntimeError):
    """A recoverable failure of a model evaluator, safe to display in snapshots (`jev.JevError`).

    `status` is the HTTP status that caused it, when there was one.
    """

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Action(TypedDict):
    """An executable world command with a stable candidate identifier."""

    id: str
    verb: str
    target_id: str | None
    # The item from the actor's hands that a verb such as `give` names; absent for the others.
    item: NotRequired[str]


# Scores each candidate 0–1 from the evaluator view, the candidates and the AI config;
# raises EvaluatorError on a recoverable model failure, which falls back to the local policy.
Evaluator = Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]], Mapping[str, Any]], Awaitable[dict[str, float]]]


@dataclass(frozen=True)
class Evaluators:
    """The model port of a decision: one evaluator per stage of choosing.

    `actions` scores the first stage, one option per activity family; `seats` the chairs
    after `seating`; `family` the actions within another chosen family. Without `family`,
    `actions` scores those too: they are ordinary actions.
    """

    actions: Evaluator
    seats: Evaluator
    family: Evaluator | None = None


class Decision(TypedDict):
    """A decision plus scores and a safe, visible fallback reason."""

    action: Action
    source: str
    scores: dict[str, float]
    error: str | None


async def _unwired(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                   config: Mapping[str, Any]) -> dict[str, float]:
    raise ValueError("Asking a model needs evaluators; the shell supplies them")


def _action(verb: str, target: str | None = None, item: str | None = None) -> Action:
    action: Action = {"id": ":".join(part for part in (verb, item, target) if part is not None),
                      "verb": verb, "target_id": target}
    return action if item is None else {**action, "item": item}


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
        join is in sight. Leaving needs a known door; a door is shared (see
        `Activity.shared_target`), so it is never busy. Once the inn has closed, going home is
        the only option, or waiting a turn when no door is known.

    Raises:
        ValueError: Observation, needs, inventory, closing flag or object records are malformed.
    """
    actor, objects = own_actor(observation), known_objects(observation)
    talks = _social_candidates(observation, actor, objects)  # also validates the visible visitors
    if _closed(observation):
        return _going_home(observation, objects)
    # A mug is carried to a seat and drunk there, unless there is no seat to be had.
    seatless = not actor.get("seat_id") and not _free_seats(observation, objects)
    actions = [_action("drink")] if actor["inventory"]["beer"] and (actor.get("seat_id") or seatless) else []
    verbs = {"tap": "take_beer", "chair": "rest", "toilet": "use_toilet", "darts": "play_darts", "door": "leave"}
    for item in sorted(objects, key=lambda item: item["id"]):
        if item["kind"] not in verbs or item.get("table_id"):
            continue
        if item["kind"] == "tap" and (not item.get("stock") or actor["inventory"]["beer"]):
            continue
        if item["kind"] == "tap" and "social" in actor["needs"] and actor["needs"]["thirst"] < 35:
            continue
        actions.extend(_line_options(observation, item, _action(verbs[item["kind"]], item["id"])))
    return [*actions, *_seat_wish(observation, objects), *_views(observation, objects), *_games(objects),
            *_bar_stand(observation, actor, objects), *talks, *_gifts(observation, actor),
            *_fetches(observation, actor, objects), _action("inspect"), _action("wait"),
            *_hostile(observation)]


def _line_options(observation: Mapping[str, Any], item: Mapping[str, Any], action: Action) -> list[Action]:
    # A busy place with a line is still offered: choosing it means waiting in line, or keeping
    # one's place in it. Cutting in is offered while others wait ahead, unless the line is full.
    if "queue_spots" not in item:
        return [] if in_use(observation, item) else [action]
    ahead, joined = line_place(observation, item)
    if not joined and ahead >= len(item["queue_spots"]):
        return []
    return [action, *([_action("cut_in_line", item["id"])] if ahead else [])]


def _closed(observation: Mapping[str, Any]) -> bool:
    # Observations built outside the world may omit the flag; that reads as an open inn.
    closed = observation.get("closed", False)
    if not isinstance(closed, bool):
        raise ValueError("Closing flag must be a boolean")
    return closed


def _going_home(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    doors = [_action("leave", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
             if item["kind"] == "door" and not in_use(observation, item)]
    return doors or [_action("wait")]


def _views(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Any window shows the same road, so only the nearest free one is offered beside the fireplace;
    # a view needs somewhere to stand.
    actor = observation["actor"]
    free = [item for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] in ("window", "fireplace") and item.get("interaction_spots")
            and not in_use(observation, item)]
    nearest = min((item for item in free if item["kind"] == "window"), default=None,
                  key=lambda item: abs(item["x"] - actor["x"]) + abs(item["y"] - actor["y"]))
    return [_action("watch", item["id"]) for item in free if item["kind"] == "fireplace" or item is nearest]


def _games(objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # A game under way, as the visitor last saw it (two players seated), draws onlookers to its table.
    return [_action("watch_dice", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "dice_table" and len((item.get("game") or {}).get("players", [])) == 2]


def _bar_stand(observation: Mapping[str, Any], actor: Mapping[str, Any],
               objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Leaning on a bar is worth offering while a barkeep is in sight to chat with, the guest does not
    # already stand on one of its spots, and one of them has nobody on it.
    people = observation.get("people", [])
    if not any(person.get("post") for person in people):
        return []
    taken = {(person["x"], person["y"]) for person in people}
    return [_action("stand_at_bar", item["id"]) for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "bar" and [actor["x"], actor["y"]] not in item["interaction_spots"]
            and any(tuple(spot) not in taken for spot in item["interaction_spots"])]


def _gifts(observation: Mapping[str, Any], actor: Mapping[str, Any]) -> list[Action]:
    # Handing over what the guest carries is offered to the company near who could take it (`gift_targets`).
    # A thirsty guest drinks their own mug rather than give it away; what is in a pocket is theirs to give.
    thirsty = actor["needs"].get("thirst", 0) >= KEEPS_OWN_MUG
    return [_action("give", target, kind) for kind in ITEMS if actor["inventory"].get(kind)
            and not (kind == "beer" and thirsty) for target in gift_targets(observation, kind)]


def _fetches(observation: Mapping[str, Any], actor: Mapping[str, Any],
             objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # A guest with a free hand who knows a tap that has ale may fetch a drink for company with empty hands,
    # unless they are on an errand already.
    free_hand = actor["inventory"].get("beer", 0) < ITEMS["beer"].hands
    able = free_hand and actor["id"] not in observation.get("on_errands", [])
    stocked = any(item["kind"] == "tap" and item.get("stock") for item in objects)
    return [_action("bring_drink", target) for target in empty_handed_company(observation)] if able and stocked else []


def _hostile(observation: Mapping[str, Any]) -> list[Action]:
    # Turning on someone is offered only to a guest with a grudge, a temper and the nerve (`hostility`);
    # a fight asks more than a shove, so every target of one is also a target of the other.
    return [_action(verb, target) for verb in HOSTILITY.urge for target in hostile_targets(observation, verb)]


def _free_seats(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in sorted(objects, key=lambda item: item["id"])
            if item["kind"] == "chair" and item.get("table_id") and not in_use(observation, item)]


def _seat_wish(observation: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Choosing a table seat takes two decisions: first whether to sit, then which chair.
    # Once seated, that chair is the visitor's own and they return to it; they choose again
    # only if it was taken, or to join company seen at a table with a free chair.
    actor, visitors = observation["actor"], observation.get("visitors", [])
    free = _free_seats(observation, objects)
    own = next((item for item in free if item["id"] == actor.get("favorite_seat_id")), None)
    if own is None:
        return [_action("seating")] if free else []
    # Only company they like is worth moving to: a stranger's table is not theirs to sit at (walk over instead).
    now = observation.get("time", -math.inf)
    company = {item.get("table_id") for item in visitors if item.get("seat_id")
               and liked(actor, item["id"], now)} - {own["table_id"]}
    joinable = any(item["table_id"] in company for item in free)
    return [_action("sit", own["id"]), *([_action("seating")] if joinable else [])]


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
    return [_action("sit", item["id"]) for item in _free_seats(observation, known_objects(observation))]


def _social_candidates(observation: Mapping[str, Any], actor: Mapping[str, Any],
                       objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    # Seated tablemates, or anyone standing beside them (`people`, when observed): talk to whoever
    # is free, or join a conversation already going, once per scene through its first member seen.
    # Anyone seated at another table can be walked over to.
    visitors, people = observation.get("visitors", []), observation.get("people", [])
    if not isinstance(visitors, list) or not isinstance(people, list):
        raise ValueError("Visible visitors must be a list")
    seat = next((item for item in objects if item["id"] == actor.get("seat_id")), None)
    table = seat.get("table_id") if seat else None
    options: dict[str, Action] = {}
    walks: dict[str, Action] = {}
    # Company they like at a table with a free chair is joined by sitting down (`_seat_wish`), not by a walk over.
    now, open_tables = observation.get("time", -math.inf), {item["table_id"] for item in _free_seats(observation, objects)}
    # Somewhere to stand at that table: a walk over is pointless while every spot has someone on it.
    taken = {(person["x"], person["y"]) for person in [*visitors, *people] if isinstance(person, Mapping)
             and "x" in person and "y" in person}
    standing_room = {item["id"]: not item.get("interaction_spots")
                     or any(tuple(spot) not in taken for spot in item["interaction_spots"])
                     for item in objects if item["kind"] == "table"}
    for visitor in [*visitors, *people]:
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
                walks.setdefault(visitor["table_id"], _action("approach", visitor["id"]))
            continue
        if visitor.get("available"):
            options.setdefault(visitor["id"], _action("talk", visitor["id"]))
        elif visitor.get("conversation"):
            options.setdefault(visitor["conversation"], _action("join_conversation", visitor["id"]))
    return [*options.values(), *walks.values()]


async def choose_action(
    observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random,
    evaluators: Evaluators | None = None, limit: int = 8,
) -> dict[str, Any]:
    """Evaluate and select a candidate without blocking the world simulation.

    Args:
        observation: Private actor observation; no other NPC's state is used.
        config: Explicit API key, model, timeout and selection temperature.
        rng: Seeded random generator owned by the calling simulation.
        evaluators: Model port asked when the config holds a key. New callers pass it;
            None asks no model: a config with a model key then fails loudly.
        limit: Most options one request may hold; the local policy keeps the best ones.

    Returns:
        Action, normalized scores, actual decision source and visible fallback error.
        A missing key selects intentional local mode with no error. The first stage scores
        one option per activity family. When the visitor chooses `seating`, a second
        evaluation picks the chair and `seat` holds that stage's source, scores and error;
        when they choose a family of several actions, a second evaluation picks one of them
        and `family` holds the family's name and that stage's source, scores and error.

    Raises:
        ValueError: Observation, configuration or limit is malformed.
    """
    evaluators = evaluators or Evaluators(_unwired, _unwired)
    options, temperature = build_candidates(observation), read_temperature(config)
    # Every concrete action is scored together, so a family is worth its best member.
    local = local_scores(observation, [item for option in options for item in option.get("members", [option])])
    draw = (config, rng, temperature, limit)
    decision = await _decide(observation, options, family_scores(options, local), evaluators.actions, *draw)
    chosen = decision["action"]
    if chosen["verb"] == "seating":
        seats = build_seat_candidates(observation)
        seat = await _decide(observation, seats, local_seat_scores(observation, seats), evaluators.seats, *draw)
        return {**decision, "action": seat["action"], "seat": _stage(seat)}
    if "members" not in chosen:
        return decision
    member = await _decide(observation, chosen["members"], local, evaluators.family or evaluators.actions, *draw)
    return {**decision, "action": member["action"], "family": {"name": chosen["id"], **_stage(member)}}


def _stage(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {key: decision[key] for key in ("source", "scores", "error")}


def _evaluator_view(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # The evaluator reads the situation in plain words plus the visitor's exact numbers;
    # raw cell lists, maps and earlier scores are noise to it.
    actor = observation["actor"]
    keys = ("name", "needs", "traits", "inventory", "visit", "seat_id", "favorite_seat_id")
    return {**brief(observation, candidates), "self": {key: actor.get(key) for key in keys}}


async def _decide(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], local: Mapping[str, float], remote: Evaluator,
    config: Mapping[str, Any], rng: Random, temperature: float, limit: int,
) -> dict[str, Any]:
    candidates = bounded(candidates, local, limit)
    scores, source, error = {action["id"]: local[action["id"]] for action in candidates}, "local", None
    if config.get("typesafe_api_key"):
        try:
            scores = await remote(_evaluator_view(observation, candidates), candidates, config)
            source = "jev"
        except EvaluatorError as failure:
            error = str(failure)
    return {"action": select(drawable(candidates, scores), scores, temperature, rng),
            "source": source, "scores": scores, "error": error}
