"""The Claude boundary: cache-ready requests, strict JSON answers, usage, and recoverable errors."""

import asyncio
from collections.abc import Callable
import json
from typing import Any

import httpx2
import pytest

from tavern.adapters.claude import ClaudeError, ask_claude
from tavern.mind.questions import Question

SCHEMA = {"type": "object", "properties": {"mood": {"type": "string"}}, "required": ["mood"],
          "additionalProperties": False}


def question(**fields: Any) -> Question:
    """A question with a two-block cached prefix."""
    return Question(**{"system": ["World notes.", "Ada's card."], "content": "How is Ada?", "schema": SCHEMA,
                       "max_tokens": 200, **fields})


def config(**fields: Any) -> dict[str, Any]:
    """Claude settings with a test key."""
    return {"anthropic_api_key": "test-secret", "model": "claude-haiku-4-5", "timeout": 5.0, "retries": 0,
            **fields}


def message(text: str = '{"mood": "calm"}', stop_reason: str = "end_turn", **usage: Any) -> dict[str, Any]:
    """A Messages API response body with one text block."""
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-4-5",
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 7, "cache_read_input_tokens": 4100,
                      "cache_creation_input_tokens": 0, **usage}}


def ask(respond: Callable[[httpx2.Request], httpx2.Response], asked: Question | None = None,
        settings: dict[str, Any] | None = None) -> Any:
    """Ask through a mock transport; return the answer and usage."""
    async def run() -> Any:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
            return await ask_claude(asked or question(), settings or config(), client)
    return asyncio.run(run())


def reply(body: Any, status: int = 200) -> Callable[[httpx2.Request], httpx2.Response]:
    """Answer every request with the same JSON body."""
    return lambda request: httpx2.Response(status, json=body)


def test_answer_and_usage_come_back() -> None:
    assert ask(reply(message())) == ({"mood": "calm"}, {"input_tokens": 12, "output_tokens": 7,
                                                        "cache_read_input_tokens": 4100,
                                                        "cache_creation_input_tokens": 0})


def test_unreported_cache_counters_read_as_no_caching() -> None:
    body = message(cache_read_input_tokens=None, cache_creation_input_tokens=None)
    assert ask(reply(body))[1] == {"input_tokens": 12, "output_tokens": 7, "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}


def test_request_caches_each_system_block_and_asks_for_the_schema() -> None:
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json=message())
    ask(respond)
    body = json.loads(sent[0].content)
    assert (sent[0].url.path, sent[0].headers["x-api-key"]) == ("/v1/messages", "test-secret")
    assert body["system"] == [{"type": "text", "text": "World notes.", "cache_control": {"type": "ephemeral"}},
                              {"type": "text", "text": "Ada's card.", "cache_control": {"type": "ephemeral"}}]
    assert (body["model"], body["max_tokens"], body["messages"], "thinking" in body) == (
        "claude-haiku-4-5", 200, [{"role": "user", "content": "How is Ada?"}], False)
    assert body["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}


@pytest.mark.parametrize("respond, error", [
    pytest.param(reply({"type": "error", "error": {"type": "api_error", "message": "boom"}}, 500), "HTTP 500",
                 id="server-error"),
    pytest.param(reply({"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}, 429),
                 "HTTP 429", id="rate-limited"),
    pytest.param(reply(message("not json")), "invalid JSON", id="malformed-json"),
    pytest.param(reply(message("[1, 2]")), "JSON object", id="json-array"),
    pytest.param(reply(message("")), "invalid JSON", id="empty-text"),
    pytest.param(reply({**message(), "content": []}), "no text", id="no-text-block"),
    pytest.param(reply(message(stop_reason="refusal")), "refusal", id="refused"),
    pytest.param(reply(message('{"mood": "ca', stop_reason="max_tokens")), "max_tokens", id="cut-off"),
    pytest.param(lambda request: (_ for _ in ()).throw(httpx2.ReadTimeout("slow", request=request)),
                 "timed out", id="timeout"),
    pytest.param(lambda request: (_ for _ in ()).throw(httpx2.ConnectError("down", request=request)),
                 "connection", id="connection-failed"),
])
def test_failures_are_recoverable_and_keep_the_key_secret(
        respond: Callable[[httpx2.Request], httpx2.Response], error: str) -> None:
    with pytest.raises(ClaudeError, match=error) as raised:
        ask(respond)
    assert "test-secret" not in str(raised.value)


@pytest.mark.parametrize("asked, settings", [
    pytest.param(question(system=[]), config(), id="empty-prefix"),
    pytest.param(question(system=["a", "b", "c", "d", "e"]), config(), id="more-breakpoints-than-allowed"),
    pytest.param(question(system=["World notes.", ""]), config(), id="blank-prefix-block"),
    pytest.param(question(content=""), config(), id="empty-content"),
    pytest.param(question(schema=[]), config(), id="malformed-schema"),
    pytest.param(question(max_tokens=0), config(), id="no-tokens"),
    pytest.param(question(), config(anthropic_api_key=""), id="missing-key"),
    pytest.param(question(), config(model=None), id="missing-model"),
    pytest.param(question(), config(timeout=-1), id="negative-timeout"),
    pytest.param(question(), config(retries=True), id="malformed-retries"),
])
def test_malformed_question_or_config_fails_before_any_call(asked: Question, settings: dict[str, Any]) -> None:
    def never(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request may be sent")
    with pytest.raises(ValueError):
        ask(never, asked, settings)


@pytest.mark.parametrize("status, body, expected", [
    pytest.param(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}, 401,
                 id="key-refused"),
    pytest.param(400, {"type": "error", "error": {"type": "invalid_request_error",
                                                  "message": "Your credit balance is too low to access the API."}},
                 402, id="credit-balance-too-low"),
    pytest.param(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "bad field"}}, 400,
                 id="other-bad-request"),
])
def test_failures_carry_a_status_and_a_missing_credit_reads_as_payment_required(
        status: int, body: dict[str, Any], expected: int) -> None:
    with pytest.raises(ClaudeError) as raised:
        ask(reply(body, status))
    assert raised.value.status == expected
