"""The Haiku turn writer: a conversation line asked of Claude, laid out for caching and checked at the boundary."""

from collections.abc import Mapping
import re
from typing import Any

from tavern.drunkenness import speech_instruction
from tavern.questions import Ask, Question
from tavern.turn_prompt import shared_prefix, turn_schema
from tavern.turns import TurnResult, TurnWriter, check_turn

MAX_LINE = 160  # Characters; the style asks for about 120, and a little over still reads in a bubble.
MAX_TOPIC = 60  # Characters; a topic is a few words.
MAX_TOKENS = 200  # Bounds the answer: a short JSON object.
# Stage directions: an action in asterisks, or a leading (or bracketed) note on how it is said.
_DIRECTION = re.compile(r"[*\[\]]|^\s*\(")
_NEEDS = (("thirst", "thirst"), ("fatigue", "tiredness"), ("bladder", "bladder"), ("social", "wish for company"),
          ("boredom", "boredom"))
_FAMILIARITY = {"stranger": "a stranger to you", "acquaintance": "an acquaintance", "friend": "an old friend"}


class RejectedTurn(ValueError):
    """The model's line broke the answer's rules, so a scripted line stands in."""


def card_block(speaker: Mapping[str, Any]) -> str:
    """Describe the guest being voiced, for the second cached system block.

    Args:
        speaker: The view's speaker (`turns.turn_view`): name, `card` words or None, `portrait`.

    Returns:
        The card's words and the portrait; the same for the same guest all evening.
    """
    card = speaker["card"]
    if card is None:
        words = f"Name: {speaker['name']}\nA traveller; nothing more is written about them."
    else:
        words = "\n".join(f"{key.capitalize()}: {value}" for key, value in card.items())
    return f"THE GUEST YOU VOICE\n\n{words}\n\nPortrait: {speaker['portrait'] or 'No ties to anyone here.'}"


def turn_content(view: Mapping[str, Any]) -> str:
    """Describe the moment of the turn: the scene, the speaker's mind, drink, places and goal.

    Args:
        view: Scene view of `turns.turn_view`.

    Returns:
        The per-call text that follows the cached blocks.
    """
    return "\n\n".join([_scene(view["conversation"], view["speaker"]), _self(view["speaker"]),
                        "Write the speaker's next line now."])


def _scene(scene: Mapping[str, Any], me: Mapping[str, Any]) -> str:
    people = {item["id"]: item["name"] for item in scene["participants"]}
    present = [f"- {item['name']} (id \"{item['id']}\"): {_FAMILIARITY[item['familiarity']]}; your opinion of "
               f"them is {item['opinion']:+.0f} on -100 to 100" + (f"; on your mind: {'; '.join(item['thoughts'])}"
                                                                    if item["thoughts"] else "")
               for item in me["company"]]
    lines = [f"{people.get(turn['speaker'], turn['speaker'])} to "
             f"{people.get(turn['addressee'], 'everyone') if turn['addressee'] else 'everyone'} [{turn['act']}]: "
             f"\"{turn['line']}\"" for turn in scene["turns"]]
    said = "\n".join(lines) if lines else "No one has spoken yet: the speaker opens the conversation."
    return (f"THE SCENE\n\nLine {scene['turn'] + 1} of a conversation about {scene['topic']}.\n"
            f"Present besides the speaker:\n" + "\n".join(present) + f"\n\nRecent lines, oldest first:\n{said}")


def _self(me: Mapping[str, Any]) -> str:
    needs = ", ".join(f"{label} {me['needs'][key]:.0f}" for key, label in _NEEDS)
    places = ", ".join(f"{item['name']} ({item['kind']})" for item in me["places"]) or \
        "none, so the speaker cannot use share_place"
    goal = me["card"]["goal"] if me["card"] else "to rest and pass a pleasant evening"
    return (f"THE SPEAKER\n\nYou are {me['name']} (id \"{me['id']}\").\nHow they feel: {me['feelings']}\n"
            f"Drink: {speech_instruction(me['drunkenness']) or 'You are sober.'} "
            f"Beers tonight: {me['visit']['beers']}.\n"
            f"Needs (0 calm, 100 desperate; 75 or more presses hard): {needs}.\n"
            f"Places you know: {places}.\nYour goal tonight: {goal}")


def turn_question(view: Mapping[str, Any]) -> Question:
    """Ask for the next line: shared instructions, then the speaker's card, then the moment.

    Args:
        view: Scene view of `turns.turn_view`; its `acts` give the act rules and the schema.

    Returns:
        A question whose first system block is the same for every turn and whose second is the
        same for every turn of one speaker, each closed by a cache breakpoint.
    """
    return Question(system=[shared_prefix(view["acts"]), card_block(view["speaker"])],
                    content=turn_content(view), schema=turn_schema(view["acts"]), max_tokens=MAX_TOKENS)


def parse_turn(view: Mapping[str, Any], answer: Any) -> TurnResult:
    """Check the model's answer at the boundary.

    Args:
        view: The view the line was written for.
        answer: The decoded answer object.

    Returns:
        The answer as a turn result.

    Raises:
        RejectedTurn: It is not exactly a line, act, addressee and topic (see `turns.check_turn`);
            the line is longer than MAX_LINE characters, spans lines or holds a stage direction;
            the topic is longer than MAX_TOPIC; or the speaker shares places while knowing none.
    """
    try:
        result = check_turn(view, answer)
    except ValueError as error:
        raise RejectedTurn(str(error)) from error
    line = result["line"]
    if len(line) > MAX_LINE or "\n" in line or _DIRECTION.search(line):
        raise RejectedTurn(f"A line is one short spoken line without stage directions, not {line!r}")
    if len(result["topic"]) > MAX_TOPIC:
        raise RejectedTurn(f"A topic is a few words, not {result['topic']!r}")
    if result["act"] == "share_place" and not view["speaker"]["places"]:
        raise RejectedTurn(f"{view['speaker']['name']} knows no places to share")
    return result


def claude_writer(ask: Ask) -> TurnWriter:
    """Make a turn writer (`turns.TurnWriter`) that asks Claude through a port.

    Args:
        ask: The Claude port, e.g. `claude.ask_claude` bound to its config, possibly recorded
            or replayed (`recording.record_questions`, `recording.replay_questions`).

    Returns:
        A writer that asks one question per turn and returns the checked line. It ignores the
        runner's AI config (the port holds Claude's) and raises RejectedTurn or the port's
        error, after which the runner speaks a scripted line instead.
    """
    async def write(view: Mapping[str, Any], config: Mapping[str, Any]) -> TurnResult:
        return parse_turn(view, await ask(turn_question(view)))
    return write
