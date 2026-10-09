"""Play one headless evening in lockstep; write its event log, model calls and metrics."""

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
from random import Random
import time
from typing import Any, Callable, Mapping

from dotenv import dotenv_values

from tavern.adapters import jev
from tavern.adapters.claude import HAIKU_4_5, ClaudeError, ask_claude
from tavern.adapters.probes import probes
from tavern.adapters.tracing import (Scorer, Tracer, open_tracer, traced_intender, traced_question, traced_scores,
                                     traced_writer)
from tavern.evening.aim_metrics import aim_counts
from tavern.evening.choice_metrics import choice_counts
from tavern.evening.lockstep import Pace, evening_mode, run_evening
from tavern.evening.metrics import (attention_counts, bar_metrics, conversation_counts, dice_metrics, evening_metrics,
                                    intention_counts, news_metrics, sleep_metrics, writer_stats)
from tavern.evening.giving_metrics import giving_counts
from tavern.evening.manner_metrics import manner_counts
from tavern.evening.goal_metrics import goal_counts, promise_counts
from tavern.evening.repetition import ALIKE, repetition_counts
from tavern.evening.response_metrics import response_counts
from tavern.evening.project_metrics import project_counts
from tavern.evening.recording import (Record, format_record, parse_records, record_calls, record_questions, replay_calls,
                              replay_questions)
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.staff import on_staff
from tavern.mind.agents import Evaluators
from tavern.mind.cards import parse_cards
from tavern.mind.haiku_turns import claude_writer, writer_mode
from tavern.mind.intentions import Intender, intention_writer
from tavern.mind.model_health import HealthBoard, banner, blocking
from tavern.mind.questions import Question
from tavern.mind.scripted import write_scripted_turn
from tavern.mind.selection import read_switch
from tavern.social.turns import TurnWriter

DECIDES = {"local": "the local policy (no model)", "live": "Jev, recorded", "replay": "Jev answers replayed"}
CLAUDE_MODEL = "claude-haiku-4-5"
TARIFFS = {"turn": HAIKU_4_5, "card": HAIKU_4_5, "intention": HAIKU_4_5}


def arguments(root: Path) -> argparse.ArgumentParser:
    """Describe the command line.

    Args:
        root: Repository directory, for default paths.
    Returns:
        Parser of the evening options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scenario", type=Path, default=root / "data" / "scenarios" / "first_evening.json",
                        help="who comes tonight, when, and when the inn closes")
    parser.add_argument("--characters", type=Path, default=root / "data" / "characters",
                        help="character cards the scenario casts its guests from")
    parser.add_argument("--staff", type=Path, default=root / "data" / "staff",
                        help="cards the scenario casts its staff from")
    parser.add_argument("--mode", choices=("local", "live", "replay"),
                        help="default: live when TYPESAFE_API_KEY is in the env file, else local")
    parser.add_argument("--out", type=Path, default=root / "runs" / "evening-0")
    parser.add_argument("--calls", type=Path, help="recorded calls.jsonl to replay (replay mode)")
    parser.add_argument("--writer", choices=("haiku", "scripted"),
                        help="who writes conversation lines; default: Haiku when ANTHROPIC_API_KEY is in the env "
                             "file (a replay: when the recording has turns), else scripted")
    parser.add_argument("--env-file", type=Path, default=root / ".env")
    parser.add_argument("--trace", action="store_true",
                        help="trace the live Jev and Haiku calls to LangSmith, one thread per character; "
                             "needs LANGSMITH_API_KEY in the env file and spends LangSmith quota")
    parser.add_argument("--step", type=float, default=0.1, help="game seconds per tick")
    parser.add_argument("--latency", type=float, default=1.0, help="virtual model latency, game seconds")
    parser.add_argument("--time-limit", type=float, default=1200.0, help="game seconds before the evening is cut off")
    parser.add_argument("--stuck-threshold", type=float, default=3.0, help="seconds a stall may last before it counts")
    parser.add_argument("--input-price", type=float, default=0.042,
                        help="Jev USD per million input tokens; verified 2026-10-01")
    return parser


def config(values: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Build the AI config the decisions read, from the env file.

    Args:
        values: Parsed env file.
        mode: Evening mode.
    Returns:
        Config with the key only in live mode.
    """
    # A replay answers from its recording: the placeholder key only switches decisions to the
    # model and is never sent anywhere.
    key = {"live": values.get("TYPESAFE_API_KEY"), "replay": "replay", "local": None}[mode]
    return {"typesafe_api_key": key, "model": values.get("TYPESAFE_MODEL", "jev-latest"),
            "timeout": float(values.get("AI_TIMEOUT", "8")), "temperature": float(values.get("AI_TEMPERATURE", "0.25")),
            "lean": read_switch(values.get("AI_LEAN"), True, "AI_LEAN"),
            "aims": read_switch(values.get("AI_AIMS"), True, "AI_AIMS"),
            "projects": read_switch(values.get("AI_PROJECTS"), True, "AI_PROJECTS")}


def keeper(calls: list[Record], log: Path) -> Callable[[Record], None]:
    """Start a recording: each call is kept in memory and appended to a JSON-lines file as it ends.

    Args:
        calls: Receives the evening's calls.
        log: File to write; emptied first.
    Returns:
        The record keeper.
    """
    log.write_text("")

    def keep(record: Record) -> None:
        calls.append(record)
        with log.open("a") as lines:
            lines.write(format_record(record))
    return keep


def evaluators(mode: str, recording: Path | None, calls: list[Record], keep: Callable[[Record], None],
               tracer: Tracer | None) -> Evaluators:
    """Wire the model port for a mode.

    Args:
        mode: Evening mode.
        recording: Calls to replay, in replay mode.
        calls: Receives the calls loaded for replay.
        keep: Receives each live call as soon as it ends.
        tracer: Traces each live call to LangSmith, or None.
    Returns:
        Evaluators for every decision stage; the actions within a chosen family are
        ordinary actions, so Jev scores them with the action question, recorded as `family`.
    """
    if mode == "replay":
        calls.extend(parse_records(recording.read_text()))
        return Evaluators(*(replay_calls(kind, calls, jev.JevError) for kind in ("actions", "seats", "family", "aims")))
    if mode == "local":
        # Without a key the decisions never ask a model; Jev only fills the port.
        return Evaluators(jev.evaluate_actions, jev.evaluate_seats, aims=jev.evaluate_aims)
    def scorer(stage: str, evaluate: Scorer) -> Scorer:
        return evaluate if tracer is None else traced_scores(stage, evaluate, tracer)
    return Evaluators(*(record_calls(stage, scorer(stage, evaluate), keep, time.monotonic, jev.JevError)
                        for stage, evaluate in (("actions", jev.evaluate_actions_metered),
                                                ("seats", jev.evaluate_seats_metered),
                                                ("family", jev.evaluate_actions_metered),
                                                ("aims", jev.evaluate_aims_metered))))


def turn_writer(writer: str, mode: str, calls: list[Record], keep: Callable[[Record], None],
                values: Mapping[str, Any], tracer: Tracer | None) -> TurnWriter:
    """Wire the conversation line writer.

    Args:
        writer: `haiku` or `scripted` (see `haiku_turns.writer_mode`).
        mode: Evening mode; a replay answers Haiku turns from `calls`.
        calls: The evening's calls, loaded for a replay.
        keep: Receives each live Haiku call as soon as it ends, recorded as `turn`.
        values: Parsed env file with ANTHROPIC_API_KEY.
        tracer: Traces each live line to LangSmith, or None.
    Returns:
        The writer port.
    """
    if writer == "scripted":
        return write_scripted_turn
    if mode == "replay":
        return claude_writer(replay_questions("turn", calls, ClaudeError))
    # One SDK retry at most, so slow calls show in the latency measure rather than hide in retries.
    config = {"anthropic_api_key": values["ANTHROPIC_API_KEY"], "model": CLAUDE_MODEL, "timeout": 30.0, "retries": 1}

    async def ask(question: Question) -> Any:
        return await ask_claude(question, config)
    if tracer is None:
        return claude_writer(record_questions("turn", ask, keep, time.monotonic, ClaudeError))
    asked = record_questions("turn", traced_question(ask, CLAUDE_MODEL, tracer), keep, time.monotonic, ClaudeError)
    return traced_writer(claude_writer(asked), tracer)


def mind(mode: str, values: Mapping[str, Any], prefix: str, calls: list[Record],
         log: Path, tracer: Tracer | None) -> tuple[Intender | None, str]:
    """Wire the mind port that writes guests' intentions, and say how it runs.

    Args:
        mode: Evening mode.
        values: Parsed env file; live intentions need `ANTHROPIC_API_KEY`.
        prefix: Shared system prefix of every intention question.
        calls: The evening's calls (loaded already in replay mode); live calls are added.
        log: JSON-lines file each live call is appended to.
        tracer: Traces each live intention to LangSmith, or None.
    Returns:
        The intender, or None offline, and a label for the metrics.
    """
    if mode == "replay":
        if not any(record["kind"] == "intention" for record in calls):
            return None, "offline: the recording holds no intentions"
        return intention_writer(prefix, replay_questions("intention", calls, ClaudeError)), "Claude answers replayed"
    if mode == "local" or not values.get("ANTHROPIC_API_KEY"):
        return None, f"offline: {'local mode' if mode == 'local' else 'no ANTHROPIC_API_KEY'}, so no intentions"
    claude = {"anthropic_api_key": values["ANTHROPIC_API_KEY"], "model": "claude-haiku-4-5", "timeout": 30.0,
              "retries": 1}

    async def metered(question: Question) -> tuple[dict[str, Any], Mapping[str, int]]:
        answer, usage = await ask_claude(question, claude)
        return answer, dict(usage)

    def keep(record: Record) -> None:
        calls.append(record)
        with log.open("a") as lines:
            lines.write(format_record(record))
    if tracer is None:
        asked = record_questions("intention", metered, keep, time.monotonic, ClaudeError)
        return intention_writer(prefix, asked), "Claude Haiku 4.5 (claude-haiku-4-5), recorded"
    asked = record_questions("intention", traced_question(metered, CLAUDE_MODEL, tracer), keep, time.monotonic,
                             ClaudeError)
    return traced_intender(intention_writer(prefix, asked), tracer), "Claude Haiku 4.5 (claude-haiku-4-5), recorded"


def rounded(value: Any) -> Any:
    """Round every float in a JSON-like value for display.

    Args:
        value: Metrics or one of their parts.
    Returns:
        The same structure with floats rounded to six decimals.
    """
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    return value


def announce_health(parser: argparse.ArgumentParser, mode: str, writer: str, settings: Mapping[str, Any],
                    values: Mapping[str, Any]) -> None:
    """Probe the services this run will ask, print how they are doing, and stop a run none could serve.

    Args:
        parser: Reports the stop as a usage error.
        mode: Evening mode; a replay asks nobody.
        writer: Who writes the lines (`haiku` asks Claude).
        settings: The AI config of the run.
        values: Parsed env file.
    """
    claude_key = values.get("ANTHROPIC_API_KEY")
    used = [name for name, wanted in (("jev", mode == "live"),
                                      ("claude", bool(claude_key) and (writer == "haiku" or mode == "live")))
            if wanted]
    if mode == "replay":
        return
    board = HealthBoard({"jev": bool(settings["typesafe_api_key"]), "claude": bool(claude_key)})
    calls = probes(settings, claude_key)

    async def ask_all() -> None:
        for name in used:
            await board.probe(name, calls[name])
    asyncio.run(ask_all())
    health = board.snapshot()
    print(banner(health, used))
    stopped = blocking(health, used)
    if stopped:
        parser.error("; ".join(f"{name.upper()} cannot be used ({health[name]['status']}"
                               f"{': ' + health[name]['reason'] if health[name]['reason'] else ''})"
                               for name in stopped))


def main(root: Path) -> None:
    """Read options and the env file, play the evening, and write its outputs.

    Args:
        root: Repository directory.
    """
    parser = arguments(root)
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    try:
        mode, note = evening_mode(args.mode, bool(values.get("TYPESAFE_API_KEY")))
        pace = Pace(args.step, args.latency, args.time_limit)
    except ValueError as error:
        parser.error(str(error))
    if mode == "replay" and args.calls is None:
        parser.error("replay mode needs --calls (make evening MODE=replay CALLS=...)")
    if mode == "replay" and args.trace:
        parser.error("a replay asks no model, so there is nothing to trace")
    tracer = None
    if args.trace:
        try:
            tracer = open_tracer(values, f"{args.out.name} {datetime.now():%Y-%m-%d %H:%M:%S}")
        except ValueError as error:
            parser.error(str(error))
    args.out.mkdir(parents=True, exist_ok=True)
    calls: list[Record] = []
    keep = calls.append if mode == "replay" else keeper(calls, args.out / "calls.jsonl")
    ports = evaluators(mode, args.calls, calls, keep, tracer)
    keyed = (any(record["kind"] == "turn" for record in calls) if mode == "replay"
             else bool(values.get("ANTHROPIC_API_KEY")))
    try:
        writer, writer_note = writer_mode(args.writer, keyed)
    except ValueError as error:
        parser.error(str(error))
    lines = turn_writer(writer, mode, calls, keep, values, tracer)
    room = json.loads((root / "data" / "tavern.json").read_text())
    try:
        cards = parse_cards([json.loads(path.read_text()) for path in sorted(args.characters.glob("*.json"))])
        staff_cards = parse_cards([json.loads(path.read_text()) for path in sorted(args.staff.glob("*.json"))])
        world = open_evening(room, parse_scenario(json.loads(args.scenario.read_text()), cards, staff_cards),
                             args.seed)
    except (OSError, ValueError) as error:
        parser.error(f"cannot open the evening: {error}")
    settings = config(values, mode)
    intender, minded = mind(mode, values, (root / "data" / "minds" / "intention_prefix.md").read_text(), calls,
                            args.out / "calls.jsonl", tracer)
    announce_health(parser, mode, writer, settings, values)
    started = time.monotonic()
    evening = asyncio.run(run_evening(world, settings, Random(args.seed), ports, pace, lines, intender=intender))
    wall = time.monotonic() - started
    if tracer is not None:
        # The client uploads in the background; what is still queued must leave before the process ends.
        tracer.client.flush()
    # A replay matches its recording only with the same seed, pace, temperature, lean, aims and projects settings, so they are shown.
    report = {"run": {"mode": mode, "decides": DECIDES[mode], "note": note, "seed": args.seed,
                      "model": settings["model"], "temperature": settings["temperature"],
                      "lean": settings["lean"], "aims": settings["aims"],
                      "projects": settings["projects"], "step": pace.step,
                      "model_latency": pace.model_latency, "time_limit": pace.time_limit,
                      "stuck_threshold": args.stuck_threshold, "input_usd_per_million": args.input_price,
                      "writer": writer, "writer_model": CLAUDE_MODEL if writer == "haiku" else None,
                      "writer_note": writer_note, "intentions": minded},
              **evening_metrics(evening, calls, args.input_price, args.stuck_threshold, TARIFFS),
              "intentions": intention_counts(evening), "repetition": repetition_counts(evening.events, ALIKE),
              "choice": choice_counts(evening.choices, evening.events),
              "responses": response_counts(evening.events), "aims": aim_counts(evening.events),
              "projects": project_counts(evening.events),
              "goals": goal_counts(evening.events), "promises": promise_counts(evening.events),
              "attention": attention_counts(evening), "conversation": conversation_counts(evening),
              "news": news_metrics(world), "dice": dice_metrics(evening.events),
              "sleep": sleep_metrics(evening.events, world["departed"], world["closes_at"]),
              "giving": giving_counts(evening.events), "manners": manner_counts(evening.events),
              "bar": bar_metrics(evening.events, [item["id"] for item in world["actors"] if on_staff(item)]),
              "writer": writer_stats(evening, calls, "turn", HAIKU_4_5)}
    (args.out / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in evening.events))
    (args.out / "metrics.json").write_text(json.dumps(rounded(report), indent=2) + "\n")
    print(json.dumps(rounded(report), indent=2))
    print(f"{mode} evening, seed {args.seed}, {writer} lines: {round(evening.end_time)} game s in {wall:.1f} "
          f"wall s{''.join(f' ({text})' for text in (note, writer_note) if text)}; wrote {args.out}")
    if tracer is not None:
        print(f"traced to LangSmith project {tracer.project!r}, one thread per character of {tracer.evening!r}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
