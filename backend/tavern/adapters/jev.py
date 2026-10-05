"""Asynchronous TypeSafe Score evaluation at a strict, secret-safe boundary."""

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypedDict, cast

import httpx

from tavern.body.activities import ACTIVITIES, FAMILIES
from tavern.body.items import ITEMS
from tavern.mind.agents import EvaluatorError


class JevError(EvaluatorError):
    """A recoverable model or transport failure, safe to display in snapshots."""


class Usage(TypedDict):
    """Token counts the provider reported for one request; Jev bills input tokens only."""

    input_tokens: int
    output_tokens: int


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
    return cast(list[str], ids)


def _visitor_view() -> str:
    return (
        "`state.observation.situation` describes one guest of a small border tavern in plain words, from their "
        "own point of view: how long they have been here, where they are, what they hold, their needs and "
        "temperament, their mood and what they think of the people they know, who is in sight and what those "
        "people are doing, the places and tables they know, and what happened to them recently. "
        "`state.observation.options` describes each thing they could do next "
        "(`state.actions` lists the same options as data). `state.observation.self` holds the exact numbers: "
        "needs run from 0 (satisfied) to 100 (urgent), traits from 0 to 1, and `self.visit` counts the seconds "
        "spent in the inn, the beers drunk and the wrongs that still rankle tonight. Judge like someone who knows how "
        "real tavern guests behave: they settle at a table with their drink, sip it there and chat with whoever "
        "sits with them, and they get up only for a reason - a refill, the WC, a game, a look at the fire - "
        "before going home once the evening has given them what they came for, or has gone sour. Restless "
        "wandering without a reason is unnatural, and so is ignoring a pressing need. When the situation states "
        "their intention, weigh each option against their intention: what serves it is natural, what goes against "
        "it needs a reason, but an urgent need or something that just happened still comes first. An option "
        "marked as serving their goal moves them toward what they set out to do tonight; prefer it unless a need "
        "presses or something just happened."
    )


def _activity(action: Mapping[str, Any]) -> tuple[str, str]:
    if action["verb"] in FAMILIES:
        return _family(action)
    activity = ACTIVITIES.get(action["verb"])
    if activity is None:
        raise ValueError(f"Jev cannot describe the action verb {action['verb']!r}")
    item = action.get("item")
    if not activity.names_item:
        words = ""
    elif isinstance(item, str) and item in ITEMS:
        words = ITEMS[item].one
    else:
        raise ValueError(f"Jev cannot describe the item {item!r} of action {action['id']!r}")
    return activity.what.format(target=repr(action["target_id"]), item=words), activity.guidance


def _family(option: Mapping[str, Any]) -> tuple[str, str]:
    # A family is judged as the wish its members share, with each member verb's guidance once.
    members = option.get("members")
    if not isinstance(members, list) or not members or any(
            not isinstance(item, Mapping) or item.get("verb") not in ACTIVITIES for item in members):
        raise ValueError(f"Family option {option['id']!r} must list its member actions")
    guidance = dict.fromkeys(ACTIVITIES[item["verb"]].guidance for item in members)
    return FAMILIES[option["verb"]], " ".join([*guidance, "A second decision then picks which of these they do."])


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
        raise JevError(f"Jev HTTP {error.response.status_code}", error.response.status_code) from error
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
    return (await _evaluate(observation, candidates, config, client, _action_question))[0]


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
    return (await _evaluate(observation, candidates, config, client, _seat_question))[0]


async def evaluate_actions_metered(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any], client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, float], Usage | None]:
    """Score supplied actions, as `evaluate_actions`, and report the request's token usage.

    Args:
        observation: Private agent view, never an authoritative world snapshot.
        candidates: Unique legal candidate actions to evaluate.
        config: Explicit API key, model name and timeout in seconds.
        client: Optional injected HTTP client for boundary verification.

    Returns:
        Normalized scores, and the provider-reported usage or None when it reported none.

    Raises:
        ValueError: Candidates, their verbs or configuration are malformed.
        JevError: Transport, HTTP, JSON, typed-score or usage validation fails.
    """
    scores, payload = await _evaluate(observation, candidates, config, client, _action_question)
    return scores, _read_usage(payload)


async def evaluate_seats_metered(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any], client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, float], Usage | None]:
    """Score free chairs, as `evaluate_seats`, and report the request's token usage.

    Args:
        observation: Private agent view, never an authoritative world snapshot.
        candidates: Unique `sit` actions, one per free table chair.
        config: Explicit API key, model name and timeout in seconds.
        client: Optional injected HTTP client for boundary verification.

    Returns:
        Normalized scores, and the provider-reported usage or None when it reported none.

    Raises:
        ValueError: Candidates are not `sit` actions or configuration is malformed.
        JevError: Transport, HTTP, JSON, typed-score or usage validation fails.
    """
    scores, payload = await _evaluate(observation, candidates, config, client, _seat_question)
    return scores, _read_usage(payload)


def _read_usage(payload: Mapping[str, Any]) -> Usage | None:
    # A response without usage is valid (the scores stand); reported counters must be sound.
    if "usage" not in payload:
        return None
    usage = payload["usage"]
    counts = [usage.get(name) for name in ("input_tokens", "output_tokens")] if isinstance(usage, Mapping) else []
    if len(counts) != 2 or any(isinstance(count, bool) or not isinstance(count, int) or count < 0
                               for count in counts):
        raise JevError("Jev returned malformed usage")
    return cast(Usage, {"input_tokens": counts[0], "output_tokens": counts[1]})


async def _evaluate(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], config: Mapping[str, Any],
    client: httpx.AsyncClient | None, question: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]],
) -> tuple[dict[str, float], Any]:
    ids = _candidate_ids(candidates)
    key, model, timeout = _configuration(config)
    body = _request_body(observation, candidates, model, question)
    if client is None:
        async with httpx.AsyncClient() as owned_client:
            payload = await _post_scores(owned_client, body, key, timeout)
    else:
        payload = await _post_scores(client, body, key, timeout)
    return _read_scores(payload, ids), payload
