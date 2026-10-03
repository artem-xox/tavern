"""The Jev boundary validates typed answers without exposing credentials."""

import asyncio
from collections.abc import Callable
import json
from typing import Any

import httpx
import pytest

from tavern.adapters.jev import JevError, evaluate_actions, evaluate_actions_metered, evaluate_seats_metered


def candidates():
    return [{"id": "wait", "verb": "wait", "target_id": None}]


def config(**fields):
    return {"typesafe_api_key": "test-secret", "model": "jev-latest",
            "timeout": 2.0, "temperature": 0.1, **fields}


def evaluate(response, actions=None, view=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
            return await evaluate_actions(view or {"actor": {"id": "own"}, "objects": []},
                                          candidates() if actions is None else actions, config(), client)
    return asyncio.run(run())


@pytest.mark.parametrize("score,expected", [
    pytest.param(0, 0.0, id="lowest-level"),
    pytest.param(2.5, 0.625, id="fractional-score"),
    pytest.param(4, 1.0, id="highest-level"),
])
def test_score_levels_are_normalized(score, expected):
    response = httpx.Response(200, json={"answers": {"wait": {"type": "score", "score": score}}})
    assert evaluate(response) == {"wait": expected}


@pytest.mark.parametrize("payload", [
    pytest.param({}, id="empty-response"),
    pytest.param({"answers": {}}, id="missing-single-score"),
    pytest.param({"answers": {"wait": {"type": "noul", "score": 1}}}, id="wrong-type"),
    pytest.param({"answers": {"wait": {"type": "score", "score": "2"}}}, id="malformed-number"),
    pytest.param({"answers": {"wait": {"type": "score", "score": True}}}, id="boolean-is-not-score"),
    pytest.param({"answers": {"wait": {"type": "score", "score": -1}}}, id="below-range"),
    pytest.param({"answers": {"wait": {"type": "score", "score": 5}}}, id="above-range"),
    pytest.param({"answers": {"wait": {"type": "score", "score": 1}, "invented": {"type": "score", "score": 4}}}, id="unsupplied-action"),
])
def test_invalid_jev_answers_are_rejected(payload):
    with pytest.raises(JevError):
        evaluate(httpx.Response(200, json=payload))


@pytest.mark.parametrize("raw", [
    pytest.param(b'{"answers":{"wait":{"type":"score","score":NaN}}}', id="nan"),
    pytest.param(b'{"answers":{"wait":{"type":"score","score":Infinity}}}', id="infinite"),
    pytest.param(b'not json', id="not-json"),
])
def test_invalid_json_or_nonfinite_numbers_are_rejected(raw):
    with pytest.raises(JevError):
        evaluate(httpx.Response(200, content=raw))


@pytest.mark.parametrize("actions", [
    pytest.param([], id="empty-candidate-list"),
    pytest.param(candidates() * 2, id="duplicate-candidate-id"),
    pytest.param([{"id": "wait"}], id="malformed-candidate"),
])
def test_invalid_candidates_fail_before_request(actions):
    with pytest.raises(ValueError):
        evaluate(httpx.Response(200, json={}), actions=actions)


def test_request_uses_official_api_and_private_observation():
    captured = []

    def handle(request):
        captured.append(request)
        return httpx.Response(200, json={"answers": {"wait": {"type": "score", "score": 1}}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await evaluate_actions({"actor": {"id": "own"}, "objects": []}, candidates(), config(), client)

    asyncio.run(run())
    request = captured[0]
    body = json.loads(request.content)
    assert (str(request.url), request.headers["authorization"], body["model"],
            body["state"]["observation"], len(body["questions"]["wait"]["criteria"])) == (
                "https://api.typesafe.ai/v1/systemone", "Bearer test-secret", "jev-latest",
                {"actor": {"id": "own"}, "objects": []}, 5)
    assert "test-secret" not in request.content.decode()


def test_timeout_is_explicit_and_secret_safe():
    def handle(request):
        raise httpx.ReadTimeout("sensitive test-secret detail", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await evaluate_actions({"actor": {}}, candidates(), config(), client)

    with pytest.raises(JevError, match="^Jev request timed out$"):
        asyncio.run(run())


@pytest.mark.parametrize("status", [
    pytest.param(401, id="unauthorized"),
    pytest.param(429, id="rate-limit"),
    pytest.param(500, id="server-error"),
])
def test_http_failure_is_explicit(status):
    with pytest.raises(JevError, match=f"Jev HTTP {status}"):
        evaluate(httpx.Response(status, text="sensitive response"))


@pytest.mark.parametrize("actions", [
    pytest.param([None], id="non-record-candidate"),
    pytest.param([{"id": "wait", "verb": "", "target_id": None}], id="empty-verb"),
    pytest.param([{"id": "rest:chair", "verb": "rest", "target_id": 42}], id="malformed-target"),
])
def test_malformed_action_shapes_are_rejected_before_request(actions):
    with pytest.raises(ValueError):
        evaluate(httpx.Response(200, json={}), actions=actions)


def metered(payload: Any, evaluator: Callable[..., Any] = evaluate_actions_metered,
            actions: list[dict[str, Any]] | None = None) -> Any:
    """Evaluate through a metered entry point against a canned provider payload."""
    async def run() -> Any:
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        async with httpx.AsyncClient(transport=transport) as client:
            return await evaluator({"actor": {"id": "own"}, "objects": []}, actions or candidates(), config(), client)
    return asyncio.run(run())


def answered(usage: Any = None, action_id: str = "wait") -> dict[str, Any]:
    """Build a valid provider payload, with usage counters when given."""
    return {"answers": {action_id: {"type": "score", "score": 4}}, **({} if usage is None else {"usage": usage})}


@pytest.mark.parametrize("usage, expected", [
    pytest.param(None, None, id="usage-not-reported"),
    pytest.param({"input_tokens": 0, "output_tokens": 0}, {"input_tokens": 0, "output_tokens": 0}, id="empty-counts"),
    pytest.param({"input_tokens": 4361, "output_tokens": 77}, {"input_tokens": 4361, "output_tokens": 77},
                 id="single-request"),
    pytest.param({"input_tokens": 9, "output_tokens": 1, "cached_tokens": 4}, {"input_tokens": 9, "output_tokens": 1},
                 id="other-counters-are-not-read"),
])
def test_metered_evaluation_reports_provider_usage(usage: Any, expected: Any) -> None:
    assert metered(answered(usage)) == ({"wait": 1.0}, expected)


def test_metered_seat_evaluation_reports_provider_usage() -> None:
    chair = [{"id": "sit:chair", "verb": "sit", "target_id": "chair"}]
    usage = {"input_tokens": 12, "output_tokens": 3}
    assert metered(answered(usage, "sit:chair"), evaluate_seats_metered, chair) == ({"sit:chair": 1.0}, usage)


@pytest.mark.parametrize("usage", [
    pytest.param([], id="malformed-usage"),
    pytest.param({"input_tokens": "12", "output_tokens": 1}, id="text-count"),
    pytest.param({"input_tokens": -1, "output_tokens": 1}, id="negative-count"),
    pytest.param({"input_tokens": True, "output_tokens": 1}, id="boolean-count"),
    pytest.param({"output_tokens": 1}, id="missing-input-count"),
])
def test_malformed_usage_is_rejected(usage: Any) -> None:
    with pytest.raises(JevError, match="usage"):
        metered(answered(usage))


def test_unmetered_evaluation_never_reads_usage() -> None:
    assert evaluate(httpx.Response(200, json=answered([]))) == {"wait": 1.0}
