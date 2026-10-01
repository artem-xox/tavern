"""Asynchronous TypeSafe Score evaluation at a strict, secret-safe boundary."""

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx


class JevError(RuntimeError):
    """A recoverable model or transport failure, safe to display in snapshots."""


def _candidate_ids(candidates: Sequence[Mapping[str, Any]]) -> list[str]:
    if any(not isinstance(action, Mapping) for action in candidates):
        raise ValueError("Candidates must be action mappings")
    ids = [action.get("id") for action in candidates]
    if not ids or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("Candidates must have nonempty string IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("Candidate IDs must be unique")
    if any(not isinstance(action.get("verb"), str) or not action["verb"] or "target_id" not in action for action in candidates):
        raise ValueError("Candidates must contain verb and target_id")
    if any(action["target_id"] is not None and (not isinstance(action["target_id"], str) or not action["target_id"]) for action in candidates):
        raise ValueError("Action target must be an object ID or null")
    return ids


def _visitor_view() -> str:
    return (
        "`state.observation.situation` describes one guest of a small border tavern in plain words, from their "
        "own point of view: how long they have been here, where they are, what they hold, their needs and "
        "temperament, who is in sight and what those people are doing, the places and tables they know, and "
        "what happened to them recently. `state.observation.options` describes each thing they could do next "
        "(`state.actions` lists the same options as data). `state.observation.self` holds the exact numbers: "
        "needs run from 0 (satisfied) to 100 (urgent), traits from 0 to 1, and `self.visit` counts the seconds "
        "spent in the inn, the beers drunk and the grievances held tonight. Judge like someone who knows how "
        "real tavern guests behave: they settle at a table with their drink, sip it there and chat with whoever "
        "sits with them, and they get up only for a reason - a refill, the WC, a game, a look at the fire - "
        "before going home once the evening has given them what they came for, or has gone sour. Restless "
        "wandering without a reason is unnatural, and so is ignoring a pressing need."
    )


def _activity(action: Mapping[str, Any]) -> tuple[str, str]:
    target = action["target_id"]
    activities = {
        "take_beer": (f"walk to the tap {target!r} and pour a mug of ale to carry",
                      "Thirsty guests and newcomers naturally fetch a drink. It is pointless while they already "
                      "hold a mug, or when the tap has run dry."),
        "drink": ("drink the mug of ale they are holding",
                  "Sipping ale at the table is the heart of a tavern evening; it quenches thirst but fills the "
                  "bladder."),
        "rest": (f"rest on the chair {target!r}", "It eases tiredness."),
        "seating": ("find a seat: choose a free chair at one of the tables and sit down",
                    "A separate decision picks the chair, which becomes their own seat for the rest of the "
                    "visit. Visitors who have just come in usually want to sit down and have a beer first. "
                    "If they already have a seat of their own, this means moving to another table, which "
                    "is worth it mainly to join company when they feel lonely."),
        "sit": (f"sit in their own seat {target!r} for a while",
                "Sitting in their own seat is a guest's natural resting state: it eases tiredness, it is where "
                "they sip their ale, and it lets them chat with whoever shares the table. Getting up needs a "
                "reason."),
        "talk": (f"chat with {target!r}, who sits at their table",
                 "It eases the wish for company of both and lets them share where the beer, WC and darts are. "
                 "After a few beers an impatient pair may quarrel instead, leaving both aggrieved; someone who "
                 "wronged them tonight is poor company. Right after a chat, with their wish for company "
                 "satisfied, a quiet sip or a rest is more natural than yet another chat."),
        "play_darts": (f"play a round of darts at {target!r}",
                       "A lively pastime for a bored guest; it means leaving their seat for a while."),
        "watch": (f"stand by {target!r} and watch it for a while",
                  "Gazing into the flames of the fireplace or out of a window at the road is a quiet pleasure "
                  "that eases boredom more gently than darts. Comfort-loving guests especially enjoy the warmth "
                  "of the fire, curious ones the view outside. It means leaving their seat for a while."),
        "use_toilet": (f"use the WC {target!r}", "Necessary once the bladder presses, pointless before."),
        "inspect": ("explore the room to discover or re-check places",
                    "Worthwhile only when something they need has not been found yet; otherwise it is aimless "
                    "wandering."),
        "wait": ("wait a moment and do nothing", "Idling where they stand is rarely the most natural thing."),
        "leave": (f"leave the inn for the night through {target!r}, ending their visit for good",
                  "Going home is the natural end of an evening, not a failure. It is the right move when they "
                  "are content: they have stayed a good while (several minutes of `self.visit.seconds`), drunk "
                  "their fill (two or three beers in `self.visit.beers`) and their needs are mostly low, or when "
                  "their company has gone home and the evening has run its course; after a long evening and "
                  "several beers, a guest left alone in the inn naturally heads home. It is also right when the "
                  "evening has gone wrong: the beer has run out (the tap shows stock 0 when last seen) while they "
                  "are still thirsty, someone took their seat, someone offended them or they had a quarrel (see "
                  "`self.visit.grievances`), or their needs keep going unmet. Leaving is a poor choice when they "
                  "have just arrived, still hold an undrunk mug, want a drink that is still available, or are "
                  "enjoying good company. Impatient guests walk out sooner after a grievance; comfort-loving "
                  "guests linger in a cosy seat."),
    }
    if action["verb"] not in activities:
        raise ValueError(f"Jev cannot describe the action verb {action['verb']!r}")
    return activities[action["verb"]]


def _guest(observation: Mapping[str, Any]) -> str:
    return (observation.get("self") or observation.get("actor") or {}).get("name") or "this guest"


def _briefed(observation: Mapping[str, Any], action: Mapping[str, Any], fallback: str) -> str:
    # A briefing from the agent describes the option concretely; bare observations get the generic wording.
    return (observation.get("options") or {}).get(action["id"], fallback)


def _action_question(action: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    rubric = ["Makes no sense for them now", "Unlikely, though possible", "A reasonable choice",
              "A very natural choice", "Exactly what they would do now"]
    what, guidance = _activity(action)
    return {"type": "score", "criteria": rubric, "instructions": (
        f"{_visitor_view()} How natural and worthwhile is it for {_guest(observation)}, right now, to "
        f"{_briefed(observation, action, what)}? {guidance}")}


def _seat_question(action: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    if action["verb"] != "sit":
        raise ValueError("Seat questions only judge chairs to sit on")
    rubric = ["A poor seat for them", "Below average", "Acceptable", "A good seat", "The ideal seat for them tonight"]
    chair = _briefed(observation, action, f"take the chair {action['target_id']!r}")
    return {"type": "score", "criteria": rubric, "instructions": (
        f"{_visitor_view()} {_guest(observation)} has decided to sit down and is choosing a chair; the one they "
        f"pick becomes their own seat for the rest of the visit. How good a choice is it to {chair}? Weigh the "
        "table's appeal (0 to 1) and its comforts: a window gives light and a view, the fireplace warmth and "
        "cosiness, while a plain table in a corner has neither. Guests with a high comfort trait care most about "
        "appeal. Company matters too: people already sitting at that table are welcome when the guest wishes for "
        "company, while a quiet table suits someone who would rather be left alone, or who was wronged by those "
        "people tonight. A long walk matters more when they are tired. If this chair is already their own seat, "
        "staying is natural unless company elsewhere draws them.")}


def _request_body(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], model: str,
    question: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    return {"model": model, "state": {"observation": dict(observation), "actions": list(candidates)},
            "questions": {action["id"]: question(action, observation) for action in candidates}}


def _read_scores(payload: Any, ids: Sequence[str]) -> dict[str, float]:
    answers = payload.get("answers") if isinstance(payload, Mapping) else None
    if not isinstance(answers, Mapping) or set(answers) != set(ids):
        raise JevError("Jev response must score exactly the supplied actions")
    scores = {}
    for action_id in ids:
        answer = answers[action_id]
        score = answer.get("score") if isinstance(answer, Mapping) else None
        if not isinstance(answer, Mapping) or answer.get("type") != "score":
            raise JevError("Jev returned an invalid answer type")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise JevError("Jev returned an invalid numeric score")
        if not 0 <= score <= 4:
            raise JevError("Jev returned a score outside the shared rubric")
        scores[action_id] = float(score) / 4
    return scores


async def _post_scores(
    client: httpx.AsyncClient, body: Mapping[str, Any], key: str, timeout: float
) -> Any:
    try:
        response = await client.post(
            "https://api.typesafe.ai/v1/systemone", json=body,
            headers={"Authorization": f"Bearer {key}"}, timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as error:
        raise JevError("Jev request timed out") from error
    except httpx.HTTPStatusError as error:
        raise JevError(f"Jev HTTP {error.response.status_code}") from error
    except httpx.RequestError as error:
        raise JevError("Jev connection failed") from error
    except ValueError as error:
        raise JevError("Jev returned invalid JSON") from error


def _configuration(config: Mapping[str, Any]) -> tuple[str, str, float]:
    key, model, timeout = config.get("typesafe_api_key"), config.get("model"), config.get("timeout")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Jev requires an API key")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Jev requires a model name")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Jev timeout must be a positive finite number")
    return key, model, float(timeout)


async def evaluate_actions(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any], client: httpx.AsyncClient | None = None,
) -> dict[str, float]:
    """Score supplied actions using only the NPC's personal observation.

    Args:
        observation: Private agent view, never an authoritative world snapshot.
        candidates: Unique legal candidate actions to evaluate.
        config: Explicit API key, model name and timeout in seconds.
        client: Optional injected HTTP client for boundary verification.

    Returns:
        Scores normalized from the shared five-level rubric to 0–1.

    Raises:
        ValueError: Candidates, their verbs or configuration are malformed.
        JevError: Transport, HTTP, JSON or typed-score validation fails.
    """
    return await _evaluate(observation, candidates, config, client, _action_question)


async def evaluate_seats(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any], client: httpx.AsyncClient | None = None,
) -> dict[str, float]:
    """Score the chairs a visitor who decided to sit down could take.

    Args:
        observation: Private agent view, never an authoritative world snapshot.
        candidates: Unique `sit` actions, one per free table chair.
        config: Explicit API key, model name and timeout in seconds.
        client: Optional injected HTTP client for boundary verification.

    Returns:
        Scores normalized from the five-level seat rubric to 0–1.

    Raises:
        ValueError: Candidates are not `sit` actions or configuration is malformed.
        JevError: Transport, HTTP, JSON or typed-score validation fails.
    """
    return await _evaluate(observation, candidates, config, client, _seat_question)


async def _evaluate(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], config: Mapping[str, Any],
    client: httpx.AsyncClient | None, question: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> dict[str, float]:
    ids = _candidate_ids(candidates)
    key, model, timeout = _configuration(config)
    body = _request_body(observation, candidates, model, question)
    if client is None:
        async with httpx.AsyncClient() as owned_client:
            payload = await _post_scores(owned_client, body, key, timeout)
    else:
        payload = await _post_scores(client, body, key, timeout)
    return _read_scores(payload, ids)
