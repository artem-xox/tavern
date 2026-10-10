"""Launch wiring: reads the environment, builds the concrete adapters and creates the default server."""

import logging
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from random import Random
from typing import Any

from fastapi import FastAPI

from tavern.adapters.claude import ClaudeError, ask_claude
from tavern.adapters.jev import (evaluate_actions, evaluate_actions_metered, evaluate_aims, evaluate_aims_metered, evaluate_answers, evaluate_answers_metered,
                                 evaluate_seats, evaluate_seats_metered)
from tavern.adapters.probes import probes
from tavern.adapters.tracing import (Scorer, Tracer, open_tracer, traced_intender, traced_question, traced_scores,
                                     traced_writer)
from tavern.mind.agents import Evaluator, EvaluatorError, Evaluators, choose_action, choose_answer
from tavern.adapters.voices import load_voices
from tavern.mind.haiku_turns import claude_writer
from tavern.mind.intentions import intention_writer
from tavern.mind.selection import read_switch
from tavern.mind.model_health import HealthBoard
from tavern.mind.questions import Ask, Question
from tavern.server.api import create_app
from tavern.server.runtime import Answerer, Chooser


def create_default_app() -> FastAPI:
    """Read launch configuration and create the local demo application.

    Returns:
        Server initialized from the repository's map, first-evening scenario, and
        environment variables; `ANTHROPIC_API_KEY` enables the card compiler and Haiku lines,
        and `TAVERN_TRACE=true` (`make run TRACE=true`) traces Jev and Claude calls to LangSmith.

    Raises:
        ValueError: Tracing is on without `LANGSMITH_API_KEY`.
    """
    working_root = Path.cwd()
    root = (working_root if (working_root / "data" / "tavern.json").is_file()
            else Path(__file__).resolve().parents[2])
    config = {"typesafe_api_key": os.environ.get("TYPESAFE_API_KEY"),
              "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
              "timeout": float(os.environ.get("AI_TIMEOUT", "8")),
              "temperature": float(os.environ.get("AI_TEMPERATURE", "0.25")),
              "lean": read_switch(os.environ.get("AI_LEAN"), True, "AI_LEAN"),
              "aims": read_switch(os.environ.get("AI_AIMS"), True, "AI_AIMS"),
              "projects": read_switch(os.environ.get("AI_PROJECTS"), True, "AI_PROJECTS"),
              "answers": read_switch(os.environ.get("AI_ANSWERS"), False, "AI_ANSWERS")}
    board = HealthBoard({"jev": bool(config["typesafe_api_key"]), "claude": bool(os.environ.get("ANTHROPIC_API_KEY"))},
                        log=logging.getLogger("tavern.health").warning)
    # Traces spend LangSmith quota, so only an explicit switch turns them on; one server run is one evening.
    tracer = (open_tracer(os.environ, f"live {datetime.now():%Y-%m-%d %H:%M:%S}")
              if os.environ.get("TAVERN_TRACE") == "true" else None)
    ask = _claude_port(os.environ.get("ANTHROPIC_API_KEY"), board, tracer)
    database_url = (os.environ.get("DATABASE_URL")
                     if os.environ.get("TAVERN_DATABASE_ENABLED") == "true" else None)
    # With a Claude key Haiku writes conversation lines; without one the labeled scripted writer does.
    lines: dict[str, Any] = {}
    intender = None
    if ask is not None:
        writer, intender = claude_writer(ask, load_voices(root / "data" / "voices")), intention_writer(
            (root / "data" / "minds" / "intention_prefix.md").read_text(), ask)
        if tracer is not None:
            writer, intender = traced_writer(writer, tracer), traced_intender(intender, tracer)
        lines = {"writer": writer, "writer_label": "haiku"}
    choosers = _jev_choosers(board, tracer)
    return create_app(root / "data" / "tavern.json", root / "saves", config,
                      database_url=database_url, seed=Random().randrange(1 << 30),
                      scenario_path=root / "data" / "scenarios" / "first_evening.json",
                      characters_dir=root / "data" / "characters", staff_dir=root / "data" / "staff",
                      ask=ask, intender=intender,
                      choose=choosers[0], answer=choosers[1], health=board, probes=probes(config, os.environ.get("ANTHROPIC_API_KEY")),
                      **lines)


def _claude_port(key: str | None, board: HealthBoard, tracer: Tracer | None) -> Ask | None:
    # The key stays on the server; without one the card compiler runs offline.
    if not key:
        return None
    model = "claude-haiku-5-5"
    config = {"anthropic_api_key": key, "model": model, "timeout": 30.0, "retries": 1}

    async def metered(question: Question) -> tuple[dict[str, Any], Mapping[str, Any]]:
        return await ask_claude(question, config)
    asked = metered if tracer is None else traced_question(metered, model, tracer)

    async def ask(question: Question) -> dict[str, Any]:
        try:
            answer = (await asked(question))[0]
        except ClaudeError as error:
            board.record("claude", error)
            raise
        board.record("claude", None)
        return answer
    return ask


def _jev_choosers(board: HealthBoard, tracer: Tracer | None) -> tuple[Chooser, Answerer]:
    # Jev's evaluators, each call noted on the board (and traced, when tracing is on); a failure
    # still falls back to the local policy.
    def scorer(stage: str, plain: Evaluator, metered: Scorer) -> Evaluator:
        if tracer is None:
            return plain
        traced = traced_scores(stage, metered, tracer)

        async def scores(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                         config: Mapping[str, Any]) -> dict[str, float]:
            return (await traced(view, candidates, config))[0]
        return scores

    def watched(evaluate: Evaluator) -> Evaluator:
        async def noted(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                        config: Mapping[str, Any]) -> dict[str, float]:
            try:
                scores = await evaluate(view, candidates, config)
            except EvaluatorError as error:
                board.record("jev", error)
                raise
            board.record("jev", None)
            return scores
        return noted

    # The actions within a family are ordinary actions, scored as the first stage is.
    evaluators = Evaluators(watched(scorer("actions", evaluate_actions, evaluate_actions_metered)),
                            watched(scorer("seats", evaluate_seats, evaluate_seats_metered)),
                            watched(scorer("family", evaluate_actions, evaluate_actions_metered)),
                            watched(scorer("aims", evaluate_aims, evaluate_aims_metered)),
                            watched(scorer("answers", evaluate_answers, evaluate_answers_metered)))

    async def choose(observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
        return await choose_action(observation, config, rng, evaluators)

    async def answer(observation: Mapping[str, Any], invitation: Mapping[str, Any], options: Sequence[str],
                     config: Mapping[str, Any], rng: Random) -> dict[str, Any]:
        return await choose_answer(observation, invitation, options, config, rng, evaluators)
    return choose, answer
