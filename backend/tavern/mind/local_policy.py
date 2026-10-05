"""The local policy: what a visitor would score each option without a model, from their needs and temper."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from tavern.mind.goals import GOAL_PULL, goal_pull
from tavern.mind.hall_view import in_use, line_place
from tavern.social.hostility import urge
from tavern.social.thoughts import THOUGHTS, opinion_of, thought_mood


# How far the most and least sociable guests drift from an ordinary one's taste for company.
SOCIABLE_PULL = 0.4


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
    # The sociable lean toward company and loners away; 0.5 is ordinary, and scores stay within 0–1.
    company = SOCIABLE_PULL * (traits.get("sociability", 0.5) - 0.5)
    utility = {
        "drink": 0.9 * thirst + 0.1,
        "take_beer": max(0.0, 0.8 * thirst - 0.3 * bladder),
        "rest": fatigue * (0.85 + 0.15 * traits.get("comfort", 0.5)),
        "sit": seated_rest,
        "seating": 0.15 + 0.6 * actor["needs"].get("social", 0) / 100 if moving else seated_rest,
        "talk": min(1.0, max(0.0, 0.4 + 0.6 * actor["needs"].get("social", 0) / 100 + company)),
        # Joining company already talking is a little less natural than starting a chat.
        "join_conversation": min(1.0, max(0.0, 0.35 + 0.6 * actor["needs"].get("social", 0) / 100 + company)),
        "play_darts": 0.15 + 0.65 * actor["needs"].get("boredom", 0) / 100,
        # A chat across the bar suits the sociable and curious, once nothing presses.
        "stand_at_bar": max(0.0, 0.05 + 0.45 * actor["needs"].get("social", 0) / 100 + company
                            + 0.15 * traits.get("curiosity", 0.5) - 0.25 * max(thirst, fatigue, bladder)),
        # A gentler pastime than darts that comfort-loving visitors favour, once nothing presses.
        "watch": ((0.05 + 0.45 * actor["needs"].get("boredom", 0) / 100 + 0.3 * traits.get("comfort", 0.5))
                  * (1 - max(thirst, fatigue, bladder))),
        # A game draws the bored and the curious, unless a need presses.
        "watch_dice": max(0.0, 0.1 + 0.5 * actor["needs"].get("boredom", 0) / 100 + 0.25 * traits.get("curiosity", 0.5)
                          - 0.3 * max(thirst, fatigue, bladder)),
        "use_toilet": bladder,
        "inspect": 0.08 + 0.12 * traits.get("curiosity", 0.5) + 0.4 * missing_relief,
        "wait": max(0.0, 0.08 + 0.12 * traits.get("patience", 0.5) - 0.08 * max(thirst, fatigue, bladder)),
        "leave": _leave_utility(observation),
        "cut_in_line": 0.0,  # weighed against the wait in _score_lines
        "give": 0.0,  # weighed gift by gift in _score_gifts
        "bring_drink": 0.0,  # weighed with the gifts, as a trip for someone
        # Hostile acts are rare: even the hottest head scores them below a seat to rest in, and only the
        # urge (temper loosened by drink) lifts them; a fight is likelier than a shove only through Jev.
        "shove": 0.1 + 0.3 * min(1.0, urge(observation)),
        "start_fight": 0.05 + 0.2 * min(1.0, urge(observation)),
    }
    scores = {action["id"]: utility[action["verb"]] for action in candidates}
    _score_seats(observation, candidates, scores)
    _score_lines(observation, candidates, scores)
    _score_gifts(observation, candidates, scores, company)
    _score_goal(observation, candidates, scores)
    return scores


def _score_gifts(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                 scores: dict[str, float], company: float) -> None:
    # Handing something over is a small kindness, low in itself: warmer from a sociable guest and toward someone
    # they like. A mug is the better gift to hands that visibly hold none, and a thirsty guest keeps their own.
    # Fetching one is a trip too, which a need of their own, a full bladder or weariness, outweighs.
    actor, people = observation["actor"], {item["id"]: item for item in observation.get("people", [])}
    now, needs = observation.get("time", -math.inf), actor["needs"]
    for action in candidates:
        if action["verb"] not in ("give", "bring_drink"):
            continue
        score = 0.1 + company + 0.25 * opinion_of(actor, action["target_id"], now) / 100
        if action["verb"] == "bring_drink":
            score -= 0.3 * max(needs["fatigue"], needs["bladder"]) / 100
        elif action["item"] == "beer":
            empty = not people.get(action["target_id"], {}).get("holding", {}).get("beer", 0)
            score += 0.15 * empty - 0.4 * needs["thirst"] / 100
        scores[action["id"]] = min(1.0, max(0.0, score))


# What serving the guest's goal usually adds to an option's score (see `goals.GoalKind.pull`).
GOAL_BONUS = GOAL_PULL


def _score_goal(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                scores: dict[str, float]) -> None:
    for action in candidates:
        scores[action["id"]] = min(1.0, scores[action["id"]] + goal_pull(observation, action))


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
    # company offsets a slight. Observations built outside the world may carry no thoughts, which
    # read as none. Without a clock every thought counts.
    feeling = thought_mood(observation["actor"], observation.get("time", -math.inf))
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
    _score_goal(observation, candidates, scores)
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
