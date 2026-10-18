"""Intentions: when a guest's mind takes stock, what it is asked, and the thought and intention it keeps.

The mind layer writes, per guest, one first-person `thought` about how they read the situation and
one `intention` for what they want to do next. Jev reads the intention in the briefing and weighs
its options against it. A guest takes stock on arrival, after a salient event (an interrupt or an
alert, a wrong done to them, a game's result, a goal's end, the barkeep's call, closing time) and every `interval` seconds, at
most `budget` times after arrival.
Runners ask asynchronously, like decisions: one request per guest at a time, at least `min_gap`
seconds apart; a salient event after the request makes its answer stale (`stale_intentions`).
"""

from collections.abc import Callable, Collection, Container, Coroutine, Mapping
from copy import deepcopy
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, NotRequired, TypedDict

from tavern.body.dozing import asleep
from tavern.body.drunkenness import drunk_stage
from tavern.hall.closing import closing_called
from tavern.hall.memory import log_event
from tavern.hall.staff import on_staff, post_of
from tavern.hall.state import World, find_actor
from tavern.hall.world import observe_actor, observe_people
from tavern.mind.briefing import brief
from tavern.mind.cards import PARAMS, TEXT_FIELDS, persona_words
from tavern.mind.goals import GOALS, STATUSES, Goal, check_goal, goal_words, open_alone, open_kinds
from tavern.mind.questions import Ask, Question
from tavern.social.heard import earlier_lines
from tavern.social.names import called
from tavern.social.scenes import conversation_of
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
    and what prompted it. `obsession` is the index into the card's obsessions that the intention serves;
    absent when it serves none (and in saves written before it existed)."""

    thought: str
    intention: str
    goal: Goal | None
    written_at: float
    trigger: Trigger
    obsession: NotRequired[int]


class Written(TypedDict):
    """The mind's validated answer; a `goal` it leaves out is none, and an `obsession` it leaves out serves none."""

    thought: str
    intention: str
    goal: NotRequired[Goal | None]
    obsession: NotRequired[int]


@dataclass(frozen=True)
class IntentionRules:
    """How often a guest takes stock, in game seconds.

    `interval`: without salient events, a guest takes stock again this long after the last time;
    a failed request also waits this long before it is asked again. `min_gap`: least time between
    two requests of one guest, so a burst of events costs one call. `budget`: most requests per guest
    after arrival, apart from closing time, or None for no limit. `talk_lines`: lines of the guest's current
    scene since they last took stock after which they take stock again, so a long talk changes their mind.
    """

    interval: float
    min_gap: float
    budget: int | None = None
    talk_lines: int = 5

    def __post_init__(self) -> None:
        if not 0 < self.interval < math.inf:
            raise ValueError(f"Intention interval must be a positive number of seconds, not {self.interval!r}")
        if not 0 <= self.min_gap < math.inf:
            raise ValueError(f"Intention gap must be a nonnegative number of seconds, not {self.min_gap!r}")
        if self.budget is not None and (isinstance(self.budget, bool) or self.budget < 0):
            raise ValueError(f"Intention budget must be a nonnegative number of requests or None, not {self.budget!r}")
        if isinstance(self.talk_lines, bool) or not isinstance(self.talk_lines, int) or self.talk_lines < 1:
            raise ValueError(f"Lines of talk before taking stock must be a positive whole number, not {self.talk_lines!r}")


# Every three minutes of game time: twice or three times in a ten-minute evening.
# Each guest's mind is asked at most eight more times after arrival: the evening's turning points and a rethink every
# five lines of a long talk, not every line.
INTENTION_RULES = IntentionRules(interval=180.0, min_gap=3.0, budget=8, talk_lines=5)
# Triggers the budget never withholds: a guest always plans on arriving, at the barkeep's call and when the inn closes.
UNMETERED = ("arrival", "last_call", "closing")

# Remembered events that make a guest take stock, by trigger kind.
# A scene's end alone is not one: what a talk changed is told by a goal reached, a thought or a fact.
SALIENT_EVENTS: Mapping[str, str] = MappingProxyType({
    "interrupted": "interrupted", "woken": "woken", "alerted": "alerted", "dice_won": "dice", "dice_lost": "dice", "goal_done": "goal", "goal_failed": "goal", "goal_expired": "goal",
    "saw_fight": "fight", "fight_ended": "fight"})
# Thought kinds that make a guest take stock: a wrong done to them.
SALIENT_THOUGHTS = ("quarrel", "seat_taken", "table_intruded", "insulted", "shoved", "attacked", "lost_fight",
                    "knocked_out_by")
# Of those, the ones words alone cause: about someone in the guest's current scene they are part of the talk, weighed
# once a stretch of it has passed (`IntentionRules.talk_lines`), not line by line, which would spend the guest's
# budget in the first minute of a quarrel.
SPOKEN_THOUGHTS = ("quarrel", "insulted")
_LONGEST = 400
# What the log of an intention that serves an obsession carries inside its "(after: …)", then the obsession: the
# intention's words must still end in the parenthesis (`evening.repetition` reads them).
CHASING = "; chasing: "
_ANSWER_FIELDS = {"thought", "intention", "goal", "obsession"}

# Writes a guest's thought and intention from their view (see `intention_view`); raises on failure.
Intender = Callable[[Mapping[str, Any]], Coroutine[Any, Any, Written]]


def latest_trigger(world: Mapping[str, Any], actor: Mapping[str, Any], since: float) -> Trigger | None:
    """Find the newest salient event a guest met after a game time.

    Args:
        world: Current world with `time`, `last_call_at` and `closes_at`.
        actor: Guest with `memory` and `thoughts`.
        since: Game time; only later events count.

    Returns:
        The newest salient thought (but not one words caused about someone in their current scene, see
        `SPOKEN_THOUGHTS`), the barkeep's call, closing time or remembered event, or None. On a tie a
        thought wins over the call and the close, and those over a remembered event: it says most about why.
    """
    scene = conversation_of(world, actor["id"])
    talking_with = set(scene["participants"]) if scene else set()
    found = [Trigger(kind=item["kind"], text=item["text"], time=item["expires_at"] - THOUGHTS[item["kind"]].seconds)
             for item in actor["thoughts"] if item["kind"] in SALIENT_THOUGHTS and item["kind"] in THOUGHTS
             and not (item["kind"] in SPOKEN_THOUGHTS and item["about"] in talking_with)]
    if closing_called(world):
        found.append(Trigger(kind="last_call", text="The barkeep called closing time", time=world["last_call_at"]))
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
        None for a guest asleep; else `arrival` for a guest without an intention; else the newest salient event since their
        intention was asked; else `talk` once `rules.talk_lines` lines of their current scene have been said since;
        else `interval` once `rules.interval` has passed; else None.
    """
    now, current = world["time"], actor["intention"]
    if asleep(actor):
        return None
    if current is None:
        return Trigger(kind="arrival", text=f"{actor['name']} has just come in", time=now)
    salient = latest_trigger(world, actor, current["written_at"]) or _talked(world, actor, current["written_at"],
                                                                               rules.talk_lines)
    if salient is not None:
        return salient
    if now - current["written_at"] >= rules.interval:
        return Trigger(kind="interval", text="A few minutes have passed since they last took stock", time=now)
    return None


def _talked(world: Mapping[str, Any], actor: Mapping[str, Any], since: float, lines: int) -> Trigger | None:
    # A stretch of talk in their current scene since they last took stock: what was said may have changed their mind.
    scene = conversation_of(world, actor["id"])
    if scene is None:
        return None
    spoken = [turn for turn in scene["turns"] if turn["time"] > since]
    if len(spoken) < lines:
        return None
    people = {item["id"]: item for item in world["actors"]}
    others = ", ".join(called(actor, people[key]) for key in scene["participants"] if key != actor["id"] and key in people)
    return Trigger(kind="talk", text=f"{actor['name']} has talked a while with {others} "
                                     f"({len(spoken)} lines since they last took stock)", time=world["time"])


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
        `obsessions` (the card's obsessions, in order; empty without a card or persona), `duty` (the bar they work at, or None for a guest), `others` (the guests in the hall as this guest calls them: ID to name, for a goal), `possible` (the goal kinds the hall can carry out for each of them now), `alone` (those about no one it can carry out), `earlier`
        (the latest 8 lines they said or heard tonight, see `heard.earlier_lines`) and `drink`
        (drunkenness stage).
    """
    observation = {**observe_actor(world, actor["id"]), "people": observe_people(world, actor["id"])}
    # The previous intention is shown on its own, so the situation leaves it out.
    observation["actor"]["intention"] = None
    return {"actor_id": actor["id"], "name": actor["name"], "time": world["time"], "trigger": dict(trigger),
            "previous": deepcopy(actor["intention"]), "card": _card(actor), "obsessions": _obsessions(actor),
            "possible": {item["id"]: open_kinds(world, actor, item) for item in world["actors"] if item["id"] != actor["id"]},
            "alone": open_alone(world, actor),
            "situation": brief(observation, [])["situation"],
            "duty": post_of(world["map"], actor)["name"] if on_staff(actor) else None,
            "others": {item["id"]: called(actor, item) for item in world["actors"] if item["id"] != actor["id"]},
            "thoughts": [item["text"] for item in active_thoughts(actor["thoughts"], world["time"])],
            "earlier": earlier_lines(actor, RECALLED_LINES),
            "drink": drunk_stage(actor["drunkenness"]).name}


def _card(actor: Mapping[str, Any]) -> str:
    card = actor["card"]
    if card is None:
        return f"The guest: {actor['name']}. They have no character card; judge them from the situation alone."
    words = "\n".join([*(f"{field}: {card[field]}" for field in TEXT_FIELDS),
                       *(f"{label}: {text}" for label, text in persona_words(card).items())])
    params = ", ".join(f"{name} {card['params'][name]}" for name in PARAMS)
    return f"The guest's character card.\n{words}\nTraits from 0 to 1 (0.5 is ordinary): {params}."


def _obsessions(actor: Mapping[str, Any]) -> list[str]:
    card = actor["card"]
    return list(card.get("obsessions", [])) if card else []


def _wishes(view: Mapping[str, Any]) -> list[str]:
    # Their obsessions by number, so the answer can name the one this intention serves.
    if not view["obsessions"]:
        return []
    numbered = "; ".join(f"{index}: {text}" for index, text in enumerate(view["obsessions"]))
    return [f"Their obsessions tonight, by number: {numbered}. Name the number of the one this intention serves, "
            "or null when it serves none."]


def _previous(view: Mapping[str, Any]) -> str:
    previous = view["previous"]
    if previous is None:
        return "Their previous thought and intention: none yet."
    goal = previous.get("goal")
    aim = "" if goal is None else (f" Their previous goal: {goal_words(goal, view['others'].get(goal['target']))} "
                                   f"({goal['status']}).")
    return (f"Their previous thought: \"{previous['thought']}\" Their previous intention: \"{previous['intention']}\" "
            f"(decided at {previous['written_at']:.0f} s, after: {previous['trigger']['text']}).{aim}")


def _duty(view: Mapping[str, Any]) -> list[str]:
    # Someone at work stays at their post: their thought, intention and goal are about the work and the people
    # who come to the bar, never games, money or leaving it.
    if view["duty"] is None:
        return []
    return [f"{view['name']} is on duty behind the {view['duty']} all evening. What they want must be what a "
            "barkeep wants: pouring, keeping the peace, hearing the news from those who lean on the bar. Never "
            "games, wagers or money, and never leaving the bar."]


def _others(view: Mapping[str, Any]) -> str:
    # Each guest with the goal kinds the hall can carry out for them now: the same list `parse_stance` checks against.
    people = "; ".join(f"{name} (id \"{key}\"; goals open: {', '.join(view['possible'][key]) or 'none'})"
                       for key, name in view["others"].items()) or "no one"
    return (f"Guests they could set a goal about: {people}. Goal kinds: "
            + "; ".join(f"{kind} = {goal_words({'kind': kind, 'target': None, 'status': 'active'}, 'that guest')}"
                        for kind in GOALS) + f". Goals about no one (target null) open now: {', '.join(view['alone']) or 'none'}.")


def _earlier(view: Mapping[str, Any]) -> list[str]:
    # The latest lines they said or heard tonight, so their mind builds on talk it already had.
    lines = [f"{line['speaker']}: \"{line['line']}\"" for scene in view["earlier"] for line in scene["lines"]]
    return [f"What they said and heard lately, oldest first: {' / '.join(lines)}."] if lines else []


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
        f"Thoughts on their mind: {thoughts}.", *_earlier(view), f"Drink: they are {view['drink']}.", *_duty(view),
        *_wishes(view), _others(view),
        f"Write {view['name']}'s thought, intention and goal."])
    return Question(system=[prefix, view["card"]], content=content, schema=_schema(), max_tokens=250)


def _schema() -> dict[str, Any]:
    text = {"type": "string"}
    # The goal's kinds and people are checked at the boundary (`parse_stance`), so the schema is the same
    # for every guest and moment and stays cacheable.
    return {"type": "object", "properties": {
        "thought": {**text, "description": "One first-person sentence: how they read the situation now."},
        "intention": {**text, "description": "One sentence: what they want to do next."},
        "goal": {**text, "description": "A goal kind, or none when they set out to do nothing in particular."},
        "target": {"anyOf": [text, {"type": "null"}],
                   "description": "The ID of the guest the goal is about, or null when the goal is none."},
        # Not required: a guest without obsessions has none to name (checked against the card at the boundary).
        "obsession": {"anyOf": [{"type": "integer"}, {"type": "null"}],
                      "description": "The number of the obsession this intention serves, or null."}},
        "required": ["thought", "intention", "goal", "target"], "additionalProperties": False}


def check_intention(answer: Any, obsessions: int = 0) -> Written:
    """Validate the mind's answer.

    Args:
        answer: Decoded answer.
        obsessions: How many obsessions the guest's card lists; an `obsession` index must be below it.

    Returns:
        The thought and intention, with the goal and the obsession index when the answer names them.

    Raises:
        ValueError: It is not a thought and an intention, each nonempty text of at most 400 characters, with at
            most a valid goal and an obsession that is null or an index into the card's list.
    """
    if not isinstance(answer, Mapping) or not {"thought", "intention"} <= set(answer) <= _ANSWER_FIELDS:
        raise ValueError(f"An intention has a thought, an intention and perhaps a goal and an obsession, not {answer!r}")
    for key in ("thought", "intention"):
        if not isinstance(answer[key], str) or not answer[key].strip() or len(answer[key]) > _LONGEST:
            raise ValueError(f"An intention's {key} must be nonempty text of at most {_LONGEST} characters")
    goal = answer.get("goal")
    if goal is not None and not _is_goal(goal):
        raise ValueError(f"Invalid intention goal {goal!r}")
    written = Written(thought=answer["thought"], intention=answer["intention"])
    if goal is not None:
        written["goal"] = goal
    obsession = answer.get("obsession")
    if obsession is not None:
        if isinstance(obsession, bool) or not isinstance(obsession, int) or not 0 <= obsession < obsessions:
            raise ValueError(f"Obsession {obsession!r} is not one of the card's {obsessions} obsessions")
        written["obsession"] = obsession
    return written


def _is_goal(goal: Any) -> bool:
    return (isinstance(goal, dict) and set(goal) == {"kind", "target", "status"} and goal["kind"] in GOALS
            and (isinstance(goal["target"], str) or (goal["target"] is None and not GOALS[goal["kind"]].person))
            and goal["status"] in STATUSES)


def parse_stance(answer: Any, others: Mapping[str, str], on_duty: bool = False, obsessions: int = 0,
                 possible: Mapping[str, Collection[str]] | None = None, alone: Collection[str] | None = None) -> Written:
    """Check what the mind answered at the boundary.

    Args:
        answer: Decoded answer: a thought, an intention, a goal kind (or "none") and its person's ID.
        others: Guests in the hall besides the one asking: ID to name (`intention_view`).
        on_duty: Whether the one asking works behind a bar (`intention_view`'s `duty`).
        obsessions: How many obsessions the guest's card lists (`len(intention_view["obsessions"])`).
        possible: For each guest, the goal kinds the hall can carry out now (`intention_view`'s `possible`); None
            asks nothing of the hall.

    Returns:
        The thought, the intention, the goal they name, active, or none, and the obsession they serve.

    Raises:
        ValueError: The answer is not those four fields, with at most an `obsession`; a text is blank or over 400
            characters, the obsession is not an index into the card's list, the goal kind is not in `GOALS` or not open to someone on duty, its person is not in the hall, or the
            hall cannot carry it out for that person now.
    """
    if not isinstance(answer, Mapping) or set(answer) - {"obsession"} != {"thought", "intention", "goal", "target"}:
        raise ValueError(f"An answer has a thought, an intention, a goal and a target, not {answer!r}")
    kind = answer["goal"]
    if not isinstance(kind, str) or not (answer["target"] is None or isinstance(answer["target"], str)):
        raise ValueError(f"A goal is a kind and the ID of a guest, not {kind!r} and {answer['target']!r}")
    goal = check_goal(None if kind == "none" else kind, answer["target"], others, on_duty, possible, alone)
    return check_intention({"thought": answer["thought"], "intention": answer["intention"], "goal": goal,
                            "obsession": answer.get("obsession")}, obsessions)


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
        return parse_stance(await ask(intention_question(prefix, view)), view["others"], view["duty"] is not None,
                            len(view["obsessions"]), view["possible"], view["alone"])
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
        written = check_intention(answer, len(view["obsessions"]))
    except Exception as error:
        log_event(world, actor_id, "intention_failed", f"{actor['name']}'s intention could not be written ({error})")
        return world["time"] + rules.interval
    previous = actor["intention"]
    goal = _pursued(previous, written)
    kept = previous is not None and goal is not None and goal is previous.get("goal")
    intention = Intention(thought=written["thought"], intention=written["intention"], goal=goal,
                          written_at=view["time"], trigger=deepcopy(view["trigger"]))
    if "obsession" in written:
        intention["obsession"] = written["obsession"]
    actor["intention"] = intention
    chasing = f"{CHASING}{view['obsessions'][written['obsession']]}" if "obsession" in written else ""
    log_event(world, actor_id, "intention", f"{actor['name']} thinks: {written['thought']} Intends: "
                                       f"{written['intention']} (after: {view['trigger']['text']}{chasing})")
    if goal is not None and not kept:
        log_event(world, actor_id, "goal_set", f"{actor['name']} set out to {goal_words(goal, view['others'].get(goal['target']))}")
    return world["time"] + rules.min_gap


def _pursued(previous: Intention | None, written: Written) -> Goal | None:
    # A goal not yet reached is kept while the mind goes on naming the obsession it was set for: a guest chases an
    # obsession until the world ends the goal, not until the next time the mind takes stock.
    if previous is not None:
        old = previous.get("goal")
        if (old is not None and old["status"] == "active" and previous.get("obsession") is not None
                and written.get("obsession") == previous["obsession"]):
            return old
    return written.get("goal")


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
    if not isinstance(intention, dict) or set(intention) - {"obsession"} != Intention.__required_keys__:
        raise ValueError(f"Invalid saved intention {intention!r}")
    card = actor["card"]
    check_intention({"thought": intention["thought"], "intention": intention["intention"], "goal": intention["goal"],
                     "obsession": intention.get("obsession")}, len(card.get("obsessions", [])) if card else 0)
    trigger = intention["trigger"]
    if not isinstance(trigger, dict) or set(trigger) != set(Trigger.__annotations__) or not all(
            isinstance(trigger[key], str) for key in ("kind", "text")):
        raise ValueError(f"Invalid saved intention trigger {trigger!r}")
    for value in (intention["written_at"], trigger["time"]):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < math.inf:
            raise ValueError(f"Invalid saved intention time {value!r}")

