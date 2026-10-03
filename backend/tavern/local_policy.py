"""The local policy: what a visitor would score each option without a model, from their needs and temper."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from tavern.hall_view import in_use, line_place
from tavern.thoughts import THOUGHTS, thought_mood


def local_scores(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Score concrete actions without a model, from the visitor's needs, traits and what they know.

    Args:
        observation: The visitor's own observation.
        candidates: Concrete actions (not family options), each with `id`, `verb` and `target_id`.

    Returns:
        A 0–1 score per candidate ID, in the same terms the model's rubric uses.
    """
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
    # Visitors go home content after a long evening with a few beers, or early when it goes wrong,
    # and at once when they agreed to walk home with someone (observations built outside the
    # world carry no invitations).
    actor = observation["actor"]
    if any(item["kind"] == "leave_together" and item["stage"] != "pending"
           for item in observation.get("invitations", [])):
        return 0.95
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


def local_seat_scores(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Score `sit` candidates without a model: comfort, company and distance.

    Args:
        observation: The visitor's own observation.
        candidates: `sit` actions, one per free chair.

    Returns:
        A 0–1 score per candidate ID.
    """
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
