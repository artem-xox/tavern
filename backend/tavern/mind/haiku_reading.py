"""Haiku's reading of a player's line: the question and the parse."""

from collections.abc import Mapping
from typing import Any

from tavern.mind.haiku_turns import MAX_TOPIC
from tavern.mind.questions import Ask, Question
from tavern.mind.turn_prompt import shared_prefix
from tavern.social.conversation import ACTS
from tavern.social.player_lines import ReadLine
from tavern.social.turns import check_turn

MAX_TOKENS = 120  # Bounds the answer: a short JSON object, with no line in it.
_RULES = """READING A LINE THAT IS ALREADY WRITTEN

This request is different from the others. A person playing the speaker has typed the line themselves, and the \
words are final: you do not write, change, shorten or answer them. You only read what the speaker does by saying \
them, and answer with the speech act those words perform, whom they are addressed to, and what the conversation \
is about now. The game then decides what the act does in the world, so the act must honestly match the words.

- Choose from the acts offered in this request only. Name the act the words perform, not the one that would make \
the better story: a joke is a joke even when it is rude, and an insult is an insult only when the words insult.
- When the words fit no act clearly, or you are unsure, choose remark.
- The addressee is who the words are meant for. If the request says whom the player addressed, that is the \
addressee. Otherwise take it from the words (a name, a "you" answering the last line); when the words speak to the \
whole company or to no one in particular, the addressee is null.
- An invite names one of the invitation kinds offered, and only an invite does. Telling news names the id of one \
of the news items the speaker holds, and only that act does. Everything else has both null.
- The topic is a few words on what the talk is about after these words."""


class RejectedReading(ValueError):
    """The model's reading broke the answer's rules, so the line is spoken as a remark."""


def reading_question(view: Mapping[str, Any], text: str, to: str) -> Question:
    """Ask for the act of a line the player has typed: shared instructions, reading rules, then the moment.

    Args:
        view: The played guest's view of their scene (`turn_view` as them).
        text: What the player typed.
        to: `auto`, `everyone` or the ID of a guest in the scene.

    Returns:
        A question whose first system block is the line writer's, byte for byte, so that its cache is shared,
        and whose answer schema enumerates the acts offered now and the people in the scene.
    """
    acts = {name: act.meaning for name, act in ACTS.items()}
    return Question(system=[shared_prefix(acts), _RULES], content=_content(view, text, to), schema=_schema(view),
                    max_tokens=MAX_TOKENS)


def parse_reading(view: Mapping[str, Any], text: str, answer: Any) -> dict[str, Any]:
    """Check the model's answer at the boundary.

    Args:
        view: The view the line was read for.
        text: What the player typed.
        answer: The decoded answer object.

    Returns:
        The reading: `act`, `addressee` (an ID or None), `topic`, and `invitation` or `fact_id` where the act
        carries one.

    Raises:
        RejectedReading: It is not exactly an act, addressee, topic, invitation and fact; or it breaks the rules of
            a turn (`turns.check_turn`); or the topic is longer than MAX_TOPIC.
    """
    try:
        if not isinstance(answer, Mapping) or set(answer) != {"act", "addressee", "topic", "invitation", "fact_id"}:
            raise ValueError(f"A reading has exactly an act, addressee, topic, invitation and fact_id, not {answer!r}")
        given = {key: value for key, value in answer.items() if key not in ("invitation", "fact_id")
                 or value is not None}
        if isinstance(given["addressee"], str):
            # Named as listed; anything else is checked as it stands, so a stray id still means its guest.
            given["addressee"] = _labels(view).get(given["addressee"], given["addressee"])
        turn = check_turn(view, {**given, "line": text})
    except ValueError as error:
        raise RejectedReading(str(error)) from error
    if len(turn["topic"]) > MAX_TOPIC:
        raise RejectedReading(f"A topic is a few words, not {turn['topic']!r}")
    return {key: value for key, value in turn.items() if key != "line"}


def claude_reader(ask: Ask) -> ReadLine:
    """Make a reader (`player_lines.ReadLine`) that asks Claude through a port.

    Args:
        ask: The Claude port, e.g. `claude.ask_claude` bound to its config.

    Returns:
        A reader that asks one question per line and returns the checked reading. It raises RejectedReading or the
        port's error, after which the line is spoken as a remark.
    """
    async def read(view: Mapping[str, Any], text: str, to: str) -> Mapping[str, Any]:
        return parse_reading(view, text, await ask(reading_question(view, text, to)))
    return read


def _labels(view: Mapping[str, Any]) -> dict[str, str]:
    # The others in the scene, by how the played guest calls them (`names.called`), to their internal IDs, which the
    # model never sees.
    return {item["name"]: item["id"] for item in view["conversation"]["participants"]
            if item["id"] != view["speaker"]["id"]}


def _content(view: Mapping[str, Any], text: str, to: str) -> str:
    scene, me = view["conversation"], view["speaker"]
    names = {item["id"]: item["name"] for item in scene["participants"]}
    lines = [f"{names.get(turn['speaker'], turn['speaker'])} to "
             f"{names.get(turn['addressee'], 'everyone') if turn['addressee'] else 'everyone'} [{turn['act']}]: "
             f"\"{turn['line']}\"" for turn in scene["turns"][-6:]]
    news = [f'- id "{item["id"]}", {item["topic"]}: "{item["told_as"]}"' for item in me.get("news") or []]
    meant = ("The player did not say whom it is for: take it from the words." if to == "auto"
             else "The player addressed everyone in the scene." if to == "everyone"
             else f"The player addressed {names[to]}.")
    acts = "\n".join(f"- {name}: {meaning}" for name, meaning in view["acts"].items())
    kinds = ", ".join(view.get("invitations") or []) or "none"
    return "\n\n".join([
        f"THE SCENE\n\n{me['name']} is the speaker, talking about {scene['topic']} with "
        f"{', '.join(label for label in _labels(view)) or 'no one'}.\nLast lines, oldest first:\n"
        + ("\n".join(lines) if lines else "No one has spoken yet."),
        f"ACTS OFFERED NOW\n\n{acts}\n\nInvitation kinds open now: {kinds}.",
        "NEWS THE SPEAKER HOLDS\n\n" + ("\n".join(news) if news else "None."),
        f"THE LINE\n\n{meant}\nThe speaker says: \"{text}\"",
        "Read the line now."])


def _schema(view: Mapping[str, Any]) -> dict[str, Any]:
    news = [item["id"] for item in view["speaker"].get("news") or []]
    invitations = list(view.get("invitations") or [])
    return {"type": "object", "properties": {
        "act": {"type": "string", "enum": list(view["acts"]), "description": "The speech act the words perform."},
        "addressee": {"anyOf": [{"type": "string", "enum": list(_labels(view))}, {"type": "null"}],
                      "description": "The one other person the words are for, or null for everyone."},
        "topic": {"type": "string", "description": "What the conversation is about now, in a few words."},
        "invitation": _optional(invitations, "For an invite, the invitation offered; otherwise null."),
        "fact_id": _optional(news, "For share_news, the id of the news told; otherwise null.")},
        "required": ["act", "addressee", "topic", "invitation", "fact_id"], "additionalProperties": False}


def _optional(values: list[str], description: str) -> dict[str, Any]:
    # One of the values or null; with nothing to choose from, only null (an enum cannot be empty).
    return ({"anyOf": [{"type": "string", "enum": values}, {"type": "null"}], "description": description} if values
            else {"type": "null", "description": description})
