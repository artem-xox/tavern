"""Projects: plans of several steps a guest takes on with one choice, and how each step is carried out.

A project is chosen once (`start_action` opens it) and then runs by itself: each tick, while the guest is idle,
`honor_projects` starts the next step through the ordinary action lifecycle, so the usual rules decide whether it
is possible. The guest asks for no decision until it ends: done, failed (a step was refused or came to nothing),
dropped (an interrupt called them away) or expired. Each end is one event a story can cite.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, NotRequired, TypedDict, cast

from tavern.body.actions import action_error
from tavern.body.dozing import asleep
from tavern.body.items import ITEMS
from tavern.hall.memory import record_event
from tavern.hall.staff import on_staff
from tavern.hall.state import Actor, World, find_actor
from tavern.hall.validation import number
from tavern.social.dice import PLAY, open_chairs
from tavern.social.errands import fetching_a_drink
from tavern.social.invitations import errand_parties, known_place
from tavern.social.responses import calling, mark_answered
from tavern.social.scenes import conversation_of, table_of, within_reach

# Starts an action the way `world.start_action` does: world, visitor ID, action; returns acceptance.
Start = Callable[[World, str, Mapping[str, Any]], Mapping[str, Any]]


class Project(TypedDict):
    """A plan under way: its kind, whose it is, what it is about (a chair, a table or a guest, by kind), the step reached
    out of `of`, whether that step has been started, and since when. `targets` are the guests a plan serves in turn,
    frozen when it began; only a kind that has them carries the field."""

    kind: str
    by: str
    target: str
    step: int
    of: int
    running: bool
    started_at: float
    targets: NotRequired[list[str]]


# What a step reads: the world, the guest and the project.
Reading = Callable[[Mapping[str, Any], Mapping[str, Any], Project], Any]


@dataclass(frozen=True)
class Step:
    """One step.

    Attributes:
        name: What it is, for "... came to nothing".
        command: The action to start (a mapping with `id`, `verb` and `target_id`), or None when it cannot be started;
            the field itself is None for a step that only waits on the world.
        done: Whether the world shows it done.
        broken: For a step that waits, why it can no longer come about, or None while it still can.
    """

    name: str
    command: Reading | None
    done: Reading
    broken: Reading | None = None


@dataclass(frozen=True)
class ProjectKind:
    """One kind of project.

    Attributes:
        wording: What it is, for "could not ...": "settle in".
        gerund: The same as an activity, for "gave up ...": "settling in".
        done_words: How a finished one is told: "settled in with an ale".
        steps: The steps in order, for a project (the number of steps may depend on its `targets`).
        lasts: Game seconds before an unfinished one lapses.
        begin: Whether the guest can begin it with the target chosen: the reason it cannot, or None, and the fields the
            project takes (`target`, and `targets` where the kind has them).
        target_kind: What its `target` is: `chair`, `table` or `guest`.
        opened: Called when a project of the kind has begun (the world, the guest, the project), or None.
    """

    wording: str
    gerund: str
    done_words: str
    steps: Callable[[Project], tuple[Step, ...]]
    lasts: float
    begin: Callable[[Mapping[str, Any], Mapping[str, Any], str | None], tuple[str | None, dict[str, Any]]]
    target_kind: str
    opened: Callable[[World, Actor, Project], None] | None = None


def _action(verb: str, target: str | None, **more: Any) -> dict[str, Any]:
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target, **more}


# --- settling in: an ale from the tap, a chair, the drink ---

def _settle_error(world: Mapping[str, Any], actor: Mapping[str, Any], chair: str | None
                  ) -> tuple[str | None, dict[str, Any]]:
    # A chair at a table they could sit on, an empty hand and a tap that has ale, as far as they know.
    if actor["inventory"]["beer"] > 0:
        return "They already hold a mug of ale", {}
    if known_place(actor, "tap") is None:
        return "They know no tap that has ale", {}
    target = next((item for item in world["map"]["objects"] if item["id"] == chair), None)
    if target is None or target["kind"] != "chair" or not target.get("table_id"):
        return "Choose a chair at a table to settle at", {}
    return action_error(world, actor, _action("sit", chair)), {"target": chair}


_SETTLE_IN = (
    Step("getting the ale", lambda world, actor, project: _action("take_beer", known_place(actor, "tap")),
         lambda world, actor, project: actor["inventory"]["beer"] >= 1),
    Step("taking the chair", lambda world, actor, project: _action("sit", project["target"]),
         lambda world, actor, project: actor.get("seat_id") == project["target"]),
    Step("drinking it", lambda world, actor, project: _action("drink", None),
         lambda world, actor, project: actor["inventory"]["beer"] == 0))


# --- standing a round: an ale for each empty-handed tablemate, in turn ---

def _tablemates(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[str]:
    # Guests at the actor's table with no mug and no errand, in the order of their chairs on the map.
    table = table_of(world, actor)
    busy = errand_parties(world)
    chairs = [item["id"] for item in world["map"]["objects"] if item["kind"] == "chair" and item.get("table_id") == table]
    return [other["id"] for chair in chairs for other in world["actors"]
            if other.get("seat_id") == chair and other["id"] != actor["id"] and not on_staff(other)
            and not asleep(other) and not other["inventory"]["beer"] and other["id"] not in busy]


def _round_error(world: Mapping[str, Any], actor: Mapping[str, Any], target: str | None
                 ) -> tuple[str | None, dict[str, Any]]:
    if table_of(world, actor) is None:
        return "Only a guest at a table can stand it a round", {}
    if actor["inventory"]["beer"] >= ITEMS["beer"].hands:
        return "They have no free hand for another mug", {}
    if known_place(actor, "tap") is None:
        return "They know no tap that has ale", {}
    receivers = _tablemates(world, actor)
    if len(receivers) < 2:
        return "A round is for two or more empty-handed tablemates", {}
    return None, {"target": table_of(world, actor), "targets": receivers}


def _round_steps(project: Project) -> tuple[Step, ...]:
    def served(receiver: str) -> Reading:
        # Done once they hold a mug; a tablemate who has gone, or left the table, is skipped.
        def done(world: Mapping[str, Any], actor: Mapping[str, Any], current: Project) -> bool:
            other = find_actor(world, receiver)
            return other is None or table_of(world, other) != current["target"] or other["inventory"]["beer"] >= 1
        return done

    def bring(receiver: str) -> Reading:
        return lambda world, actor, current: _action("bring_drink", receiver)

    return tuple(Step("fetching an ale for a tablemate", bring(receiver), served(receiver))
                 for receiver in project.get("targets", []))


# --- a rematch: go to the winner and ask for another game of dice ---

def _rematch_error(world: Mapping[str, Any], actor: Mapping[str, Any], target: str | None
                   ) -> tuple[str | None, dict[str, Any]]:
    other = find_actor(world, target)
    if other is None or other["id"] == actor["id"] or on_staff(other):
        return "Choose another guest to ask for a rematch", {}
    if not any(item["kind"] == "lost_at_dice" and item["about"] == target for item in calling(actor, world["time"])):
        return "They have no lost game with that guest to answer", {}
    table = known_place(actor, "dice_table")
    if table is None or not open_chairs(world, table):
        return "No dice table they know is free", {}
    return None, {"target": target}


def _loss_answered(world: World, actor: Actor, project: Project) -> None:
    # Setting out to ask for a rematch is the answer to the loss, whatever comes of it: a plan that fails does not
    # make the same loss call for another.
    mark_answered(world, actor, {"verb": "talk", "target_id": project["target"]})


def _reach(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> dict[str, Any] | None:
    # The way to a word with them from where the guest stands: join their talk, chat beside them, or walk over to
    # their table. The aim tells the line writers what the guest came for.
    other = find_actor(world, project["target"])
    if other is None:
        return None
    if within_reach(world, actor, other):
        return _action("join_conversation" if conversation_of(world, other["id"]) else "talk", other["id"], aim="rematch")
    return _action("approach", other["id"], aim="rematch") if table_of(world, other) is not None else None


def _met(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> bool:
    scene = conversation_of(world, actor["id"])
    return scene is not None and project["target"] in scene["participants"]


def _playing(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> bool:
    pair = {actor["id"], project["target"]}
    return any(item["kind"] == "dice_table" and pair <= set((item.get("game") or {}).get("players", []))
               for item in world["map"]["objects"])


def _no_game(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> str | None:
    # Why the game can no longer come about: they went home, said no, or the talk ended with no game agreed.
    other = find_actor(world, project["target"])
    if other is None:
        return "they went home"
    refused = f"from {actor['name']}"
    if any(item["type"] == "invitation_declined" and item["time"] >= project["started_at"] and refused in item["message"]
           and "dice" in item["message"] for item in world["events"]):
        return "they would not play"
    agreed = any(item["kind"] == "dice_together" and {item["from"], item["to"]} == {actor["id"], other["id"]}
                 for item in world["invitations"])
    heading = (actor.get("action") or {}).get("verb") == PLAY  # on the way to the table, the game not yet begun
    return None if _met(world, actor, project) or agreed or heading else "no game came of the talk"


_REMATCH = (Step("getting to them", _reach, _met),
            Step("agreeing a game", None, _playing, _no_game))


PROJECTS: Mapping[str, ProjectKind] = MappingProxyType({
    "settle_in": ProjectKind(
        wording="settle in", gerund="settling in", done_words="settled in with an ale",
        steps=lambda project: _SETTLE_IN, lasts=150.0, begin=_settle_error, target_kind="chair"),
    "stand_a_round": ProjectKind(
        wording="stand a round", gerund="standing a round", done_words="stood the table a round",
        steps=_round_steps, lasts=240.0, begin=_round_error, target_kind="table"),
    "rematch": ProjectKind(
        wording="ask for a rematch", gerund="asking for a rematch", done_words="got the rematch",
        steps=lambda project: _REMATCH, lasts=150.0, begin=_rematch_error, target_kind="guest", opened=_loss_answered),
})


def project_error(world: Mapping[str, Any], actor: Mapping[str, Any], kind: str, target: str | None) -> str | None:
    """Tell why a guest cannot begin a project.

    Args:
        world: Current world.
        actor: The guest.
        kind: A kind of `PROJECTS`.
        target: The chair, table or guest it is about (None for a kind that picks its own).

    Returns:
        A refusal reason, or None when they can.
    """
    if on_project(world, actor["id"]):
        return f"{actor['name']} is busy with a plan already"
    return PROJECTS[kind].begin(world, actor, target)[0]


def open_project(world: World, actor: Actor, kind: str, target: str | None) -> dict[str, Any]:
    """Begin a project for a guest.

    Args:
        world: World whose `projects` receive it.
        actor: The guest, who may not already have one.
        kind: A kind of `PROJECTS`.
        target: The chair, table or guest it is about (None for a kind that picks its own).

    Returns:
        Acceptance as `world.start_action` reports it: refused with the reason when `project_error` finds one.
    """
    reason = project_error(world, actor, kind, target)
    if reason:
        return {"accepted": False, "reason": reason}
    fields = PROJECTS[kind].begin(world, actor, target)[1]
    project = Project(kind=kind, by=actor["id"], target=fields["target"], step=0, of=0, running=False,
                      started_at=world["time"])
    if "targets" in fields:
        project["targets"] = fields["targets"]
    project["of"] = len(PROJECTS[kind].steps(project))
    world["projects"].append(project)
    opened = PROJECTS[kind].opened
    if opened is not None:
        opened(world, actor, project)
    return {"accepted": True, "reason": None}


def on_project(world: Mapping[str, Any], actor_id: str) -> bool:
    """Tell whether a guest is carrying out a project.

    Args:
        world: Current world.
        actor_id: The guest.

    Returns:
        True from the choice until the project ends: the guest asks for no decision meanwhile.
    """
    return any(item["by"] == actor_id for item in world["projects"])


def honor_projects(world: World, start: Start) -> None:
    """Carry every project one step further.

    Args:
        world: World whose projects and visitors are updated in place. A project of a guest who has gone home is
            dropped without a word. Otherwise it expires once `lasts` has passed; finished steps are passed over; a
            step that waits on the world ends the project as failed when it can no longer come about; and, when the
            guest is idle, in no conversation and on no errand, a started step that came to nothing ends it (as
            dropped when an interrupt came after it began, else as failed) and the next step is started, a refusal
            ending it as failed.
        start: Starts an action through the ordinary lifecycle (`world.start_action`).
    """
    for project in list(world["projects"]):
        actor = find_actor(world, project["by"])
        outcome = None if actor is None else _carry_on(world, actor, project, start)
        if actor is None or outcome:
            world["projects"].remove(project)
        if actor is not None and outcome:
            kind = PROJECTS[project["kind"]]
            words = {"done": kind.done_words, "expired": f"gave up {kind.gerund}",
                     "dropped": f"was called away from {kind.gerund}"}
            message = words[outcome[0]] if outcome[0] in words else f"could not {kind.wording}: {outcome[1]}"
            record_event(world, actor, f"project_{outcome[0]}", f"{actor['name']} {message} ({project['kind']})")


def _carry_on(world: World, actor: Actor, project: Project, start: Start) -> tuple[str, str] | None:
    # Returns how the project ended (its outcome and the reason, for a failure), or None while it goes on.
    kind = PROJECTS[project["kind"]]
    steps = kind.steps(project)
    if world["time"] - project["started_at"] >= kind.lasts:
        return "expired", ""
    while project["step"] < project["of"] and steps[project["step"]].done(world, actor, project):
        project["step"] += 1
        project["running"] = False
    if project["step"] == project["of"]:
        return "done", ""
    step = steps[project["step"]]
    if step.command is None:
        why = step.broken(world, actor, project) if step.broken else None
        return ("failed", why) if why else None
    if actor["status"] != "idle" or conversation_of(world, actor["id"]) is not None \
            or fetching_a_drink(world, actor["id"]):
        return None
    if project["running"]:
        interrupted = actor["interrupted_at"] is not None and actor["interrupted_at"] >= project["started_at"]
        return ("dropped", "") if interrupted else ("failed", f"{step.name} came to nothing")
    command = step.command(world, actor, project)
    if command is None:
        return "failed", f"no way of {step.name}"
    result = start(world, actor["id"], command)
    if not result["accepted"]:
        return "failed", str(result["reason"]).rstrip(".").lower()
    project["running"] = True
    return None


def check_saved_projects(world: Mapping[str, Any]) -> None:
    """Check the projects in a saved world.

    Args:
        world: Decoded save.

    Raises:
        ValueError: The projects are not a list of well-formed ones: a known kind with its step count, a step within it,
            a guest in the hall, a target of the kind's sort, a start not in the future, the `targets` exactly where
            the kind has them and all guests in the hall, and at most one project per guest.
    """
    projects = world.get("projects")
    if not isinstance(projects, list):
        raise ValueError("Saved projects must be a list")
    guests = {item["id"] for item in world["actors"]}
    places = {"chair": {item["id"] for item in world["map"]["objects"] if item["kind"] == "chair" and item.get("table_id")},
              "table": {item["id"] for item in world["map"]["objects"] if item["kind"] == "table"}, "guest": guests}
    for item in projects:
        required = set(Project.__annotations__) - {"targets"}
        if not isinstance(item, dict) or not required <= set(item) <= set(Project.__annotations__) \
                or item["kind"] not in PROJECTS or item["by"] not in guests \
                or item["target"] not in places[PROJECTS[item["kind"]].target_kind] or type(item["running"]) is not bool \
                or type(item["step"]) is not int or type(item["of"]) is not int:
            raise ValueError(f"Invalid saved project {item!r}")
        targets = item.get("targets")
        if targets is not None and (not isinstance(targets, list) or not set(targets) <= guests):
            raise ValueError(f"Invalid saved project targets {targets!r}")
        if item["of"] != len(PROJECTS[item["kind"]].steps(cast(Project, item))) or not 0 <= item["step"] < item["of"]:
            raise ValueError(f"Invalid saved project {item!r}")
        number(item["started_at"], "Saved project start", 0, world["time"])
    if len({item["by"] for item in projects}) != len(projects):
        raise ValueError("A saved guest has more than one project")
