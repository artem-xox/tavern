"""Run the local dialogue eval: live evenings of two famous guests, a minute of their talk measured and judged.

Local only: it plays real evenings with Jev and Haiku (keys from the env file) and costs a few cents a run. Use it to
check a prompt or a mind change, not in CI.
"""

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from dotenv import dotenv_values

from tavern.adapters.claude import ClaudeError, ask_claude
from tavern.evening.dialogue_judge import CRITERIA, Verdict, judge_dialogue
from tavern.evening.dialogue_metrics import dialogue_metrics, missed_thresholds, pair_transcript, talk_window
from tavern.mind.questions import Question

JUDGE_MODEL = "claude-haiku-5-5"  # The game's own line model: the eval spends no more than an evening does.
METRICS = ("lines", "balance", "repeated", "echo", "novelty", "variety", "on_brief", "fallbacks")


def arguments(root: Path) -> argparse.ArgumentParser:
    """Describe the command line.

    Args:
        root: Repository directory, for default paths.
    Returns:
        Parser of the eval options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=root / "data" / "evals" / "putin_zelensky.json",
                        help="pair, brief words, judge notes, thresholds and scenarios")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1], help="seeds to play each scenario with")
    parser.add_argument("--only", nargs="+", help="scenario names to play; default: all")
    parser.add_argument("--out", type=Path, default=root / "runs" / "evals" / f"{datetime.now():%Y%m%d-%H%M%S}")
    parser.add_argument("--env-file", type=Path, default=root / ".env")
    parser.add_argument("--jobs", type=int, default=3, help="evenings played at once")
    parser.add_argument("--engine", type=Path, default=root,
                        help="checkout whose scripts/evening.py and backend play the evenings, e.g. a worktree of "
                             "main to compare a change against; it must know --no-retelling")
    return parser


async def play(engine: Path, scenario: Mapping[str, Any], name: str, seed: int, args: argparse.Namespace,
               spec: Mapping[str, Any], slots: asyncio.Semaphore) -> Path:
    """Play one evening through `scripts/evening.py`, live, without the retelling.

    Args:
        engine: Checkout that plays the evening.
        scenario: The evening's scenario.
        name: Its name in the spec.
        seed: The evening's seed.
        args: Command line, for the output folder and env file.
        spec: The eval spec, for the time limit.
        slots: Limits how many evenings play at once.
    Returns:
        The run folder holding `events.jsonl` and `evening.log`.
    Raises:
        RuntimeError: The evening failed.
    """
    run = args.out / f"{name}-{seed}"
    run.mkdir(parents=True, exist_ok=True)
    (run / "scenario.json").write_text(json.dumps(scenario, indent=2))
    command = [sys.executable, str(engine / "scripts" / "evening.py"), "--scenario", str(run / "scenario.json"),
               "--seed", str(seed), "--out", str(run), "--time-limit", str(spec["time_limit"]),
               "--env-file", str(args.env_file), "--mode", "live", "--writer", "haiku", "--no-retelling"]
    async with slots:
        with (run / "evening.log").open("w") as log:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=log, stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "PYTHONPATH": str(engine / "backend")})
            code = await process.wait()
    if code != 0:
        raise RuntimeError(f"{name} with seed {seed} failed; see {run / 'evening.log'}")
    return run


async def measure(run: Path, spec: Mapping[str, Any], claude: Mapping[str, Any]) -> dict[str, Any]:
    """Measure and judge the pair's first minute of talk in one evening.

    Args:
        run: The run folder.
        spec: The eval spec.
        claude: Claude config for the judge.
    Returns:
        The run's name, its values (metrics and judge scores), the thresholds it missed, the judge's notes and
        the transcript.
    """
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    window = talk_window(events, spec["pair"], spec["window"])
    transcript = pair_transcript(window, spec["pair"])
    values: dict[str, float] = dict(dialogue_metrics(window, spec["pair"], spec["brief"]))
    verdict: Verdict | None = None
    if transcript:
        async def ask(question: Question) -> dict[str, Any]:
            return (await ask_claude(question, claude))[0]
        verdict = await judge_dialogue(transcript, spec["look_for"], ask)
        values.update(verdict["scores"])
    return {"run": run.name, "values": values, "missed": missed_thresholds(values, spec["thresholds"]),
            "notes": verdict["notes"] if verdict else "They never spoke to each other.", "transcript": transcript}


def report(results: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]) -> str:
    """Write the eval report in Markdown: a table of every run and the mean, then each talk and its notes.

    Args:
        results: What `measure` returned per run.
        spec: The eval spec, for the window.
    Returns:
        The report.
    """
    columns = [*METRICS, *CRITERIA]
    rows = [f"| {item['run']} | " + " | ".join(_cell(item["values"].get(name)) for name in columns)
            + f" | {'; '.join(item['missed']) or 'ok'} |" for item in results]
    means = {name: [item["values"][name] for item in results if name in item["values"]] for name in columns}
    mean = "| **mean** | " + " | ".join(_cell(sum(found) / len(found) if found else None)
                                       for found in means.values()) + " | |"
    header = "| run | " + " | ".join(columns) + " | missed |\n|" + "---|" * (len(columns) + 2)
    talks = "\n\n".join(f"### {item['run']}\n\n{item['notes']}\n\n" + "\n".join(f"- {line}" for line in item["transcript"])
                        for item in results)
    return (f"# Dialogue eval\n\nThe pair's first {spec['window']} s of talk per evening.\n\n"
            f"{header}\n" + "\n".join(rows) + f"\n{mean}\n\n## Talks\n\n{talks}\n")


def _cell(value: float | None) -> str:
    # Presentation only: counts stay whole, shares get two decimals.
    if value is None:
        return "–"
    return f"{value:g}" if float(value).is_integer() else f"{value:.2f}"


async def run_eval(args: argparse.Namespace, spec: Mapping[str, Any],
                   claude: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Play every chosen scenario with every seed at once, then measure each.

    Args:
        args: Command line.
        spec: The eval spec.
        claude: Claude config for the judge.
    Returns:
        What `measure` returned per run, in scenario then seed order.
    """
    names = args.only or list(spec["scenarios"])
    unknown = [name for name in names if name not in spec["scenarios"]]
    if unknown:
        raise ValueError(f"Unknown scenarios {unknown!r}; the spec has {sorted(spec['scenarios'])!r}")
    slots = asyncio.Semaphore(args.jobs)
    runs = await asyncio.gather(*(play(args.engine, spec["scenarios"][name], name, seed, args, spec, slots)
                                  for name in names for seed in args.seeds))
    return list(await asyncio.gather(*(measure(run, spec, claude) for run in runs)))


def main(root: Path) -> None:
    """Run the eval, write `report.md` and `report.json`, and exit 1 when a run missed a threshold.

    Args:
        root: Repository directory.
    """
    args = arguments(root).parse_args()
    values = dotenv_values(args.env_file)
    missing = [key for key in ("TYPESAFE_API_KEY", "ANTHROPIC_API_KEY") if not values.get(key)]
    if missing:
        sys.exit(f"The dialogue eval plays live evenings: {', '.join(missing)} missing from {args.env_file}")
    spec = json.loads(args.spec.read_text())
    claude = {"anthropic_api_key": values["ANTHROPIC_API_KEY"], "model": JUDGE_MODEL, "timeout": 60.0, "retries": 1}
    try:
        results = asyncio.run(run_eval(args, spec, claude))
    except (ClaudeError, RuntimeError, ValueError) as error:
        sys.exit(f"dialogue eval failed: {error}")
    text = report(results, spec)
    (args.out / "report.md").write_text(text)
    (args.out / "report.json").write_text(json.dumps(results, indent=2) + "\n")
    print(text.split("\n## Talks")[0])
    print(f"wrote {args.out / 'report.md'}")
    if any(item["missed"] for item in results):
        sys.exit(1)


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
