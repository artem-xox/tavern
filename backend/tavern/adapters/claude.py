"""Structured-output calls to Claude at a strict, secret-safe boundary."""

from collections.abc import Mapping
import json
import math
from typing import Any, TypedDict

import anthropic
import httpx2

from tavern.evening.recording import Tariff
from tavern.mind.questions import Question

# Claude Haiku 4.5, USD per million tokens: input, output, cache reads, 5-minute cache writes.
HAIKU_4_5 = Tariff(input=1.0, output=5.0, cache_read=0.10, cache_write=1.25)
# The API allows at most four cache breakpoints per request; every system block takes one.
_MAX_BREAKPOINTS = 4


class ClaudeError(RuntimeError):
    """A recoverable model or transport failure, safe to display."""


class ClaudeUsage(TypedDict):
    """Token counts Claude reported for one request."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


def _configuration(config: Mapping[str, Any]) -> tuple[str, str, float, int]:
    key, model, timeout, retries = (config.get(name) for name in ("anthropic_api_key", "model", "timeout", "retries"))
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Claude requires an API key")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Claude requires a model name")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout < math.inf:
        raise ValueError("Claude timeout must be a positive finite number of seconds")
    if type(retries) is not int or retries < 0:
        raise ValueError("Claude retries must be a nonnegative integer")
    return key, model, float(timeout), retries


def _check_question(question: Question) -> None:
    system = question.get("system")
    if not isinstance(system, list) or not 1 <= len(system) <= _MAX_BREAKPOINTS or any(
            not isinstance(block, str) or not block.strip() for block in system):
        raise ValueError(f"A question's system prefix is 1 to {_MAX_BREAKPOINTS} nonempty text blocks")
    if not isinstance(question.get("content"), str) or not question["content"].strip():
        raise ValueError("A question needs nonempty content")
    if not isinstance(question.get("schema"), dict) or question["schema"].get("type") != "object":
        raise ValueError("A question's schema must describe a JSON object")
    if type(question.get("max_tokens")) is not int or question["max_tokens"] < 1:
        raise ValueError("A question's max_tokens must be a positive integer")


def _request(question: Question, model: str) -> dict[str, Any]:
    # A breakpoint closes every system block, so each prefix level is cached on its own; the
    # per-call content comes after them. Haiku 4.5 takes no adaptive thinking, so none is asked.
    system = [{"type": "text", "text": block, "cache_control": {"type": "ephemeral"}} for block in question["system"]]
    return {"model": model, "max_tokens": question["max_tokens"], "system": system,
            "messages": [{"role": "user", "content": question["content"]}],
            "output_config": {"format": {"type": "json_schema", "schema": question["schema"]}}}


async def _send(client: anthropic.AsyncAnthropic, request: Mapping[str, Any]) -> Any:
    try:
        return await client.messages.create(**request)
    except anthropic.APITimeoutError as error:
        raise ClaudeError("Claude request timed out") from error
    except anthropic.APIStatusError as error:
        raise ClaudeError(f"Claude HTTP {error.status_code}") from error
    except anthropic.APIConnectionError as error:
        raise ClaudeError("Claude connection failed") from error


def _answer(message: Any) -> dict[str, Any]:
    if message.stop_reason != "end_turn":
        raise ClaudeError(f"Claude stopped early: {message.stop_reason}")
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        raise ClaudeError("Claude returned no text")
    try:
        answer = json.loads(text)
    except ValueError as error:
        raise ClaudeError("Claude returned invalid JSON") from error
    if not isinstance(answer, dict):
        raise ClaudeError("Claude must answer with a JSON object")
    return answer


def _usage(message: Any) -> ClaudeUsage:
    # Cache counters the API leaves out mean nothing was read from or written to the cache.
    usage = message.usage
    return {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0}


async def ask_claude(question: Question, config: Mapping[str, Any],
                     client: httpx2.AsyncClient | None = None) -> tuple[dict[str, Any], ClaudeUsage]:
    """Ask Claude a structured question and report the tokens it took.

    Args:
        question: Cached system prefix, per-call content, answer schema and token bound.
        config: Explicit `anthropic_api_key`, `model`, `timeout` in seconds and SDK `retries`.
        client: Optional injected HTTP client, for boundary verification; it stays open.

    Returns:
        The answer as a decoded JSON object (its meaning is the caller's to validate), and the
        reported usage with cache reads and writes.

    Raises:
        ValueError: The question or configuration is malformed.
        ClaudeError: Transport, HTTP, refusal, truncation or JSON decoding fails.
    """
    _check_question(question)
    key, model, timeout, retries = _configuration(config)
    claude = anthropic.AsyncAnthropic(api_key=key, timeout=timeout, max_retries=retries, http_client=client)
    try:
        message = await _send(claude, _request(question, model))
    finally:
        if client is None:
            await claude.close()
    return _answer(message), _usage(message)
