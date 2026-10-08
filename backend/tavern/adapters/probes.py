"""The smallest requests that prove Jev and Claude can be used: a key, credit and a connection."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from tavern.adapters.claude import ask_claude
from tavern.adapters.jev import evaluate_actions
from tavern.mind.questions import Question


def probes(jev: Mapping[str, Any], claude_key: str | None) -> dict[str, Callable[[], Awaitable[object]]]:
    """Make the cheap calls that prove each service can be used.

    Args:
        jev: AI config with the Jev key, model and timeout.
        claude_key: Anthropic key, or None.

    Returns:
        Per service the smallest request it answers: Jev scores one action, Claude fills a one-field
        object. Claude's is a real request, because only one proves the account has credit; each costs
        a fraction of a cent. Each raises the adapter's recoverable error on failure.
    """
    async def ask_jev() -> object:
        wait = {"id": "wait", "verb": "wait", "target_id": None}
        return await evaluate_actions({"actor": {"id": "probe"}, "objects": []}, [wait], jev)

    async def ask_claude_once() -> object:
        question = Question(system=["Answer with a JSON object."], content='Reply with {"ok": true}.',
                            schema={"type": "object", "properties": {"ok": {"type": "boolean"}},
                                    "required": ["ok"], "additionalProperties": False}, max_tokens=20)
        config = {"anthropic_api_key": claude_key, "model": "claude-haiku-5-5", "timeout": 30.0, "retries": 0}
        return await ask_claude(question, config)
    return {"jev": ask_jev, "claude": ask_claude_once}
