"""Intentions: when a guest's mind takes stock, what it is shown, and the thought and intention it keeps.

The mind layer writes, per guest, one first-person `thought` about how they read the situation and
one `intention` for what they want to do next. Jev reads the intention in the briefing and weighs
its options against it. A guest takes stock on arrival, after a salient event (an interrupt or an
alert, a wrong done to them, a game's result, a goal's end, closing time) and every `interval` seconds, at
most `budget` times after arrival.
Runners ask asynchronously, like decisions: one request per guest at a time, at least `min_gap`
seconds apart; a salient event after the request makes its answer stale (`stale_intentions`).
"""

from collections.abc import Callable, Container, Coroutine, Mapping
from copy import deepcopy
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, NotRequired, TypedDict

from tavern.body.drunkenness import drunk_stage
from tavern.hall.memory import log_event
from tavern.hall.staff import on_staff, post_of
from tavern.hall.state import World, find_actor
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.briefing import brief
from tavern.mind.cards import PARAMS, TEXT_FIELDS
from tavern.mind.goals import GOALS, STATUSES, Goal, check_goal, goal_words
from tavern.mind.intention_prompt import intention_question
from tavern.mind.questions import Ask
from tavern.social.giving import drink_targets
from tavern.social.heard import earlier_lines
from tavern.social.names import called
from tavern.social.thoughts import THOUGHTS, active_thoughts


RECALLED_LINES = 8  # Lines of tonight's talk a guest's mind is shown when it takes stock.


class Trigger(TypedDict):
    """What made a guest take stock: its kind, the event in words, and its game time."""

    kind: str
    text: str
    time: float


class Intention(TypedDict):
    """A guest's current mind: a first-person thought, what they intend next in words, the goal they
    set out to do (see `goals`, or None), when it was asked (the game time whose situation it answers),
    and what prompted it."""

    thought: str
    intention: str
    goal: Goal | None
    written_at: float
    trigger: Trigger


class Written(TypedDict):
    """The mind's validated answer; a `goal` it leaves out is none."""

    thought: str
    intention: str
    goal: NotRequired[Goal | None]


@dataclass(frozen=True)
class IntentionRules:
    """How often a guest takes stock, in game seconds.

    `interval`: without salient events, a guest takes stock again this long after the last time;
    a failed request also waits this long before it is asked again. `min_gap`: least time between
    two requests of one guest, so a burst of events costs one call. `budget`: most requests per guest
    after arrival, apart from closing time, or None for no limit.
    """

    interval: float
    min_gap: float
    budget: int | None = None

    def __post_init__(self) -> None:
        if not 0 < self.interval < math.inf:
            raise ValueError(f"Intention interval must be a positive number of seconds, not {self.interval!r}")
        if not 0 <= self.min_gap < math.inf:
            raise ValueError(f"Intention gap must be a nonnegative number of seconds, not {self.min_gap!r}")
        if self.budget is not None and (isinstance(self.budget, bool) or self.budget < 0):
            raise ValueError(f"Intention budget must be a nonnegative number of requests or None, not {self.budget!r}")


# Every three minutes of game time: twice or three times in a seven-minute evening.
# Each guest's mind is asked at most four more times after arrival: the evening's turning points, not every scene.
INTENTION_RULES = IntentionRules(interval=180.0, min_gap=3.0, budget=4)
# Triggers the budget never withholds: a guest always plans on arriving and when the inn closes.
UNMETERED = ("arrival", "closing")

# Remembered events that make a guest take stock, by trigger kind.
# A scene's end alone is not one: what a talk changed is told by a goal reached, a thought or a fact.
SALIENT_EVENTS: Mapping[str, str] = MappingProxyType({
    "interrupted": "interrupted", "alerted": "alerted", "dice_won": "dice", "dice_lost": "dice", "goal_done": "goal", "goal_failed": "goal", "goal_expired": "goal"})
# Thought kinds that make a guest take stock: a wrong done to them.
SALIENT_THOUGHTS = ("quarrel", "seat_taken", "insulted", "shoved", "attacked")
_LONGEST = 400

# Writes a guest's thought and intention from their view (see `intention_view`); raises on failure.
Intender = Callable[[Mapping[str, Any]], Coroutine[Any, Any, Written]]


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
                       rules: IntentionRules, made: Mapping[str, int] | None = None) -> list[tuple[str, dict[str, Any]]]:
    """List the guests whose mind should be asked now, with what it is shown.

    Args:
        world: Current world; building a view refreshes the guest's knowledge, as decisions do.
        pending: Guests already waiting for an answer: one request per guest at a time.
        next_allowed: Earliest game time each guest may be asked again; absent means at once.
        rules: Interval rule and budget.
        made: Requests already answered per guest apart from `UNMETERED` ones; a guest who has made
            `rules.budget` of them is asked only at an unmetered trigger. None counts none.

    Returns:
        (actor ID, view) pairs in actor order.
    """
    requests = []
    for actor in world["actors"]:
        if actor["id"] in pending or world["time"] < next_allowed.get(actor["id"], 0.0):
            continue
        trigger = intention_due(world, actor, rules)
        spent = rules.budget is not None and (made or {}).get(actor["id"], 0) >= rules.budget
        if trigger is not None and not (spent and trigger["kind"] not in UNMETERED):
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
        `situation` (the briefing paragraph, without the previous intention), active `thoughts`,
        `duty` (the bar they work at, or None for a guest), `others` (the guests in the hall as this guest calls them: ID to name, for a goal),
        `fetchable` (those among them they could bring a drink, see `giving.drink_targets`), `earlier`
        (the latest 8 lines they said or heard tonight, see `heard.earlier_lines`) and `drink`
        (drunkenness stage).
    """
    observation = {**observe_actor(world, actor["id"]), "people": observe_people(world, actor["id"])}
    # The previous intention is shown on its own, so the situation leaves it out.
    observation["actor"]["intention"] = None
    return {"actor_id": actor["id"], "name": actor["name"], "time": world["time"], "trigger": dict(trigger),
            "previous": deepcopy(actor["intention"]), "card": _card(actor),
            "situation": brief(observation, [])["situation"],
            "duty": post_of(world["map"], actor)["name"] if on_staff(actor) else None,
            "others": {item["id"]: called(actor, item) for item in world["actors"] if item["id"] != actor["id"]},
            "fetchable": {item["id"]: item["name"] for item in observation["people"]
                          if item["id"] in drink_targets(observation)},
            "thoughts": [item["text"] for item in active_thoughts(actor["thoughts"], world["time"])],
            "earlier": earlier_lines(actor, RECALLED_LINES),
            "drink": drunk_stage(actor["drunkenness"]).name}


def _card(actor: Mapping[str, Any]) -> str:
    card = actor["card"]
    if card is None:
        return f"The guest: {actor['name']}. They have no character card; judge them from the situation alone."
    words = "\n".join(f"{field}: {card[field]}" for field in TEXT_FIELDS)
    params = ", ".join(f"{name} {card['params'][name]}" for name in PARAMS)
    return f"The guest's character card.\n{words}\nTraits from 0 to 1 (0.5 is ordinary): {params}."


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
    if not isinstance(answer, Mapping) or set(answer) not in ({"thought", "intention"},
                                                               {"thought", "intention", "goal"}):
        raise ValueError(f"An intention has exactly a thought, an intention and perhaps a goal, not {answer!r}")
    for key in ("thought", "intention"):
        if not isinstance(answer[key], str) or not answer[key].strip() or len(answer[key]) > _LONGEST:
            raise ValueError(f"An intention's {key} must be nonempty text of at most {_LONGEST} characters")
    goal = answer.get("goal")
    if goal is not None and not _is_goal(goal):
        raise ValueError(f"Invalid intention goal {goal!r}")
    written = Written(thought=answer["thought"], intention=answer["intention"])
    if goal is not None:
        written["goal"] = goal
    return written


def _is_goal(goal: Any) -> bool:
    return (isinstance(goal, dict) and set(goal) == {"kind", "target", "status"} and goal["kind"] in GOALS
            and isinstance(goal["target"], str) and goal["status"] in STATUSES)


def parse_stance(answer: Any, others: Mapping[str, str], on_duty: bool = False) -> Written:
    """Check what the mind answered at the boundary.

    Args:
        answer: Decoded answer: a thought, an intention, a goal kind (or "none") and its person's ID.
        others: Guests in the hall besides the one asking: ID to name (`intention_view`).
        on_duty: Whether the one asking works behind a bar (`intention_view`'s `duty`).

    Returns:
        The thought, the intention and the goal they name, active, or none.

    Raises:
        ValueError: The answer is not exactly those four fields, a text is blank or over 400 characters, the
            goal kind is not in `GOALS` or not open to someone on duty, or its person is not in the hall (so it
            cannot be carried out).
    """
    if not isinstance(answer, Mapping) or set(answer) != {"thought", "intention", "goal", "target"}:
        raise ValueError(f"An answer has exactly a thought, an intention, a goal and a target, not {answer!r}")
    kind = answer["goal"]
    if not isinstance(kind, str) or not (answer["target"] is None or isinstance(answer["target"], str)):
        raise ValueError(f"A goal is a kind and the ID of a guest, not {kind!r} and {answer['target']!r}")
    goal = check_goal(None if kind == "none" else kind, answer["target"], others, on_duty)
    return check_intention({"thought": answer["thought"], "intention": answer["intention"], "goal": goal})


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
        return parse_stance(await ask(intention_question(prefix, view)), view["others"], view["duty"] is not None)
    return write


def deliver_intention(world: World, actor_id: str, view: Mapping[str, Any],
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
                                   goal=written.get("goal"), written_at=view["time"],
                                   trigger=deepcopy(view["trigger"]))
    log_event(world, actor_id, "intention", f"{actor['name']} thinks: {written['thought']} Intends: "
                                       f"{written['intention']} (after: {view['trigger']['text']})")
    goal = written.get("goal")
    if goal is not None:
        log_event(world, actor_id, "goal_set", f"{actor['name']} set out to {goal_words(goal, view['others'][goal['target']])}",
                  goal=goal["kind"])
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
    check_intention({"thought": intention["thought"], "intention": intention["intention"], "goal": intention["goal"]})
    trigger = intention["trigger"]
    if not isinstance(trigger, dict) or set(trigger) != set(Trigger.__annotations__) or not all(
            isinstance(trigger[key], str) for key in ("kind", "text")):
        raise ValueError(f"Invalid saved intention trigger {trigger!r}")
    for value in (intention["written_at"], trigger["time"]):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < math.inf:
            raise ValueError(f"Invalid saved intention time {value!r}")

