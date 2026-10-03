"""Launch wiring: reads the environment, builds the concrete adapters and creates the default server."""

import os
from pathlib import Path
from random import Random
from typing import Any

from fastapi import FastAPI

from tavern.adapters.claude import ask_claude
from tavern.mind.haiku_turns import claude_writer
from tavern.mind.intentions import intention_writer
from tavern.mind.questions import Ask, Question
from tavern.server.api import create_app


def create_default_app() -> FastAPI:
    """Read launch configuration and create the local demo application.

    Returns:
        Server initialized from the repository's map, first-evening scenario, and
        environment variables; `ANTHROPIC_API_KEY` enables the card compiler and Haiku lines.
    """
    working_root = Path.cwd()
    root = (working_root if (working_root / "data" / "tavern.json").is_file()
            else Path(__file__).resolve().parents[2])
    config = {"typesafe_api_key": os.environ.get("TYPESAFE_API_KEY"),
              "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(os.environ.get("AI_TIMEOUT", "8")),
              "temperature": float(os.environ.get("AI_TEMPERATURE", "0.25"))}
    ask = _claude_port(os.environ.get("ANTHROPIC_API_KEY"))
    database_url = (os.environ.get("DATABASE_URL")
                     if os.environ.get("TAVERN_DATABASE_ENABLED") == "true" else None)
    ask = _claude_port(os.environ.get("ANTHROPIC_API_KEY"))
    # With a Claude key Haiku writes conversation lines; without one the labeled scripted writer does.
    lines: dict[str, Any] = {} if ask is None else {"writer": claude_writer(ask), "writer_label": "haiku"}
    return create_app(root / "data" / "tavern.json", root / "saves", config,
                      database_url=database_url, seed=Random().randrange(1 << 30),
                      scenario_path=root / "data" / "scenarios" / "first_evening.json",
                      characters_dir=root / "data" / "characters",
                      ask=ask, intender=None if ask is None else intention_writer(
                          (root / "data" / "minds" / "intention_prefix.md").read_text(), ask), **lines)


def _claude_port(key: str | None) -> Ask | None:
    # The key stays on the server; without one the card compiler runs offline.
    if not key:
        return None
    config = {"anthropic_api_key": key, "model": "claude-haiku-4-5", "timeout": 30.0, "retries": 1}

    async def ask(question: Question) -> dict[str, Any]:
        return (await ask_claude(question, config))[0]
    return ask
