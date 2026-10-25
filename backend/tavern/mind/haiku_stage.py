"""The Haiku stage writer: the words of a number, a heckle or a comeback, asked of Claude and checked at the boundary."""

from collections.abc import Mapping
import re
from typing import Any

from tavern.mind.haiku_turns import card_block
from tavern.mind.questions import Ask, Question
# A stage line may run as long as a conversation line: the bubble cuts it into pieces it shows in turn. Live evenings
# (seeds 1 and 5, 2026-10-25) threw good lines of 122-172 characters away at tighter limits.
from tavern.mind.scripted import MAX_LINE
from tavern.mind.stage_prompt import shared_prefix, stage_schema
from tavern.social.stage_lines import StageWriter

MAX_TOKENS = 300  # Bounds the answer: at most three short lines in a JSON object.
# How many lines each claim wants: a number is a short bit, a heckle and a comeback one shout.
LINES = {"number": (2, 3), "heckle": (1, 1), "comeback": (1, 1)}
# Stage directions: an action in asterisks or brackets, or a leading note in parentheses (as `haiku_turns` rejects them).
_DIRECTION = re.compile(r"[*\[\]]|^\s*\(")


class RejectedStage(ValueError):
    """The model's words broke the answer's rules, so the scripted words are said instead."""


def stage_question(view: Mapping[str, Any]) -> Question:
    """Ask for the words of a claim: the shared stage instructions, then the speaker's card, then the moment.

    Args:
        view: A claim's view (`stage_lines.stage_claims`).

    Returns:
        A question whose first system block is the same for every claim and whose second is the same for every claim
        of one speaker, each closed by a cache breakpoint.
    """
    return Question(system=[shared_prefix(), card_block(view["speaker"])], content=_moment(view),
                    schema=stage_schema(), max_tokens=MAX_TOKENS)


def _moment(view: Mapping[str, Any]) -> str:
    me = view["speaker"]
    intention = f"\nWhat you mean to do: {me['intention']}" if me.get("intention") else ""
    room = "\n".join(f"- {item['name']}: {item['opinion']:+.0f}" for item in view["room"]) or "Nobody else is here."
    seen = "\n".join(f"- {item}" for item in me["seen"]) or "Nothing worth remembering yet."
    return "\n\n".join([
        f"THE SPEAKER\n\nYou are {me['name']}.\nHow they feel: {me['feelings']}\nDrink: {me['drink']}{intention}",
        f"THE ROOM\n\nEveryone else in the hall, and what you think of them on -100 to 100:\n{room}",
        f"TONIGHT\n\nWhat you did and saw, oldest first:\n{seen}",
        f"THE TASK\n\n{_task(view)}"])


def _task(view: Mapping[str, Any]) -> str:
    if view["kind"] == "number":
        return f"You are up on the stage and the room is looking at you. Perform {view['number']['brief']}. " \
               "Write 2 or 3 lines."
    at = view["at"]["name"]
    if view["kind"] == "heckle":
        return f"{at} has just said from the stage: \"{view['heard']}\" Shout one heckle at them from the floor: " \
               "one line."
    return f"{at} has just heckled you from the floor: \"{view['heard']}\" Answer from the stage with one comeback: " \
           "one line."


def parse_stage(view: Mapping[str, Any], answer: Any) -> list[str]:
    """Check the model's answer at the boundary.

    Args:
        view: The view the words were written for; its `kind` says how many lines it wants (`LINES`).
        answer: The decoded answer object.

    Returns:
        The lines, stripped.

    Raises:
        RejectedStage: It is not exactly `lines`, a list of the right length for the claim, or a line is blank,
            longer than `MAX_LINE`, spans lines or holds a stage direction.
    """
    if not isinstance(answer, Mapping) or set(answer) != {"lines"} or not isinstance(answer["lines"], list):
        raise RejectedStage(f"A stage answer is exactly a list of lines, not {answer!r}")
    lines, (least, most) = answer["lines"], LINES[view["kind"]]
    if not least <= len(lines) <= most:
        raise RejectedStage(f"A {view['kind']} has {least} to {most} lines, not {len(lines)}")
    for line in lines:
        if not isinstance(line, str) or not line.strip() or len(line) > MAX_LINE or "\n" in line \
                or _DIRECTION.search(line):
            raise RejectedStage(f"A stage line is one short spoken line without stage directions, not {line!r}")
    return [line.strip() for line in lines]


def claude_stage_writer(ask: Ask) -> StageWriter:
    """Make a stage writer (`stage_lines.StageWriter`) that asks Claude through a port.

    Args:
        ask: The Claude port, possibly recorded or replayed (`recording.record_questions`, `recording.replay_questions`).

    Returns:
        A writer that asks one question per claim and returns the checked lines; it raises `RejectedStage` or the
        port's error, after which the scripted words are said instead (`stage_lines.deliver_stage`).
    """
    async def write(view: Mapping[str, Any], config: Mapping[str, Any]) -> list[str]:
        return parse_stage(view, await ask(stage_question(view)))
    return write
