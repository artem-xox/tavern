"""Personal-observation candidates and explicitly labeled local/Jev decisions."""

import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any, TypedDict

from tavern.briefing import brief, in_use
from tavern.jev import JevError, evaluate_actions, evaluate_seats
from tavern.selection import drawable, read_temperature, select


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
    """The model port of a decision: one evaluator per stage of choosing."""

    actions: Evaluator
    seats: Evaluator


class Decision(TypedDict):
    """A decision plus scores and a safe, visible fallback reason."""

    action: Action
    source: str
    scores: dict[str, float]
    error: str | None


def _number(value: Any, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{label} must be finite and between 0 and {maximum}")
    return float(value)


def _actor(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    actor = observation.get("actor")
    if not isinstance(actor, Mapping) or not isinstance(actor.get("id"), str) or not actor["id"]:
        raise ValueError("Observation must contain the NPC's own actor")
    needs, inventory, traits = actor.get("needs"), actor.get("inventory"), actor.get("traits", {})
    if not all(isinstance(value, Mapping) for value in (needs, inventory, traits)):
        raise ValueError("Actor needs, inventory and traits must be mappings")
    for name in ("thirst", "fatigue", "bladder"):
        _number(needs.get(name), name, 100)
    for name in ("social", "boredom"):
        _number(needs.get(name, 0), name, 100)
    beer = inventory.get("beer")
    if isinstance(beer, bool) or not isinstance(beer, int) or beer < 0:
        raise ValueError("Own beer inventory must be a nonnegative integer")
    for name in ("patience", "comfort", "curiosity"):
        _number(traits.get(name, 0.5), name, 1)
    _validate_visit(actor)
    return actor


def _validate_visit(actor: Mapping[str, Any]) -> None:
    # Observations built outside the world may omit the visit; that reads as a fresh arrival.
    visit = actor.get("visit", {})
    if not isinstance(visit, Mapping):
        raise ValueError("Visit must be a mapping")
    _number(visit.get("seconds", 0), "Visit seconds", math.inf)
    beers, grievances = visit.get("beers", 0), visit.get("grievances", [])
    if isinstance(beers, bool) or not isinstance(beers, int) or beers < 0:
        raise ValueError("Beers drunk must be a nonnegative integer")
    if not isinstance(grievances, list) or any(not isinstance(item, str) for item in grievances):
        raise ValueError("Grievances must be a list of strings")
    own = actor.get("favorite_seat_id")
    if own is not None and (not isinstance(own, str) or not own):
        raise ValueError("Own seat must be a chair ID or null")


def _known_objects(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    objects = observation.get("objects")
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
        raise ValueError("Observation objects must be a sequence")
    known = {}
    for item in objects:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("Observed objects must have nonempty string IDs")
        if item.get("kind") not in ("tap", "chair", "toilet", "table", "bar", "darts", "door", "window", "fireplace"):
            raise ValueError("Unknown observed object kind")
        if "appeal" in item:
            _number(item["appeal"], "Seat appeal", 1)
        if not isinstance(item.get("interaction_spots", []), list):
            raise ValueError("Observed interaction spots must be a list")
        if item["id"] in known and known[item["id"]] != item:
            raise ValueError("Conflicting observations of the same object")
        reservation = item.get("reserved_by")
        if reservation is not None and (not isinstance(reservation, str) or not reservation):
            raise ValueError("Observed reservation must be an actor ID or null")
        stock = item.get("stock")
        if stock is not None and (isinstance(stock, bool) or not isinstance(stock, int) or stock < 0):
            raise ValueError("Observed stock must be a nonnegative integer or unknown")
        known[item["id"]] = item
    return list(known.values())


def _action(verb: str, target: str | None = None) -> Action:
    return {"id": f"{verb}:{target}" if target is not None else verb,
            "verb": verb, "target_id": target}


def build_candidates(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
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
    actor, objects = _actor(observation), _known_objects(observation)
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
        if in_use(observation, item):
            continue
        if item["kind"] == "tap" and (not item.get("stock") or actor["inventory"]["beer"]):
            continue
        if item["kind"] == "tap" and "social" in actor["needs"] and actor["needs"]["thirst"] < 35:
            continue
        actions.append(_action(verbs[item["kind"]], item["id"]))
    return [*actions, *_seat_wish(observation, objects), *_views(observation, objects),
            *talks, _action("inspect"), _action("wait")]


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
    _actor(observation)
    return [_action("sit", item["id"]) for item in _free_seats(observation, _known_objects(observation))]


def _social_candidates(observation: Mapping[str, Any], actor: Mapping[str, Any],
                       objects: Sequence[Mapping[str, Any]]) -> list[Action]:
    visitors = observation.get("visitors", [])
    if not isinstance(visitors, list):
        raise ValueError("Visible visitors must be a list")
    seat = next((item for item in objects if item["id"] == actor.get("seat_id")), None)
    neighbors = {}
    for visitor in visitors:
        if not isinstance(visitor, Mapping) or not isinstance(visitor.get("id"), str) or not visitor["id"]:
            raise ValueError("Visible visitors must have nonempty IDs")
        if seat and seat.get("table_id") and visitor.get("table_id") == seat["table_id"] and visitor.get("available"):
            if visitor["id"] != actor["id"]:
                neighbors[visitor["id"]] = _action("talk", visitor["id"])
    return list(neighbors.values())


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
        "play_darts": 0.15 + 0.65 * actor["needs"].get("boredom", 0) / 100,
        # A gentler pastime than darts that comfort-loving visitors favour, once nothing presses.
        "watch": ((0.05 + 0.45 * actor["needs"].get("boredom", 0) / 100 + 0.3 * traits.get("comfort", 0.5))
                  * (1 - max(thirst, fatigue, bladder))),
        "use_toilet": bladder,
        "inspect": 0.08 + 0.12 * traits.get("curiosity", 0.5) + 0.4 * missing_relief,
        "wait": max(0.0, 0.08 + 0.12 * traits.get("patience", 0.5) - 0.08 * max(thirst, fatigue, bladder)),
        "leave": _leave_utility(observation),
    }
    scores = {action["id"]: utility[action["verb"]] for action in candidates}
    _score_seats(observation, candidates, scores)
    return scores


def _leave_utility(observation: Mapping[str, Any]) -> float:
    # Visitors go home content after a long evening with a few beers, or early when it goes wrong.
    actor = observation["actor"]
    needs, visit = actor["needs"], actor.get("visit", {})
    seconds, patience = visit.get("seconds", 0), actor.get("traits", {}).get("patience", 0.5)
    calm = 1 - sum(needs.get(name, 0) for name in ("thirst", "fatigue", "bladder", "social", "boredom")) / 500
    content = min(1.0, seconds / 240) * min(1.0, visit.get("beers", 0) / 3) * calm
    taps = [item for item in observation["objects"] if item["kind"] == "tap"]
    run_dry = bool(taps) and not any(item.get("stock") for item in taps) and not actor["inventory"]["beer"]
    upset = min(1.0, 0.35 * len(visit.get("grievances", [])) * (1.5 - patience)
                + (needs["thirst"] / 100 if run_dry else 0.0))
    return 0.05 + 0.75 * max(content, upset * min(1.0, seconds / 60))


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
    evaluators: Evaluators | None = None,
) -> dict[str, Any]:
    """Evaluate and select a candidate without blocking the world simulation.

    Args:
        observation: Private actor observation; no other NPC's state is used.
        config: Explicit API key, model, timeout and selection temperature.
        rng: Seeded random generator owned by the calling simulation.
        evaluators: Model port asked when the config holds a key. New callers pass it;
            None falls back to the Jev adapter (a known leak, see below).

    Returns:
        Action, normalized scores, actual decision source and visible fallback error.
        A missing key selects intentional local mode with no error. When the visitor
        chooses `seating`, a second evaluation picks the chair: the action then sits
        there and `seat` holds that stage's source, scores and error.

    Raises:
        ValueError: Observation or configuration is malformed.
    """
    # Known leak: without explicit evaluators the Jev functions imported into this module are
    # looked up at call time, which is the seam the Stage 0 tests patch.
    evaluators = evaluators or Evaluators(evaluate_actions, evaluate_seats)
    candidates = build_candidates(observation)
    temperature = read_temperature(config)
    decision = await _decide(observation, candidates, config, rng, temperature, _local_scores, evaluators.actions)
    if decision["action"]["verb"] != "seating":
        return decision
    seat = await _decide(observation, build_seat_candidates(observation), config, rng, temperature,
                         _local_seat_scores, evaluators.seats)
    return {**decision, "action": seat["action"], "seat": {key: seat[key] for key in ("source", "scores", "error")}}


def _evaluator_view(observation: Mapping[str, Any], candidates: Sequence[Action]) -> dict[str, Any]:
    # The evaluator reads the situation in plain words plus the visitor's exact numbers;
    # raw cell lists, maps and earlier scores are noise to it.
    actor = observation["actor"]
    keys = ("name", "needs", "traits", "inventory", "visit", "seat_id", "favorite_seat_id")
    return {**brief(observation, candidates), "self": {key: actor.get(key) for key in keys}}


async def _decide(
    observation: Mapping[str, Any], candidates: Sequence[Action], config: Mapping[str, Any], rng: Random,
    temperature: float, local: Callable[[Mapping[str, Any], Sequence[Action]], dict[str, float]],
    remote: Evaluator,
) -> dict[str, Any]:
    scores, source, error = local(observation, candidates), "local", None
    if config.get("typesafe_api_key"):
        try:
            scores = await remote(_evaluator_view(observation, candidates), candidates, config)
            source = "jev"
        except JevError as failure:
            error = str(failure)
    return {"action": select(drawable(candidates, scores), scores, temperature, rng),
            "source": source, "scores": scores, "error": error}

