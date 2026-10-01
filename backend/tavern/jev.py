"""Asynchronous TypeSafe Score evaluation at a strict, secret-safe boundary."""

import math
from collections.abc import Mapping, Sequence
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


def _request_body(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], model: str
) -> dict[str, Any]:
    rubric = ["No useful effect on a current need", "Slightly useful",
              "Moderately useful", "Very useful", "Immediately satisfies an urgent need"]
    questions = {
        action["id"]: {
            "type": "score", "criteria": rubric,
            "instructions": (
                f"How useful is performing {action['verb']} on target {action['target_id']!r} "
                "now for this visitor's own needs in `observation.actor.needs`? "
                "Consider only their observed objects, inventory, traits and personal memories. "
                "Needs range from 0 (satisfied) to 100 (urgent). Higher trait values mean "
                "greater patience, comfort preference or curiosity. Unknown resources are unknown."
                " Social is desire for company; boredom is desire for recreation. "
                "Sit stays at a table for 14 seconds and reduces fatigue; prefer seats near "
                "visible company. Talk takes 8 seconds with a seated neighbor at the same table "
                "and satisfies social need for both. Play_darts takes 10 seconds and reduces boredom. "
                "Drink consumes owned beer and reduces thirst; prefer drinking while seated. "
                "When physical needs are low, spending time seated or in conversation is useful. "
                "If a physical need is urgent but no known object can relieve it, inspect "
                "to discover that resource. Chatting can share known locations of beer, toilets "
                "and darts with a neighbor. Avoid exploring when the required places are already known."
            ),
        }
        for action in candidates
    }
    return {"model": model, "state": {"observation": dict(observation),
                                      "actions": list(candidates)}, "questions": questions}


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
        ValueError: Candidates or configuration are malformed.
        JevError: Transport, HTTP, JSON or typed-score validation fails.
    """
    ids = _candidate_ids(candidates)
    key, model, timeout = _configuration(config)
    body = _request_body(observation, candidates, model)
    if client is None:
        async with httpx.AsyncClient() as owned_client:
            payload = await _post_scores(owned_client, body, key, timeout)
    else:
        payload = await _post_scores(client, body, key, timeout)
    return _read_scores(payload, ids)
