"""The local policy: what a visitor would score each option without a model, from their needs and temper."""

from collections.abc import Mapping, Sequence
import math
from types import MappingProxyType
from typing import Any

from tavern.body.ailment import carries_cure
from tavern.body.items import ITEMS
from tavern.body.wounds import health_of, hurt
from tavern.mind.fight_policy import hatred_scores, utilities as fight_utilities
from tavern.mind.goals import serving
from tavern.mind.hall_view import in_use, line_place, steps_to
from tavern.social.giving import empty_handed_tablemates
from tavern.social.hostility import urge
from tavern.social.responses import answering
from tavern.social.tables import liked
from tavern.social.thoughts import THOUGHTS, opinion_of, thought_mood


# How far the most and least sociable guests drift from an ordinary one's taste for company.
SOCIABLE_PULL = 0.4
# What a walk over to someone who looks unwell adds for a guest who carries a cure, and how a remedy for them scores.
SEEKING_THE_SICK = 0.5
CURE_SCORE = 0.95


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
    # Sitting no longer eases tiredness (only sleep does), so weariness barely weighs here.
    seated_rest = 0.42 + 0.15 * fatigue + (0.15 if actor["inventory"]["beer"] else 0)
    # With their own seat free, choosing a seat again means moving to join company.
    moving = any(action["verb"] == "sit" for action in candidates)
    # The sociable lean toward company and loners away; 0.5 is ordinary, and scores stay within 0–1.
    company = SOCIABLE_PULL * (traits.get("sociability", 0.5) - 0.5)
    utility = {
        "drink": 0.9 * thirst + 0.1,
        "take_beer": max(0.0, 0.8 * thirst - 0.3 * bladder),
        # The whole of coming in thirsty, a little above fetching the ale alone (tap, then chair, then the drink).
        "settle_in": min(1.0, 0.1 + 0.8 * thirst - 0.3 * bladder),
        "rest": fatigue * (0.85 + 0.15 * traits.get("comfort", 0.5)),
        "sit": seated_rest,
        "seating": 0.15 + 0.6 * actor["needs"].get("social", 0) / 100 if moving else seated_rest,
        "talk": min(1.0, max(0.0, 0.4 + 0.6 * actor["needs"].get("social", 0) / 100 + company)),
        # A walk over to another table is a little less natural than a chat within reach (see `_score_approaches`).
        "approach": min(1.0, max(0.0, 0.1 + 0.6 * actor["needs"].get("social", 0) / 100 + company)),
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
        # Sleep suits a guest who is tired, and more so one who has drunk: they sleep it off where they sit.
        "doze": min(1.0, max(0.0, 2.2 * (fatigue - 0.6)) + 0.9 * actor.get("drunkenness", 0.0)),
        "inspect": 0.08 + 0.12 * traits.get("curiosity", 0.5) + 0.4 * missing_relief,
        "wait": max(0.0, 0.08 + 0.12 * traits.get("patience", 0.5) - 0.08 * max(thirst, fatigue, bladder)),
        "leave": _leave_utility(observation),
        "cut_in_line": 0.0,  # weighed against the wait in _score_lines
        "give": 0.0,  # weighed gift by gift in _score_gifts
        "bring_drink": 0.0,  # weighed with the gifts, as a trip for someone
        "stand_a_round": 0.0,  # weighed with the gifts, as trips for several
        # Another go at someone who just won: the bored and the hot-tempered want it most.
        "rematch": min(1.0, 0.2 + 0.4 * actor["needs"].get("boredom", 0) / 100 + 0.3 * traits.get("temper", 0.5)),
        # Hostile acts are rare: even the hottest head scores them below a seat to rest in, and only the
        # urge (temper loosened by drink) lifts them; a fight is likelier than a shove only through Jev.
        "shove": 0.1 + 0.3 * min(1.0, urge(observation)),
        "start_fight": 0.05 + 0.2 * min(1.0, urge(observation)),
        **fight_utilities(observation),
    }
    scores = {action["id"]: utility[action["verb"]] for action in candidates}
    _score_seats(observation, candidates, scores)
    _score_lines(observation, candidates, scores)
    _score_gifts(observation, candidates, scores, company)
    _score_approaches(observation, candidates, scores)
    _score_goal(observation, candidates, scores)
    _score_answers(observation, candidates, scores)
    hatred_scores(observation, candidates, scores)
    return scores


def _score_gifts(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                 scores: dict[str, float], company: float) -> None:
    # Handing something over is a small kindness, low in itself: warmer from a sociable guest and toward someone
    # they like. A mug is the better gift to hands that visibly hold none, and a thirsty guest keeps their own.
    # Fetching one is a trip too, which a need of their own, a full bladder or weariness, outweighs.
    actor, people = observation["actor"], {item["id"]: item for item in observation.get("people", [])}
    now, needs = observation.get("time", -math.inf), actor["needs"]
    for action in candidates:
        if action["verb"] not in ("give", "bring_drink", "stand_a_round"):
            continue
        if action["verb"] == "stand_a_round":
            # Fetching for each of the empty-handed at their table, a little more worth the trip for each beyond one.
            receivers = empty_handed_tablemates(observation)
            liking = sum(opinion_of(actor, person, now) for person in receivers) / max(1, len(receivers))
            score = 0.1 + company + 0.25 * liking / 100 + 0.1 * (len(receivers) - 1)
            score -= 0.3 * max(needs["fatigue"], needs["bladder"]) / 100
            scores[action["id"]] = min(1.0, max(0.0, score))
            continue
        score = 0.1 + company + 0.25 * opinion_of(actor, action["target_id"], now) / 100
        if action["verb"] == "bring_drink":
            score -= 0.3 * max(needs["fatigue"], needs["bladder"]) / 100
        elif action["item"] == "beer":
            empty = not people.get(action["target_id"], {}).get("holding", {}).get("beer", 0)
            score += 0.15 * empty - 0.4 * needs["thirst"] / 100
        scores[action["id"]] = min(1.0, max(0.0, score))
        # A remedy for someone who looks unwell is what a healer carries it for: little outweighs it.
        if action["verb"] == "give" and ITEMS[action["item"]].cures and _unwell(people.get(action["target_id"], {})):
            scores[action["id"]] = CURE_SCORE


def _unwell(person: Mapping[str, Any]) -> bool:
    # Someone who came in with a fever, or is hurt, whom a healer's remedy would help.
    return bool(person.get("ailing") or person.get("hurt"))


def _score_approaches(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                      scores: dict[str, float]) -> None:
    # The walk costs a little, a long one more; company they like draws and company they dislike repels.
    actor, now = observation["actor"], observation.get("time", -math.inf)
    healer = carries_cure(actor["inventory"])
    people = {item["id"]: item for item in [*observation.get("visitors", []), *observation.get("people", [])]}
    objects = {item["id"]: item for item in observation["objects"]}
    for action in candidates:
        if action["verb"] != "approach":
            continue
        table = objects.get(people.get(action["target_id"], {}).get("table_id"))
        walk = steps_to(observation, table) if table else 0
        score = scores[action["id"]] - min(0.15, 0.01 * walk) + 0.25 * opinion_of(actor, action["target_id"], now) / 100
        # Someone who carries a cure goes to the one who looks unwell (`tavern.body.ailment`) before anyone else.
        if healer and _unwell(people.get(action["target_id"], {})):
            score += SEEKING_THE_SICK
        scores[action["id"]] = min(1.0, max(0.0, score))


# The local score at which a fixture is worth a model's slot (`selection.worth_asking`): the guest's state lifts it
# over the floor when it matters. `inspect` from a need of about 40 with no known relief; `use_toilet` from a bladder
# of 25 ("mild" in the briefing); `leave` once the evening has given them what they came for, or has gone sour;
# `wait`, the one way to stay put, unless a need of about 50 presses (its score is then under 0.1).
ASK_FLOOR: Mapping[str, float] = MappingProxyType({"inspect": 0.3, "wait": 0.1, "use_toilet": 0.25, "leave": 0.25})

# What serving the guest's goal adds to an option's score: enough to tip a near tie, not to outweigh a pressing need.
GOAL_BONUS = 0.3


def _score_goal(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                scores: dict[str, float]) -> None:
    for action in candidates:
        if serving(observation, action):
            scores[action["id"]] = min(1.0, scores[action["id"]] + GOAL_BONUS)


def _score_answers(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                   scores: dict[str, float]) -> None:
    # Answering what was just done to them is tempting by temper after a wrong, and by sociability after a kindness.
    # A thought that lowers the mood is a wrong.
    actor, now = observation["actor"], observation.get("time", -math.inf)
    for action in candidates:
        thought = answering(actor, now, action)
        if thought is not None:
            urge_to_answer = actor.get("traits", {}).get("temper" if thought["mood"] < 0 else "sociability", 0.5)
            scores[action["id"]] = min(1.0, scores[action["id"]] + 0.1 + 0.3 * urge_to_answer)


def local_aim_scores(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Score the aims of a social option without a model, from the guest's needs, traits and opinion of the person.

    Args:
        observation: The guest's observation.
        candidates: Aim candidates (`aims.aim_candidates`), each with its `aim` and the person as `target_id`.

    Returns:
        A 0-1 score per candidate ID. Each kind's starting point is a guess to be tuned on offline evenings: small talk
        is the ordinary reason (0.4), news tempts the curious, a game or an invitation the bored or lonely, winning
        over the sociable, and a needle or a quarrel the hot-tempered against someone they think ill of.
    """
    actor, now = observation["actor"], observation.get("time", -math.inf)
    traits, needs = actor.get("traits", {}), actor["needs"]
    temper, sociability, curiosity = (traits.get(name, 0.5) for name in ("temper", "sociability", "curiosity"))
    scores = {}
    for candidate in candidates:
        kind, _, detail = candidate["aim"].partition(":")
        opinion = opinion_of(actor, candidate["target_id"], now) / 100
        invitation = {"darts_together": 0.2 + 0.5 * needs.get("boredom", 0) / 100,
                      "dice_together": 0.2 + 0.5 * needs.get("boredom", 0) / 100,
                      "buy_drink": 0.2 + 0.4 * max(0.0, opinion),
                      "join_table": 0.2 + 0.4 * needs.get("social", 0) / 100}
        score = {"pass_time": 0.4, "tell_news": 0.25 + 0.3 * curiosity, "invite": invitation.get(detail, 0.0),
                 "win_over": 0.2 + 0.4 * sociability, "needle": 0.1 + 0.5 * temper * max(0.0, -opinion),
                 "have_it_out": 0.2 + 0.5 * temper, "thank": 0.5,
                 "rematch": 0.2 + 0.4 * needs.get("boredom", 0) / 100 + 0.3 * temper}[kind]
        scores[candidate["id"]] = min(1.0, max(0.0, score))
    return scores


def _invitation_worth(observation: Mapping[str, Any], kind: str) -> float:
    # What each thing an invitation leads to is worth to this guest now, in the terms of the options it stands for.
    needs = observation["actor"]["needs"]
    return {"darts_together": 0.15 + 0.65 * needs.get("boredom", 0) / 100,
            "dice_together": 0.15 + 0.65 * needs.get("boredom", 0) / 100,
            "buy_drink": 0.4 + 0.5 * needs["thirst"] / 100,  # an ale is always welcome
            "join_table": 0.2 + 0.6 * needs.get("social", 0) / 100,
            "move_together": 0.2 + 0.6 * needs.get("social", 0) / 100,
            "leave_together": _leave_utility(observation)}[kind]


def local_answer_scores(observation: Mapping[str, Any], invitation: Mapping[str, Any],
                        candidates: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Score how a guest might answer an invitation without a model.

    Args:
        observation: The invitee's observation.
        invitation: The pending invitation (`kind`, `from`).
        candidates: Answer candidates, each with its `answer`: `accept`, `decline` or `counter:<kind>`.

    Returns:
        A 0-1 score per candidate ID: accepting is worth what the invitation leads to plus a quarter of the opinion of
        whoever asks, declining is worth more to the unsociable, and a counter is worth its own kind a little less than
        accepting would be, since the guest sets it up themselves.
    """
    actor, now = observation["actor"], observation.get("time", -math.inf)
    worth = _invitation_worth(observation, invitation["kind"])
    liking = 0.25 * opinion_of(actor, invitation["from"], now) / 100
    scores = {}
    for candidate in candidates:
        answer = candidate["answer"]
        score = (worth + liking if answer == "accept"
                 else 0.3 + 0.2 * (1 - actor.get("traits", {}).get("sociability", 0.5)) if answer == "decline"
                 else _invitation_worth(observation, answer.partition(":")[2]) - 0.1)
        scores[candidate["id"]] = min(1.0, max(0.0, score))
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
    # A tired guest who has stayed a while means to go home to bed, less so one who has drunk: they sleep it off.
    weary = (min(1.0, max(0.0, (needs["fatigue"] / 100 - 0.6) / 0.3)) * (1 - 0.6 * actor.get("drunkenness", 0.0))
             * min(1.0, seconds / 180))
    wish = 0.05 + 0.75 * max(content, weary, upset * min(1.0, seconds / 60))
    # A hurt guest means to go home and mend (a healer in sight scores higher, see `fight_policy`); a timid one
    # has little wish to stay where a fight is on.
    if hurt(actor):
        wish = max(wish, 0.55 + 0.4 * (1 - health_of(actor) / 100))
    if any(person.get("fighting") for person in observation.get("people", [])):
        wish = max(wish, 0.15 + 0.5 * (1 - actor.get("traits", {}).get("courage", 0.5)))
    # Once the barkeep has called closing time everyone means to go: at first a guest finishes their mug or their
    # chat, 40 s on nothing but a pressing need outweighs the door (a full bladder scores 1.0). 0.95 is as strong as
    # walking home with someone.
    called = observation.get("called_closing")
    return wish if called is None else max(wish, 0.5 + 0.45 * min(1.0, called / 40))


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


# What sitting where one is not welcome costs a seat's score: at a table others hold, whose hosts the guest does not
# like, or in a chair that is somebody's own, which is worse.
UNINVITED = 0.25
SOMEONES_OWN = 0.5


def _score_seats(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                 scores: dict[str, float]) -> None:
    actor, now = observation["actor"], observation.get("time", -math.inf)
    company = {item.get("table_id") for item in observation.get("visitors", []) if item.get("seat_id")}
    objects = {item["id"]: item for item in observation["objects"]}
    for action in candidates:
        if action["verb"] != "sit":
            continue
        seat = objects[action["target_id"]]
        distance = abs(actor.get("x", 0) - seat.get("x", 0)) + abs(actor.get("y", 0) - seat.get("y", 0))
        scores[action["id"]] -= min(0.18, distance * 0.015)
        hosts = objects.get(seat.get("table_id"), {}).get("hosts", [])
        if seat.get("owner"):
            scores[action["id"]] -= SOMEONES_OWN
        elif hosts and not any(liked(actor, host["id"], now) for host in hosts):
            scores[action["id"]] -= UNINVITED
        elif seat.get("table_id") in company:
            scores[action["id"]] += 0.22 * actor["needs"].get("social", 0) / 100
        scores[action["id"]] = min(1.0, max(0.0, scores[action["id"]]))
