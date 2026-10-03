"""Play one headless evening in lockstep; write its event log, model calls and metrics."""

import argparse
import asyncio
import json
from pathlib import Path
from random import Random
import time
from typing import Any, Callable, Mapping

from dotenv import dotenv_values

from tavern import jev
from tavern.agents import Evaluators
from tavern.cards import parse_cards
from tavern.claude import HAIKU_4_5, ClaudeError, ask_claude
from tavern.haiku_turns import claude_writer, writer_mode
from tavern.lockstep import Pace, evening_mode, run_evening
from tavern.metrics import attention_counts, conversation_counts, evening_metrics, writer_stats
from tavern.questions import Question
from tavern.recording import (Record, format_record, parse_records, record_calls, record_questions, replay_calls,
                              replay_questions)
from tavern.scenario import open_evening, parse_scenario
from tavern.scripted import write_scripted_turn
from tavern.turns import TurnWriter

DECIDES = {"local": "the local policy (no model)", "live": "Jev, recorded", "replay": "Jev answers replayed"}
CLAUDE_MODEL = "claude-haiku-4-5"
TARIFFS = {"turn": HAIKU_4_5, "card": HAIKU_4_5}


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
    parser.add_argument("--mode", choices=("local", "live", "replay"),
                        help="default: live when TYPESAFE_API_KEY is in the env file, else local")
    parser.add_argument("--out", type=Path, default=root / "runs" / "evening-0")
    parser.add_argument("--calls", type=Path, help="recorded calls.jsonl to replay (replay mode)")
    parser.add_argument("--writer", choices=("haiku", "scripted"),
                        help="who writes conversation lines; default: Haiku when ANTHROPIC_API_KEY is in the env "
                             "file (a replay: when the recording has turns), else scripted")
    parser.add_argument("--env-file", type=Path, default=root / ".env")
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
            "timeout": float(values.get("AI_TIMEOUT", "8")), "temperature": float(values.get("AI_TEMPERATURE", "0.25"))}


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


def evaluators(mode: str, recording: Path | None, calls: list[Record], keep: Callable[[Record], None]) -> Evaluators:
    """Wire the model port for a mode.

    Args:
        mode: Evening mode.
        recording: Calls to replay, in replay mode.
        calls: Receives the calls loaded for replay.
        keep: Receives each live call as soon as it ends.
    Returns:
        Evaluators for every decision stage; the actions within a chosen family are
        ordinary actions, so Jev scores them with the action question, recorded as `family`.
    """
    if mode == "replay":
        calls.extend(parse_records(recording.read_text()))
        return Evaluators(*(replay_calls(kind, calls, jev.JevError) for kind in ("actions", "seats", "family")))
    if mode == "local":
        # Without a key the decisions never ask a model; Jev only fills the port.
        return Evaluators(jev.evaluate_actions, jev.evaluate_seats)
    return Evaluators(record_calls("actions", jev.evaluate_actions_metered, keep, time.monotonic, jev.JevError),
                      record_calls("seats", jev.evaluate_seats_metered, keep, time.monotonic, jev.JevError),
                      record_calls("family", jev.evaluate_actions_metered, keep, time.monotonic, jev.JevError))


def turn_writer(writer: str, mode: str, calls: list[Record], keep: Callable[[Record], None],
                values: Mapping[str, Any]) -> TurnWriter:
    """Wire the conversation line writer.

    Args:
        writer: `haiku` or `scripted` (see `haiku_turns.writer_mode`).
        mode: Evening mode; a replay answers Haiku turns from `calls`.
        calls: The evening's calls, loaded for a replay.
        keep: Receives each live Haiku call as soon as it ends, recorded as `turn`.
        values: Parsed env file with ANTHROPIC_API_KEY.
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
    return claude_writer(record_questions("turn", ask, keep, time.monotonic, ClaudeError))


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
    args.out.mkdir(parents=True, exist_ok=True)
    calls: list[Record] = []
    keep = calls.append if mode == "replay" else keeper(calls, args.out / "calls.jsonl")
    ports = evaluators(mode, args.calls, calls, keep)
    keyed = (any(record["kind"] == "turn" for record in calls) if mode == "replay"
             else bool(values.get("ANTHROPIC_API_KEY")))
    try:
        writer, writer_note = writer_mode(args.writer, keyed)
    except ValueError as error:
        parser.error(str(error))
    lines = turn_writer(writer, mode, calls, keep, values)
    room = json.loads((root / "data" / "tavern.json").read_text())
    try:
        cards = parse_cards([json.loads(path.read_text()) for path in sorted(args.characters.glob("*.json"))])
        world = open_evening(room, parse_scenario(json.loads(args.scenario.read_text()), cards), args.seed)
    except (OSError, ValueError) as error:
        parser.error(f"cannot open the evening: {error}")
    settings = config(values, mode)
    started = time.monotonic()
    evening = asyncio.run(run_evening(world, settings, Random(args.seed), ports, pace, lines))
    wall = time.monotonic() - started
    # A replay matches its recording only with the same seed, pace and temperature, so they are shown.
    report = {"run": {"mode": mode, "decides": DECIDES[mode], "note": note, "seed": args.seed,
                      "model": settings["model"], "temperature": settings["temperature"], "step": pace.step,
                      "model_latency": pace.model_latency, "time_limit": pace.time_limit,
                      "stuck_threshold": args.stuck_threshold, "input_usd_per_million": args.input_price,
                      "writer": writer, "writer_model": CLAUDE_MODEL if writer == "haiku" else None,
                      "writer_note": writer_note},
              **evening_metrics(evening, calls, args.input_price, args.stuck_threshold, TARIFFS),
              "attention": attention_counts(evening), "conversation": conversation_counts(evening),
              "writer": writer_stats(evening, calls, "turn", HAIKU_4_5)}
    (args.out / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in evening.events))
    (args.out / "metrics.json").write_text(json.dumps(rounded(report), indent=2) + "\n")
    print(json.dumps(rounded(report), indent=2))
    print(f"{mode} evening, seed {args.seed}, {writer} lines: {round(evening.end_time)} game s in {wall:.1f} "
          f"wall s{''.join(f' ({text})' for text in (note, writer_note) if text)}; wrote {args.out}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
