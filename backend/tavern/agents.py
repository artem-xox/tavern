"""Personal-observation candidates and explicitly labeled local/Jev decisions."""

import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any, TypedDict

from tavern.briefing import brief, in_use, line_place
from tavern.families import family_scores, group_families
from tavern.jev import JevError, evaluate_actions, evaluate_seats
from tavern.observation import known_objects, own_actor
from tavern.selection import bounded, drawable, read_temperature, select
from tavern.thoughts import THOUGHTS, thought_mood


class Action(TypedDict):
    """An executable world command with a stable candidate identifier."""

    id: str
    verb: str
    target_id: str | None


# Scores each candidate 0–1 from the evaluator view, the candidates and the AI config;
# raises JevError on a recoverable model failure, which falls back to the local policy.
Evaluator = Callable[[Mapping[str, Any], Sequence[Action], Mapping[str, Any]], Awaitable[dict[str, float]]]


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


def _action(verb: str, target: str | None = None) -> Action:
    return {"id": f"{verb}:{target}" if target is not None else verb,
            "verb": verb, "target_id": target}


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
        join is in sight. Leaving needs a known, free door. Once the inn has closed, going
        home is the only option, or waiting a turn while every known door is busy.

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
    return [*actions, *_seat_wish(observation, objects), *_views(observation, objects),
            *talks, _action("inspect"), _action("wait")]


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
    company = {item.get("table_id") for item in visitors if item.get("seat_id")} - {own["table_id"]}
    joinable = any(item["table_id"] in company for item in free)
    return [_action("sit", own["id"]), *([_action("seating")] if joinable else [])]


def build_seat_candidates(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
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
    visitors, people = observation.get("visitors", []), observation.get("people", [])
    if not isinstance(visitors, list) or not isinstance(people, list):
        raise ValueError("Visible visitors must be a list")
    seat = next((item for item in objects if item["id"] == actor.get("seat_id")), None)
    table = seat.get("table_id") if seat else None
    options: dict[str, Action] = {}
    for visitor in [*visitors, *people]:
        if not isinstance(visitor, Mapping) or not isinstance(visitor.get("id"), str) or not visitor["id"]:
            raise ValueError("Visible visitors must have nonempty IDs")
        near = (table and visitor.get("seat_id") and visitor.get("table_id") == table) or visitor.get("beside")
        if not near or visitor["id"] == actor["id"]:
            continue
        if visitor.get("available"):
            options.setdefault(visitor["id"], _action("talk", visitor["id"]))
        elif visitor.get("conversation"):
            options.setdefault(visitor["conversation"], _action("join_conversation", visitor["id"]))
    return list(options.values())


def _local_scores(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    actor = observation["actor"]
    thirst, fatigue, bladder = (actor["needs"][name] / 100 for name in ("thirst", "fatigue", "bladder"))
    traits, verbs = actor.get("traits", {}), {action["verb"] for action in candidates}
    # Inspection gains priority when the agent lacks a known way to relieve a need.
    missing_relief = max(thirst if not {"drink", "take_beer"} & verbs else 0,
                         fatigue if not {"rest", "sit", "seating"} & verbs else 0,
                         bladder if "use_toilet" not in verbs else 0)
    seated_rest = 0.42 + 0.4 * fatigue + (0.15 if actor["inventory"]["beer"] else 0)
    # With their own seat free, choosing a seat again means moving to join company.
    moving = any(action["verb"] == "sit" for action in candidates)
    utility = {
        "drink": 0.9 * thirst + 0.1,
        "take_beer": max(0.0, 0.8 * thirst - 0.3 * bladder),
        "rest": fatigue * (0.85 + 0.15 * traits.get("comfort", 0.5)),
        "sit": seated_rest,
        "seating": 0.15 + 0.6 * actor["needs"].get("social", 0) / 100 if moving else seated_rest,
        "talk": 0.4 + 0.6 * actor["needs"].get("social", 0) / 100,
        # Joining company already talking is a little less natural than starting a chat.
        "join_conversation": 0.35 + 0.6 * actor["needs"].get("social", 0) / 100,
        "play_darts": 0.15 + 0.65 * actor["needs"].get("boredom", 0) / 100,
        # A gentler pastime than darts that comfort-loving visitors favour, once nothing presses.
        "watch": ((0.05 + 0.45 * actor["needs"].get("boredom", 0) / 100 + 0.3 * traits.get("comfort", 0.5))
                  * (1 - max(thirst, fatigue, bladder))),
        "use_toilet": bladder,
        "inspect": 0.08 + 0.12 * traits.get("curiosity", 0.5) + 0.4 * missing_relief,
        "wait": max(0.0, 0.08 + 0.12 * traits.get("patience", 0.5) - 0.08 * max(thirst, fatigue, bladder)),
        "leave": _leave_utility(observation),
        "cut_in_line": 0.0,  # weighed against the wait in _score_lines
    }
    scores = {action["id"]: utility[action["verb"]] for action in candidates}
    _score_seats(observation, candidates, scores)
    _score_lines(observation, candidates, scores)
    return scores


def _score_lines(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                 scores: dict[str, float]) -> None:
    # Each person ahead, including whoever uses the place, makes waiting less worthwhile, more so
    # for the impatient. Cutting in skips the wait but is rude, which the patient mind more.
    patience = observation["actor"].get("traits", {}).get("patience", 0.5)
    objects = {item["id"]: item for item in observation["objects"]}
    uses = {}
    for action in candidates:
        item = objects.get(action["target_id"])
        if item is None or "queue_spots" not in item or action["verb"] == "cut_in_line":
            continue
        ahead = line_place(observation, item)[0] + in_use(observation, item)
        uses[item["id"]] = scores[action["id"]]
        scores[action["id"]] = max(0.0, scores[action["id"]] - 0.1 * ahead * (1.5 - patience))
    for action in candidates:
        if action["verb"] == "cut_in_line":
            scores[action["id"]] = max(0.0, uses[action["target_id"]] - 0.35 - 0.4 * patience)


def _leave_utility(observation: Mapping[str, Any]) -> float:
    # Visitors go home content after a long evening with a few beers, or early when it goes wrong.
    actor = observation["actor"]
    needs, visit = actor["needs"], actor.get("visit", {})
    seconds, patience = visit.get("seconds", 0), actor.get("traits", {}).get("patience", 0.5)
    calm = 1 - sum(needs.get(name, 0) for name in ("thirst", "fatigue", "bladder", "social", "boredom")) / 500
    content = min(1.0, seconds / 240) * min(1.0, visit.get("beers", 0) / 3) * calm
    taps = [item for item in observation["objects"] if item["kind"] == "tap"]
    run_dry = bool(taps) and not any(item.get("stock") for item in taps) and not actor["inventory"]["beer"]
    upset = min(1.0, 0.35 * _wrongs(observation) * (1.5 - patience)
                + (needs["thirst"] / 100 if run_dry else 0.0))
    return 0.05 + 0.75 * max(content, upset * min(1.0, seconds / 60))


def _wrongs(observation: Mapping[str, Any]) -> float:
    # How wronged a visitor feels, in taken seats: their active thoughts' mood, where pleasant
    # company offsets a slight. Observations built outside the world may carry no thoughts;
    # then each listed grievance counts as one wrong. Without a clock every thought counts.
    actor = observation["actor"]
    if "thoughts" not in actor:
        return float(len(actor.get("visit", {}).get("grievances", [])))
    feeling = thought_mood(actor, observation.get("time", -math.inf))
    return max(0.0, -feeling) / -THOUGHTS["seat_taken"].mood


def _local_seat_scores(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    # Comfort-loving visitors care most about a cosy spot; company and distance adjust as for any seat.
    objects = {item["id"]: item for item in observation["objects"]}
    comfort = observation["actor"].get("traits", {}).get("comfort", 0.5)
    scores = {action["id"]: 0.3 + objects[action["target_id"]].get("appeal", 0.0) * (0.2 + 0.4 * comfort)
              for action in candidates}
    _score_seats(observation, candidates, scores)
    return scores


def _score_seats(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                 scores: dict[str, float]) -> None:
    actor = observation["actor"]
    company = {item.get("table_id") for item in observation.get("visitors", []) if item.get("seat_id")}
    objects = {item["id"]: item for item in observation["objects"]}
    for action in candidates:
        if action["verb"] != "sit":
            continue
        seat = objects[action["target_id"]]
        distance = abs(actor.get("x", 0) - seat.get("x", 0)) + abs(actor.get("y", 0) - seat.get("y", 0))
        scores[action["id"]] -= min(0.18, distance * 0.015)
        if seat.get("table_id") in company:
            scores[action["id"]] += 0.22 * actor["needs"].get("social", 0) / 100
        scores[action["id"]] = min(1.0, scores[action["id"]])


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
            None falls back to the Jev adapter (a known leak, see below).
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
    # Known leak: without explicit evaluators the Jev functions imported into this module are
    # looked up at call time, which is the seam the Stage 0 tests patch.
    evaluators = evaluators or Evaluators(evaluate_actions, evaluate_seats)
    options, temperature = build_candidates(observation), read_temperature(config)
    # Every concrete action is scored together, so a family is worth its best member.
    local = _local_scores(observation, [item for option in options for item in option.get("members", [option])])
    draw = (config, rng, temperature, limit)
    decision = await _decide(observation, options, family_scores(options, local), evaluators.actions, *draw)
    chosen = decision["action"]
    if chosen["verb"] == "seating":
        seats = build_seat_candidates(observation)
        seat = await _decide(observation, seats, _local_seat_scores(observation, seats), evaluators.seats, *draw)
        return {**decision, "action": seat["action"], "seat": _stage(seat)}
    if "members" not in chosen:
        return decision
    member = await _decide(observation, chosen["members"], local, evaluators.family or evaluators.actions, *draw)
    return {**decision, "action": member["action"], "family": {"name": chosen["id"], **_stage(member)}}


def _stage(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {key: decision[key] for key in ("source", "scores", "error")}


def _evaluator_view(observation: Mapping[str, Any], candidates: Sequence[Action]) -> dict[str, Any]:
    # The evaluator reads the situation in plain words plus the visitor's exact numbers;
    # raw cell lists, maps and earlier scores are noise to it.
    actor = observation["actor"]
    keys = ("name", "needs", "traits", "inventory", "visit", "seat_id", "favorite_seat_id")
    return {**brief(observation, candidates), "self": {key: actor.get(key) for key in keys}}


async def _decide(
    observation: Mapping[str, Any], candidates: Sequence[Action], local: Mapping[str, float], remote: Evaluator,
    config: Mapping[str, Any], rng: Random, temperature: float, limit: int,
) -> dict[str, Any]:
    candidates = bounded(candidates, local, limit)
    scores, source, error = {action["id"]: local[action["id"]] for action in candidates}, "local", None
    if config.get("typesafe_api_key"):
        try:
            scores = await remote(_evaluator_view(observation, candidates), candidates, config)
            source = "jev"
        except JevError as failure:
            error = str(failure)
    return {"action": select(drawable(candidates, scores), scores, temperature, rng),
            "source": source, "scores": scores, "error": error}
