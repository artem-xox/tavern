"""Play one headless evening in lockstep; write its event log, model calls and metrics."""

import argparse
import asyncio
import json
from pathlib import Path
from random import Random
import time
from typing import Any, Mapping

from dotenv import dotenv_values

from tavern import jev
from tavern.agents import Evaluators
from tavern.cards import parse_cards
from tavern.claude import HAIKU_4_5, ClaudeError, ask_claude
from tavern.intentions import Intender, intention_writer
from tavern.lockstep import Pace, evening_mode, run_evening
from tavern.metrics import attention_counts, conversation_counts, evening_metrics, intention_counts
from tavern.questions import Question
from tavern.recording import Record, format_record, parse_records, record_calls, record_questions, replay_calls, \
    replay_questions
from tavern.scenario import open_evening, parse_scenario

DECIDES = {"local": "the local policy (no model)", "live": "Jev, recorded", "replay": "Jev answers replayed"}


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


def evaluators(mode: str, recording: Path | None, calls: list[Record], log: Path) -> Evaluators:
    """Wire the model port for a mode.

    Args:
        mode: Evening mode.
        recording: Calls to replay, in replay mode.
        calls: Receives the evening's calls: recorded live, or loaded for replay.
        log: JSON-lines file each live call is appended to as soon as it ends.
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
    log.write_text("")

    def keep(record: Record) -> None:
        calls.append(record)
        with log.open("a") as lines:
            lines.write(format_record(record))
    return Evaluators(record_calls("actions", jev.evaluate_actions_metered, keep, time.monotonic, jev.JevError),
                      record_calls("seats", jev.evaluate_seats_metered, keep, time.monotonic, jev.JevError),
                      record_calls("family", jev.evaluate_actions_metered, keep, time.monotonic, jev.JevError))


def mind(mode: str, values: Mapping[str, Any], prefix: str, calls: list[Record],
         log: Path) -> tuple[Intender | None, str]:
    """Wire the mind port that writes guests' intentions, and say how it runs.

    Args:
        mode: Evening mode.
        values: Parsed env file; live intentions need `ANTHROPIC_API_KEY`.
        prefix: Shared system prefix of every intention question.
        calls: The evening's calls (loaded already in replay mode); live calls are added.
        log: JSON-lines file each live call is appended to.
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
    asked = record_questions("intention", metered, keep, time.monotonic, ClaudeError)
    return intention_writer(prefix, asked), "Claude Haiku 4.5 (claude-haiku-4-5), recorded"


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
    ports = evaluators(mode, args.calls, calls, args.out / "calls.jsonl")
    room = json.loads((root / "data" / "tavern.json").read_text())
    try:
        cards = parse_cards([json.loads(path.read_text()) for path in sorted(args.characters.glob("*.json"))])
        world = open_evening(room, parse_scenario(json.loads(args.scenario.read_text()), cards), args.seed)
    except (OSError, ValueError) as error:
        parser.error(f"cannot open the evening: {error}")
    settings = config(values, mode)
    intender, minded = mind(mode, values, (root / "data" / "minds" / "intention_prefix.md").read_text(), calls,
                            args.out / "calls.jsonl")
    started = time.monotonic()
    evening = asyncio.run(run_evening(world, settings, Random(args.seed), ports, pace, intender=intender))
    wall = time.monotonic() - started
    # A replay matches its recording only with the same seed, pace and temperature, so they are shown.
    report = {"run": {"mode": mode, "decides": DECIDES[mode], "note": note, "seed": args.seed,
                      "model": settings["model"], "temperature": settings["temperature"], "step": pace.step,
                      "model_latency": pace.model_latency, "time_limit": pace.time_limit,
                      "stuck_threshold": args.stuck_threshold, "input_usd_per_million": args.input_price,
                      "intentions": minded},
              **evening_metrics(evening, calls, args.input_price, args.stuck_threshold, {"intention": HAIKU_4_5}),
              "intentions": intention_counts(evening),
              "attention": attention_counts(evening), "conversation": conversation_counts(evening)}
    (args.out / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in evening.events))
    (args.out / "metrics.json").write_text(json.dumps(rounded(report), indent=2) + "\n")
    print(json.dumps(rounded(report), indent=2))
    print(f"{mode} evening, seed {args.seed}: {round(evening.end_time)} game s in {wall:.1f} wall s"
          f"{f' ({note})' if note else ''}; wrote {args.out}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
