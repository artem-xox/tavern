"""Personal-observation candidates and explicitly labeled local/Jev decisions."""

import math
from collections.abc import Mapping, Sequence
from random import Random
from typing import Any, TypedDict

from tavern.jev import JevError, evaluate_actions


class Action(TypedDict):
    """An executable world command with a stable candidate identifier."""

    id: str
    verb: str
    target_id: str | None


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
    return actor


def _known_objects(observation: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    objects = observation.get("objects")
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
        raise ValueError("Observation objects must be a sequence")
    known = {}
    for item in objects:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("Observed objects must have nonempty string IDs")
        if item.get("kind") not in ("tap", "chair", "toilet", "table", "bar", "darts"):
            raise ValueError("Unknown observed object kind")
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

    Raises:
        ValueError: Observation, needs, inventory or object records are malformed.
    """
    actor, objects = _actor(observation), _known_objects(observation)
    actions = [_action("drink")] if actor["inventory"]["beer"] else []
    verbs = {"tap": "take_beer", "chair": "rest", "toilet": "use_toilet", "darts": "play_darts"}
    for item in sorted(objects, key=lambda item: item["id"]):
        if item["kind"] not in verbs:
            continue
        if item.get("reserved_by") not in (None, actor["id"]):
            continue
        if item["kind"] == "tap" and (not item.get("stock") or actor["inventory"]["beer"]):
            continue
        if item["kind"] == "tap" and "social" in actor["needs"] and actor["needs"]["thirst"] < 35:
            continue
        verb = "sit" if item["kind"] == "chair" and item.get("table_id") else verbs[item["kind"]]
        actions.append(_action(verb, item["id"]))
    return [*actions, *_social_candidates(observation, actor, objects), _action("inspect"), _action("wait")]


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
                         fatigue if not {"rest", "sit"} & verbs else 0, bladder if "use_toilet" not in verbs else 0)
    utility = {
        "drink": 0.9 * thirst + 0.1,
        "take_beer": max(0.0, 0.8 * thirst - 0.3 * bladder),
        "rest": fatigue * (0.85 + 0.15 * traits.get("comfort", 0.5)),
        "sit": 0.42 + 0.4 * fatigue + (0.15 if actor["inventory"]["beer"] else 0),
        "talk": 0.4 + 0.6 * actor["needs"].get("social", 0) / 100,
        "play_darts": 0.15 + 0.65 * actor["needs"].get("boredom", 0) / 100,
        "use_toilet": bladder,
        "inspect": 0.08 + 0.12 * traits.get("curiosity", 0.5) + 0.4 * missing_relief,
        "wait": max(0.0, 0.08 + 0.12 * traits.get("patience", 0.5) - 0.08 * max(thirst, fatigue, bladder)),
    }
    scores = {action["id"]: utility[action["verb"]] for action in candidates}
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


def _temperature(config: Mapping[str, Any]) -> float:
    value = config.get("temperature")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Temperature must be a nonnegative finite number")
    return float(value)


def _select(candidates: Sequence[Action], scores: Mapping[str, float], temperature: float, rng: Random) -> Action:
    best = max(scores.values())
    if temperature == 0:
        return max(candidates, key=lambda action: scores[action["id"]])
    weights = [math.exp((scores[action["id"]] - best) / temperature) for action in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


async def choose_action(
    observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random,
) -> dict[str, Any]:
    """Evaluate and select a candidate without blocking the world simulation.

    Args:
        observation: Private actor observation; no other NPC's state is used.
        config: Explicit API key, model, timeout and selection temperature.
        rng: Seeded random generator owned by the calling simulation.

    Returns:
        Action, normalized scores, actual decision source and visible fallback error.
        A missing key selects intentional local mode with no error.

    Raises:
        ValueError: Observation or configuration is malformed.
    """
    candidates = build_candidates(observation)
    temperature = _temperature(config)
    scores, source, error = _local_scores(observation, candidates), "local", None
    if config.get("typesafe_api_key"):
        try:
            scores = await evaluate_actions(observation, candidates, config)
            source = "jev"
        except JevError as failure:
            error = str(failure)
    return {"action": _select(candidates, scores, temperature, rng),
            "source": source, "scores": scores, "error": error}
