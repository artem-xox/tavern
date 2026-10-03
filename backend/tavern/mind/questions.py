"""A structured question for the mind-layer model: the request shape and the port that answers it."""

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict


class Question(TypedDict):
    """One structured-output request, laid out for prompt caching.

    `system` is the stable prefix: one to four text blocks, each closed by a cache breakpoint, so
    the most widely shared block goes first (world notes, rules, examples) and narrower ones
    after it (a speaker's card). A prefix shorter than the model's minimum cacheable length
    (4096 tokens on Haiku 4.5) is silently not cached. `content` is what changes per call, after
    the cached prefix. `schema` is the JSON schema the answer object must follow, and
    `max_tokens` bounds the answer.
    """

    system: list[str]
    content: str
    schema: dict[str, Any]
    max_tokens: int


# The core receives this port: a question in, the decoded answer object out. Adapters raise
# their recoverable error (`claude.ClaudeError`) for transport, refusal or JSON failures; the
# consumer validates the answer's meaning itself.
Ask = Callable[[Question], Awaitable[dict[str, Any]]]
