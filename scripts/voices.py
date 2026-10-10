"""Write each guest's stock lines (`data/voices`) from their card with Claude; only stale or missing ones, unless forced."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from tavern.adapters.claude import ClaudeError, ask_claude  # noqa: E402
from tavern.mind.voice_question import card_hash, voice_lines, voice_question  # noqa: E402

MINIMUM = 5  # Fewest lines of a moment worth keeping; the prompt asks for eight.


def arguments() -> argparse.ArgumentParser:
    """Describe the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, nargs="+", default=[root / "data" / "characters", root / "data" / "staff"],
                        help="directories of character cards")
    parser.add_argument("--out", type=Path, default=root / "data" / "voices")
    parser.add_argument("--prompt", type=Path, default=root / "data" / "minds" / "voice_prompt.md")
    parser.add_argument("--model", default="claude-haiku-5-5",
                        help="a model the Claude adapter can ask (it switches thinking off, which Sonnet 5.5 rejects)")
    parser.add_argument("--only", nargs="+", help="character IDs to write; default: all")
    parser.add_argument("--force", action="store_true", help="write lines that are not stale too")
    parser.add_argument("--env-file", type=Path, default=root / ".env")
    return parser


async def write_voice(card: dict[str, Any], prompt: str, config: dict[str, Any], out: Path) -> str:
    """Ask for one guest's stock lines and write their file.

    Args:
        card: The guest's card.
        prompt: The instructions.
        config: The Claude adapter's configuration.
        out: Directory of voice files.

    Returns:
        A line saying what was written and how many lines were left out as unfit.

    Raises:
        ClaudeError: The model could not be asked.
        ValueError: The answer broke the phrasebook's rules or held too few lines.
    """
    answer, usage = await ask_claude(voice_question(prompt, card), config)
    lines, left_out = voice_lines(answer, MINIMUM)
    (out / f"{card['id']}.json").write_text(
        json.dumps({"card_hash": card_hash(card), "lines": lines}, indent=2, ensure_ascii=False) + "\n")
    return (f"{card['id']}: {sum(map(len, lines.values()))} lines, {len(left_out)} left out, "
            f"{usage['output_tokens']} output tokens")


def main() -> None:
    """Write the stale voices."""
    args = arguments().parse_args()
    key = dotenv_values(args.env_file).get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit(f"No ANTHROPIC_API_KEY in {args.env_file}")
    config = {"anthropic_api_key": key, "model": args.model, "timeout": 60.0, "retries": 1}
    prompt = args.prompt.read_text()
    args.out.mkdir(parents=True, exist_ok=True)
    cards = [json.loads(path.read_text()) for directory in args.cards for path in sorted(directory.glob("*.json"))]
    for card in cards:
        voice = args.out / f"{card['id']}.json"
        current = voice.is_file() and json.loads(voice.read_text())["card_hash"] == card_hash(card)
        if (args.only and card["id"] not in args.only) or (current and not args.force):
            print(f"{card['id']}: kept")
            continue
        try:
            print(asyncio.run(write_voice(card, prompt, config, args.out)))
        except (ClaudeError, ValueError) as error:
            print(f"{card['id']}: FAILED ({error})")


if __name__ == "__main__":
    main()
