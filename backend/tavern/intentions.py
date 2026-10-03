"""Intentions: when a guest's mind takes stock, what it is asked, and the thought and intention it keeps.

The mind layer writes, per guest, one first-person `thought` about how they read the situation and
one `intention` for what they want to do next. Jev reads the intention in the briefing and weighs
its options against it. A guest takes stock on arrival, after a salient event (an interrupt or an
alert, a quarrel, insult or taken seat, a scene ending, closing time) and every `interval` seconds.
Runners ask asynchronously, like decisions: one request per guest at a time, at least `min_gap`
seconds apart; a salient event after the request makes its answer stale (`stale_intentions`).
"""

from collections.abc import Awaitable, Callable, Container, Mapping
from copy import deepcopy
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, TypedDict

from tavern.briefing import brief
from tavern.cards import PARAMS, TEXT_FIELDS
from tavern.drunkenness import drunk_stage
from tavern.questions import Ask, Question
from tavern.memory import log_event
from tavern.state import find_actor
from tavern.thoughts import THOUGHTS, active_thoughts
from tavern.world import observe_actor, observe_people


class Trigger(TypedDict):
    """What made a guest take stock: its kind, the event in words, and its game time."""

    kind: str
    text: str
    time: float


class Intention(TypedDict):
    """A guest's current mind: a first-person thought, what they intend next, when it was asked
    (the game time whose situation it answers), and what prompted it."""

    thought: str
    intention: str
    written_at: float
    trigger: Trigger


class Written(TypedDict):
    """The mind's validated answer."""

    thought: str
    intention: str


@dataclass(frozen=True)
class IntentionRules:
    """How often a guest takes stock, in game seconds.

    `interval`: without salient events, a guest takes stock again this long after the last time;
    a failed request also waits this long before it is asked again. `min_gap`: least time between
    two requests of one guest, so a burst of events costs one call.
    """

    interval: float
    min_gap: float

    def __post_init__(self) -> None:
        if not 0 < self.interval < math.inf:
            raise ValueError(f"Intention interval must be a positive number of seconds, not {self.interval!r}")
        if not 0 <= self.min_gap < math.inf:
            raise ValueError(f"Intention gap must be a nonnegative number of seconds, not {self.min_gap!r}")


# Every three minutes of game time: twice or three times in a seven-minute evening.
INTENTION_RULES = IntentionRules(interval=180.0, min_gap=3.0)

# Remembered events that make a guest take stock, by trigger kind.
SALIENT_EVENTS: Mapping[str, str] = MappingProxyType({
    "interrupted": "interrupted", "alerted": "alerted", "conversation": "scene_end", "left_conversation": "scene_end"})
# Thought kinds that make a guest take stock; `insult` counts once a speech act gives that thought.
SALIENT_THOUGHTS = ("quarrel", "seat_taken", "insult")
_LONGEST = 400

# Writes a guest's thought and intention from their view (see `intention_view`); raises on failure.
Intender = Callable[[Mapping[str, Any]], Awaitable[Written]]


def latest_trigger(world: Mapping[str, Any], actor: Mapping[str, Any], since: float) -> Trigger | None:
    """Find the newest salient event a guest met after a game time.

    Args:
        world: Current world with `time` and `closes_at`.
        actor: Guest with `memory` and `thoughts`.
        since: Game time; only later events count.

    Returns:
        The newest salient thought, closing call or remembered event, or None. On a tie a thought
        wins over the closing call, and that over a remembered event: it says most about why.
    """
    found = [Trigger(kind=item["kind"], text=item["text"], time=item["expires_at"] - THOUGHTS[item["kind"]].seconds)
             for item in actor["thoughts"] if item["kind"] in SALIENT_THOUGHTS and item["kind"] in THOUGHTS]
    if world["closes_at"] is not None and world["closes_at"] <= world["time"]:
        found.append(Trigger(kind="closing", text="The innkeeper called closing time", time=world["closes_at"]))
    found += [Trigger(kind=SALIENT_EVENTS[item["type"]], text=item["message"], time=item["time"])
              for item in actor["memory"] if item["type"] in SALIENT_EVENTS]
    # A thought's time is derived from its expiry and may carry float error; a tick is far longer.
    return max((item for item in found if item["time"] > since + 1e-6), key=lambda item: item["time"], default=None)


def intention_due(world: Mapping[str, Any], actor: Mapping[str, Any], rules: IntentionRules) -> Trigger | None:
    """Tell whether a guest should take stock now, and why.

    Args:
        world: Current world.
        actor: Guest in it.
        rules: Interval rule.

    Returns:
        `arrival` for a guest without an intention; else the newest salient event since their
        intention was asked; else `interval` once `rules.interval` has passed; else None.
    """
    now, current = world["time"], actor["intention"]
    if current is None:
        return Trigger(kind="arrival", text=f"{actor['name']} has just come in", time=now)
    salient = latest_trigger(world, actor, current["written_at"])
    if salient is not None:
        return salient
    if now - current["written_at"] >= rules.interval:
        return Trigger(kind="interval", text="A few minutes have passed since they last took stock", time=now)
    return None


def intention_requests(world: Mapping[str, Any], pending: Container[str], next_allowed: Mapping[str, float],
                       rules: IntentionRules) -> list[tuple[str, dict[str, Any]]]:
    """List the guests whose mind should be asked now, with what it is shown.

    Args:
        world: Current world; building a view refreshes the guest's knowledge, as decisions do.
        pending: Guests already waiting for an answer: one request per guest at a time.
        next_allowed: Earliest game time each guest may be asked again; absent means at once.
        rules: Interval rule.

    Returns:
        (actor ID, view) pairs in actor order.
    """
    requests = []
    for actor in world["actors"]:
        if actor["id"] in pending or world["time"] < next_allowed.get(actor["id"], 0.0):
            continue
        trigger = intention_due(world, actor, rules)
        if trigger is not None:
            requests.append((actor["id"], intention_view(world, actor, trigger)))
    return requests


def stale_intentions(world: Mapping[str, Any], asked_at: Mapping[str, float]) -> list[str]:
    """List pending requests whose answer no longer fits.

    Args:
        world: Current world.
        asked_at: Game time each pending request was made, per guest.

    Returns:
        Guests, in `asked_at` order, who left or met a salient event after asking; their answer
        is dropped and they are asked anew. The interval alone never makes a request stale.
    """
    present = {actor["id"]: actor for actor in world["actors"]}
    return [actor_id for actor_id, asked in asked_at.items()
            if actor_id not in present or latest_trigger(world, present[actor_id], asked) is not None]


def intention_view(world: Mapping[str, Any], actor: Mapping[str, Any], trigger: Trigger) -> dict[str, Any]:
    """Describe what a guest's mind is shown when it takes stock.

    Args:
        world: Current world; the guest's knowledge is refreshed.
        actor: Guest in it.
        trigger: Why they take stock.

    Returns:
        `actor_id`, `name`, `time`, `trigger`, `previous` intention (or None), `card` in words,
        `situation` (the briefing paragraph, without the previous intention), active `thoughts`
        and `drink` (drunkenness stage).
    """
    observation = {**observe_actor(world, actor["id"]), "people": observe_people(world, actor["id"])}
    # The previous intention is shown on its own, so the situation leaves it out.
    observation["actor"]["intention"] = None
    return {"actor_id": actor["id"], "name": actor["name"], "time": world["time"], "trigger": dict(trigger),
            "previous": deepcopy(actor["intention"]), "card": _card(actor),
            "situation": brief(observation, [])["situation"],
            "thoughts": [item["text"] for item in active_thoughts(actor["thoughts"], world["time"])],
            "drink": drunk_stage(actor["drunkenness"]).name}


def _card(actor: Mapping[str, Any]) -> str:
    card = actor["card"]
    if card is None:
        return f"The guest: {actor['name']}. They have no character card; judge them from the situation alone."
    words = "\n".join(f"{field}: {card[field]}" for field in TEXT_FIELDS)
    params = ", ".join(f"{name} {card['params'][name]}" for name in PARAMS)
    return f"The guest's character card.\n{words}\nTraits from 0 to 1 (0.5 is ordinary): {params}."


def _previous(view: Mapping[str, Any]) -> str:
    previous = view["previous"]
    if previous is None:
        return "Their previous thought and intention: none yet."
    return (f"Their previous thought: \"{previous['thought']}\" Their previous intention: \"{previous['intention']}\" "
            f"(decided at {previous['written_at']:.0f} s, after: {previous['trigger']['text']}).")


def intention_question(prefix: str, view: Mapping[str, Any]) -> Question:
    """Ask the mind for a guest's thought and intention.

    Args:
        prefix: Shared system prefix, the same for every guest (world notes, rules, examples); it
            should exceed the model's minimum cacheable length.
        view: The guest's view (see `intention_view`).

    Returns:
        The question: the prefix, then the guest's card as its own cached block, then the moment.

    Raises:
        ValueError: The prefix is blank.
    """
    if not prefix.strip():
        raise ValueError("An intention question needs a shared prefix")
    thoughts = "; ".join(view["thoughts"]) or "none"
    content = "\n".join([
        f"It is {view['time']:.0f} s into the evening. {view['name']} takes stock now.",
        f"What prompted it: {view['trigger']['text']}.", _previous(view),
        f"The situation as they see it: {view['situation']}",
        f"Thoughts on their mind: {thoughts}.", f"Drink: they are {view['drink']}.",
        f"Write {view['name']}'s thought and intention."])
    return Question(system=[prefix, view["card"]], content=content, schema=_schema(), max_tokens=250)


def _schema() -> dict[str, Any]:
    text = {"type": "string"}
    return {"type": "object", "properties": {
        "thought": {**text, "description": "One first-person sentence: how they read the situation now."},
        "intention": {**text, "description": "One sentence: what they want to do next."}},
        "required": ["thought", "intention"], "additionalProperties": False}


def check_intention(answer: Any) -> Written:
    """Validate the mind's answer.

    Args:
        answer: Decoded answer.

    Returns:
        The thought and intention.

    Raises:
        ValueError: It is not exactly a thought and an intention, each nonempty text of at most
            400 characters.
    """
    if not isinstance(answer, Mapping) or set(answer) != {"thought", "intention"}:
        raise ValueError(f"An intention has exactly a thought and an intention, not {answer!r}")
    for key in ("thought", "intention"):
        if not isinstance(answer[key], str) or not answer[key].strip() or len(answer[key]) > _LONGEST:
            raise ValueError(f"An intention's {key} must be nonempty text of at most {_LONGEST} characters")
    return Written(thought=answer["thought"], intention=answer["intention"])


def intention_writer(prefix: str, ask: Ask) -> Intender:
    """Bind the mind-layer port into a writer of intentions.

    Args:
        prefix: Shared system prefix (see `intention_question`).
        ask: Model port, e.g. Claude Haiku through `claude.ask_claude`, recorded or replayed.

    Returns:
        A writer that asks the port and validates the answer; it raises what the port raises,
        or ValueError for an invalid answer.
    """
    async def write(view: Mapping[str, Any]) -> Written:
        return check_intention(await ask(intention_question(prefix, view)))
    return write


def deliver_intention(world: dict[str, Any], actor_id: str, view: Mapping[str, Any],
                      outcome: Callable[[], Any], rules: IntentionRules) -> float:
    """Keep a written intention, or log why there is none.

    Args:
        world: Authoritative world; the guest's `intention` and the event log are updated.
        actor_id: Guest the view was for.
        view: The view the writer was given.
        outcome: Returns the answer, or raises the writer's error, like an asyncio task's `result`.
        rules: Gap and interval rules.

    Returns:
        The earliest game time the guest may be asked again: `min_gap` after an answer, `interval`
        after a failure (the old intention stays). An answer for a guest who left is dropped.
    """
    try:
        answer, failure = outcome(), None
    except Exception as error:  # Any writer failure leaves the old intention, as a failed decision does.
        answer, failure = None, error
    actor = find_actor(world, actor_id)
    if actor is None:
        return world["time"] + rules.min_gap
    try:
        if failure is not None:
            raise failure
        written = check_intention(answer)
    except Exception as error:
        log_event(world, actor_id, "intention_failed", f"{actor['name']}'s intention could not be written ({error})")
        return world["time"] + rules.interval
    actor["intention"] = Intention(thought=written["thought"], intention=written["intention"],
                                   written_at=view["time"], trigger=deepcopy(view["trigger"]))
    log_event(world, actor_id, "intention", f"{actor['name']} thinks: {written['thought']} Intends: "
                                       f"{written['intention']} (after: {view['trigger']['text']})")
    return world["time"] + rules.min_gap


def check_saved_intention(actor: Mapping[str, Any]) -> None:
    """Check a saved guest's intention.

    Args:
        actor: Untrusted saved guest record.

    Raises:
        ValueError: The intention is missing or malformed.
    """
    intention = actor["intention"]
    if intention is None:
        return
    if not isinstance(intention, dict) or set(intention) != set(Intention.__annotations__):
        raise ValueError(f"Invalid saved intention {intention!r}")
    check_intention({"thought": intention["thought"], "intention": intention["intention"]})
    trigger = intention["trigger"]
    if not isinstance(trigger, dict) or set(trigger) != set(Trigger.__annotations__) or not all(
            isinstance(trigger[key], str) for key in ("kind", "text")):
        raise ValueError(f"Invalid saved intention trigger {trigger!r}")
    for value in (intention["written_at"], trigger["time"]):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < math.inf:
            raise ValueError(f"Invalid saved intention time {value!r}")

