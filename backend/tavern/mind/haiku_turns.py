"""The Haiku turn writer: a conversation line asked of Claude, laid out for caching and checked at the boundary."""

from collections.abc import Mapping, Sequence
import re
from typing import Any

from tavern.body.ailment import urgent_needs
from tavern.body.drunkenness import speech_instruction
from tavern.mind.questions import Ask, Question
from tavern.mind.scripted import BORED, CONTENT, MAX_LINE, PRESSING
from tavern.mind.turn_prompt import shared_prefix, turn_schema
from tavern.social.conversation import ACTS
from tavern.social.invitations import KINDS
from tavern.social.turns import TurnResult, TurnWriter, check_turn

MAX_TOPIC = 60  # Characters; a topic is a few words.
MAX_TOKENS = 200  # Bounds the answer: a short JSON object.
# Stage directions: an action in asterisks, or a leading (or bracketed) note on how it is said.
_DIRECTION = re.compile(r"[*\[\]]|^\s*\(")
_NEEDS = (("thirst", "thirst"), ("fatigue", "tiredness"), ("bladder", "bladder"), ("social", "wish for company"),
          ("boredom", "boredom"))
# How the speaker holds a piece of news, by confidence: the writer is shown words, never the number.
_BELIEF = ((0.85, "you are sure of it"), (0.55, "you believe it"), (0.0, "a rumour you half believe"))
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
    nudges = _nudges(view["conversation"], view["speaker"], view.get("invitations") or [], view["acts"],
                     view.get("closing_called", False), view.get("answer"))
    earlier = _earlier(view["speaker"].get("earlier") or [])
    seen = _seen(view["speaker"].get("seen") or [])
    return "\n\n".join([_scene(view["conversation"], view["speaker"]), *([earlier] if earlier else []),
                        *([seen] if seen else []),
                        _self(view["speaker"]), _news(view["speaker"]), *([f"THE MOMENT\n\n{nudges}"] if nudges else []), _offer(view),
                        "Write the speaker's next line now: one or two short sentences, under 120 characters."])


def _offer(view: Mapping[str, Any]) -> str:
    # The cached prefix explains every act; the moment says which of them fit now
    # (`conversation.offered_acts`), so the prefix stays the same for every turn.
    kinds = view.get("invitations") or []
    invitations = (f" An invite must name one of these invitations: {', '.join(kinds)}; any other act has "
                   "invitation null." if "invite" in view["acts"] and kinds else " Set invitation to null.")
    # Guests may know each other only by looks, so the answer must name people by ID.
    others = [f'"{item["id"]}"' for item in view["conversation"]["participants"] if item["id"] != view["speaker"]["id"]]
    return (f"ALLOWED NOW\n\nActs you may use for this line: {', '.join(view['acts'])}.{invitations} "
            f"The addressee must be null or one of these ids: {', '.join(others)}.")


def _nudges(scene: Mapping[str, Any], me: Mapping[str, Any], invitations: Sequence[str], acts: Sequence[str],
            closing_called: bool = False, answer: str | None = None) -> str:
    # The scripted writer's thresholds (`scripted.PRESSING`, `scripted.CONTENT`) say when a need
    # presses or company is enough; left to itself, the model rarely leaves or shares places.
    # A barkeep's needs read as all at 0, which would send him off for company enough: his nudge says he stays.
    duty = me.get("on_duty")
    urgent = urgent_needs(me.get("ailing", False))
    pressing = [f"{label} {me['needs'][key]:.0f}" for key, label in _NEEDS if key in urgent and me["needs"][key] >= PRESSING]
    shared = any(turn["speaker"] == me["id"] and turn["act"] == "share_place" for turn in scene["turns"])
    told = any(turn["speaker"] == me["id"] and turn["act"] == "share_news" for turn in scene["turns"])
    return " ".join(text for text in (
        f"You are the barkeep, on duty behind the {duty}: you stay while the guest does, and leave only to pour."
        if duty else "",
        f"Pressing now: {', '.join(pressing)}. The speaker should excuse themselves and leave the conversation."
        if pressing and not duty else "",
        "The barkeep has just called closing time: the talk turns to goodbyes and heading home, so the speaker "
        "winds it down and may say goodbye."
        if closing_called and not duty else "",
        "The speaker has had enough company for now and may say goodbye after answering."
        if me["needs"]["social"] < CONTENT and not duty else "",
        "The speaker has not yet told anyone here where the places they know are; someone may want to know."
        if me["places"] and not shared else "",
        "The speaker carries news the others have not heard from them; telling one piece is welcome."
        if me.get("news") and not told else "",
        "The speaker is bored, and the dice table stands free: a game of dice is a fine thing to propose."
        if me["needs"]["boredom"] >= BORED and "dice_together" in invitations else "",
        "The speaker means to join someone here at their table: when saying so, use the promise act addressed to "
        "them, so the game can hold the speaker to it; promise it only if the speaker means to come."
        if "promise" in acts and me.get("aims_at") in {item["id"] for item in scene["participants"]} else "",
        _came_for(me.get("aim"), acts), _answering(answer)) if text)


def _answering(answer: str | None) -> str:
    # What the speaker has decided to answer the invitation waiting for them; the acts offered are then only that one.
    if answer is None:
        return ""
    if answer == "accept":
        return "The speaker has decided to accept the invitation: say yes in their own words."
    if answer == "decline":
        return "The speaker has decided to turn it down: refuse in their own words, politely or not as they are."
    kind = answer.partition(":")[2]
    return (f"The speaker has decided to turn it down and offer something else: invite them to {KINDS[kind]} instead "
            f"(invitation {kind}) in their own words.")


def _came_for(aim: Mapping[str, Any] | None, acts: Sequence[str]) -> str:
    # What the speaker came over to do, until they have: the acts that carry it, and the news or invitation to name.
    # Passing the time needs no nudge, and an aim none of whose acts is offered now waits.
    fitting = [act for act in (aim["acts"] if aim else []) if act in acts]
    if aim is None or aim["done"] or aim["id"] == "pass_time" or not fitting:
        return ""
    names = {"share_news": "fact_id", "invite": "invitation"}
    named = f" ({names[fitting[0]]} {aim['detail']})" if fitting[0] in names and aim["detail"] else ""
    return (f"The speaker came over to {aim['words']}: say so in their own words, early. "
            f"Acts that fit: {', '.join(fitting)}{named}.")


def _scene(scene: Mapping[str, Any], me: Mapping[str, Any]) -> str:
    people = {item["id"]: item["name"] for item in scene["participants"]}
    barkeeps = {item["id"] for item in scene["participants"] if item.get("on_duty")}
    present = [f"- {item['name']}{' (the barkeep)' if item['id'] in barkeeps else ''} (id \"{item['id']}\"): "
               f"{_FAMILIARITY[item['familiarity']]}; your opinion of "
               f"them is {item['opinion']:+.0f} on -100 to 100" + ("; looks pale and feverish" if item.get("ailing") else "")
               + (f"; on your mind: {'; '.join(item['thoughts'])}"
                                                                    if item["thoughts"] else "")
               for item in me["company"]]
    lines = [f"{people.get(turn['speaker'], turn['speaker'])} to "
             f"{people.get(turn['addressee'], 'everyone') if turn['addressee'] else 'everyone'} [{turn['act']}]: "
             f"\"{turn['line']}\"" for turn in scene["turns"]]
    said = "\n".join(lines) if lines else "No one has spoken yet: the speaker opens the conversation."
    return (f"THE SCENE\n\nLine {scene['turn'] + 1} of a conversation about {scene['topic']}.\n"
            f"Present besides the speaker:\n" + "\n".join(present) + f"\n\nLines so far, oldest first:\n{said}")


def _earlier(scenes: Sequence[Mapping[str, Any]]) -> str:
    # What the speaker already said and heard in other conversations tonight; the style rules say
    # not to greet those people again or repeat a subject. Empty when nothing was heard.
    if not scenes:
        return ""
    blocks = [f"With {', '.join(scene['with']) or 'no one who answered'}:\n" +
              "\n".join(f"- {line['speaker']}: \"{line['line']}\"" for line in scene["lines"]) for scene in scenes]
    return "EARLIER TONIGHT\n\nOther conversations you were in, oldest first.\n" + "\n".join(blocks)


def _seen(memories: Sequence[str]) -> str:
    # What the speaker did and what befell them tonight, so a line can follow from it; empty when nothing did.
    if not memories:
        return ""
    return "WHAT THE SPEAKER DID AND SAW TONIGHT\n\nOldest first.\n" + "\n".join(f"- {item}" for item in memories)


def _self(me: Mapping[str, Any]) -> str:
    needs = ", ".join(f"{label} {me['needs'][key]:.0f}" for key, label in _NEEDS)
    places = ", ".join(f"{item['name']} ({item['kind']})" for item in me["places"]) or \
        "none, so the speaker cannot use share_place"
    goal = me["card"]["goal"] if me["card"] else "to rest and pass a pleasant evening"
    mean = f"\nWhat you mean to do: {me['intention']}" if me.get("intention") else ""
    unwell = "\nYou feel feverish and weak tonight." if me.get("ailing") else ""
    return (f"THE SPEAKER\n\nYou are {me['name']} (id \"{me['id']}\").\nHow they feel: {me['feelings']}{unwell}\n"
            f"Drink: {speech_instruction(me['drunkenness']) or 'You are sober.'} "
            f"Beers tonight: {me['visit']['beers']}.\n"
            f"Needs (0 calm, 100 desperate; 75 or more presses hard): {needs}.\n"
            f"Places you know: {places}.\nYour goal tonight: {goal}{mean}")


def _news(me: Mapping[str, Any]) -> str:
    # The speaker's own copies, in the words they heard, never the original; how sure they are is in words.
    # A hand-made view without the field carries no news, as with `earlier`.
    if not me.get("news"):
        return ("NEWS THE SPEAKER CARRIES\n\nNone, so the speaker cannot use share_news and talks about "
                "themselves, the road or the room.")
    items = [f'- id "{item["id"]}", {item["topic"]}: "{item["told_as"]}" ('
             f'{"you knew it before tonight" if item["heard_from"] is None else "heard from " + item["heard_from"]}; '
             f'{next(words for floor, words in _BELIEF if item["confidence"] >= floor)})' for item in me["news"]]
    return "NEWS THE SPEAKER CARRIES\n\nYour version of each, as you heard it:\n" + "\n".join(items)


def turn_question(view: Mapping[str, Any]) -> Question:
    """Ask for the next line: shared instructions, then the speaker's card, then the moment.

    Args:
        view: Scene view of `turns.turn_view`; its `acts` give the act rules and the schema.

    Returns:
        A question whose first system block is the same for every turn and whose second is the
        same for every turn of one speaker, each closed by a cache breakpoint.
    """
    # Every act is explained and allowed by the schema, so neither changes from turn to turn;
    # `check_turn` then holds the answer to what is offered now.
    acts = {name: act.meaning for name, act in ACTS.items()}
    return Question(system=[shared_prefix(acts), card_block(view["speaker"])],
                    content=turn_content(view), schema=turn_schema(acts, tuple(KINDS)), max_tokens=MAX_TOKENS)


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
        # The schema always asks for an invitation and a fact; null means none, as for every act but
        # invite and share_news.
        given = ({key: value for key, value in answer.items() if key not in ("invitation", "fact_id") or value is not None}
                 if isinstance(answer, Mapping) else answer)
        result = check_turn(view, given)
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


def writer_mode(requested: str | None, keyed: bool) -> tuple[str, str | None]:
    """Choose who writes conversation lines.

    Args:
        requested: `haiku`, `scripted`, or None for Haiku when it can be asked.
        keyed: Whether Claude can be asked: a key is configured, or a replay has recorded turns.

    Returns:
        The writer's label, and a note for the output when the default fell back to scripted lines.

    Raises:
        ValueError: The writer is unknown, or Haiku was asked for without a key.
    """
    if requested is None:
        return ("haiku", None) if keyed else (
            "scripted", "No ANTHROPIC_API_KEY (or no recorded turns), so the labeled scripted writer speaks")
    if requested not in ("haiku", "scripted"):
        raise ValueError(f"Unknown turn writer {requested!r}; choose haiku or scripted")
    if requested == "haiku" and not keyed:
        raise ValueError("The Haiku writer needs ANTHROPIC_API_KEY (or recorded turns in a replay)")
    return requested, None
