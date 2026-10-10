"""A guest's own stock lines for the moments that need no thought, and when they stand in for the model."""

from collections.abc import Mapping
from string import Formatter
import re
from typing import Any

from tavern.body.drunkenness import speech_instruction
from tavern.mind.scripted import MAX_LINE, planned_act, scripted_turn
from tavern.social.turns import TurnResult

# The kinds of line (keys of `scripted.LINES`) a phrasebook may hold: the moments whose act the game has already
# decided, so that the words are all that is left: an opening greeting, a decided yes or no, and a goodbye.
STOCK_KINDS = ("greet", "accept", "decline", "pressed", "content", "closing")
Phrasebook = Mapping[str, list[str]]

_PLACEHOLDERS = {"name", "me"}  # The addressee as the speaker calls them, and the speaker.
# Stage directions: an action in asterisks, or a leading (or bracketed) note on how it is said, as in `haiku_turns`.
_DIRECTION = re.compile(r"[*\[\]]|^\s*\(")


def check_phrasebook(data: Any) -> Phrasebook:
    """Check a guest's stock lines at the boundary.

    Args:
        data: Untrusted lines by kind, e.g. `{"greet": ["Well met, {name}."]}`.

    Returns:
        The same lines, by kind, in order.

    Raises:
        ValueError: The book is not a nonempty mapping of `STOCK_KINDS` to nonempty lists of distinct lines; or a
            line is not nonempty text of at most `MAX_LINE` characters, spans lines, holds a stage direction, or
            names a placeholder other than `{name}` and `{me}`.
    """
    if not isinstance(data, Mapping) or not data:
        raise ValueError(f"A phrasebook is a nonempty mapping of kinds to lines, not {data!r}")
    book: dict[str, list[str]] = {}
    for kind, lines in data.items():
        if kind not in STOCK_KINDS:
            raise ValueError(f"A phrasebook holds only {', '.join(STOCK_KINDS)}, not {kind!r}")
        if not isinstance(lines, list) or not lines:
            raise ValueError(f"Phrasebook {kind} must be a nonempty list of lines, not {lines!r}")
        if len(set(lines)) != len(lines):
            raise ValueError(f"Phrasebook {kind} repeats a line")
        for line in lines:
            _check_line(kind, line)
        book[kind] = list(lines)
    return book


def _check_line(kind: str, line: Any) -> None:
    if not isinstance(line, str) or not line.strip():
        raise ValueError(f"A phrasebook {kind} line must be nonempty text, not {line!r}")
    if len(line) > MAX_LINE or "\n" in line or _DIRECTION.search(line):
        raise ValueError(f"A phrasebook {kind} line is one short spoken line without stage directions, not {line!r}")
    try:
        fields = [(name, spec, conversion) for _, name, spec, conversion in Formatter().parse(line) if name is not None]
        line.format(name="", me="")
    except (ValueError, KeyError, IndexError) as error:
        raise ValueError(f"A phrasebook {kind} line may hold only {{name}} and {{me}}: {line!r}") from error
    if any(name not in _PLACEHOLDERS or spec or conversion for name, spec, conversion in fields):
        raise ValueError(f"A phrasebook {kind} line may hold only {{name}} and {{me}}: {line!r}")


def stock_turn(view: Mapping[str, Any], book: Phrasebook | None) -> TurnResult | None:
    """Speak a moment that needs no thought in the guest's own words, if their phrasebook has them.

    Only a sober, healthy guest who has not just fought speaks stock lines, since drink, fever and anger
    colour their words. The act is the scripted rule's (`scripted.planned_act`), so the game's decisions are
    the same as without a model; a yes or no is stock only when the invitee has decided it already.

    Args:
        view: Scene view of `turns.turn_view`.
        book: The speaker's phrasebook, or None for a guest without one.

    Returns:
        The turn (`turns.TurnResult`), or None when a model should write this line: no phrasebook, a moment
        that is not a stock one, or every stock line of the kind already said tonight by this speaker.
    """
    me = view["speaker"]
    if not book or speech_instruction(me.get("drunkenness", 0.0)) or me.get("ailing") or me.get("hurt") \
            or me.get("just_fought"):
        return None
    act, kind = planned_act(view)
    if kind not in STOCK_KINDS or kind not in book or act not in view["acts"] or _needs_thought(view, kind):
        return None
    unsaid = _unsaid(book[kind], view)
    return scripted_turn(view, {kind: unsaid}) if unsaid else None


def says_from(book: Phrasebook, line: str) -> bool:
    """Tell whether a spoken line is one of a phrasebook's, whoever it was said to.

    Args:
        book: A guest's stock lines.
        line: A line they spoke.

    Returns:
        True when the line is a stock line with its placeholders filled.
    """
    return any(_pattern(text).fullmatch(line) for lines in book.values() for text in lines)


def _needs_thought(view: Mapping[str, Any], kind: str) -> bool:
    # An answer the invitee has not decided is theirs to make; a greeting that carries what the speaker came
    # over to do (an aim with acts on offer) is the writer's to word.
    if kind in ("accept", "decline"):
        return view.get("answer") != kind
    aim = view["speaker"].get("aim")
    if kind == "greet" and aim is not None and not aim["done"] and aim["id"] != "pass_time":
        return any(act in view["acts"] for act in aim["acts"])
    return False


def _unsaid(lines: list[str], view: Mapping[str, Any]) -> list[str]:
    # The lines this speaker has not said tonight, in this scene or an earlier one, whoever they were said to.
    me = view["speaker"]
    said = [item["line"] for scene in me.get("earlier", []) for item in scene["lines"] if item["speaker"] == me["name"]]
    said += [turn["line"] for turn in view["conversation"]["turns"] if turn["speaker"] == me["id"]]
    return [line for line in lines if not any(_pattern(line).fullmatch(spoken) for spoken in said)]


def _pattern(template: str) -> "re.Pattern[str]":
    parts = re.split(r"(\{name\}|\{me\})", template)
    return re.compile("".join(".+" if part in ("{name}", "{me}") else re.escape(part) for part in parts))
