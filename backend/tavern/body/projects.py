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
from typing import Any, TypedDict

from tavern.body.actions import action_error
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.hall.validation import number
from tavern.social.invitations import known_place
from tavern.social.scenes import conversation_of

# Starts an action the way `world.start_action` does: world, visitor ID, action; returns acceptance.
Start = Callable[[World, str, Mapping[str, Any]], Mapping[str, Any]]


class Project(TypedDict):
    """A plan under way: its kind, whose it is, the chair or place it is about, the step reached out of `of`, whether
    that step has been started, and since when."""

    kind: str
    by: str
    target: str
    step: int
    of: int
    running: bool
    started_at: float


@dataclass(frozen=True)
class Step:
    """One step: the verb started, the target it is started on (None when it cannot be found), and whether the world
    shows it done."""

    verb: str
    target: Callable[[Mapping[str, Any], Mapping[str, Any], Project], str | None]
    done: Callable[[Mapping[str, Any], Mapping[str, Any], Project], bool]


@dataclass(frozen=True)
class ProjectKind:
    """One kind of project.

    Attributes:
        wording: What it is, for "could not ...": "settle in".
        gerund: The same as an activity, for "gave up ...": "settling in".
        done_words: How a finished one is told: "settled in with an ale".
        steps: The steps in order.
        lasts: Game seconds before an unfinished one lapses.
        error: Why it cannot begin, given the world, the guest and the target, or None.
    """

    wording: str
    gerund: str
    done_words: str
    steps: tuple[Step, ...]
    lasts: float
    error: Callable[[Mapping[str, Any], Mapping[str, Any], str | None], str | None]


def _tap(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> str | None:
    return known_place(actor, "tap")


def _chair(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> str | None:
    return project["target"]


def _nothing(world: Mapping[str, Any], actor: Mapping[str, Any], project: Project) -> str | None:
    return None


def _settle_error(world: Mapping[str, Any], actor: Mapping[str, Any], chair: str | None) -> str | None:
    # A chair at a table they could sit on, an empty hand and a tap that has ale, as far as they know.
    if actor["inventory"]["beer"] > 0:
        return "They already hold a mug of ale"
    if known_place(actor, "tap") is None:
        return "They know no tap that has ale"
    target = next((item for item in world["map"]["objects"] if item["id"] == chair), None)
    if target is None or target["kind"] != "chair" or not target.get("table_id"):
        return "Choose a chair at a table to settle at"
    return action_error(world, actor, {"id": f"sit:{chair}", "verb": "sit", "target_id": chair})


PROJECTS: Mapping[str, ProjectKind] = MappingProxyType({
    "settle_in": ProjectKind(
        wording="settle in", gerund="settling in", done_words="settled in with an ale",
        steps=(Step("take_beer", _tap, lambda world, actor, project: actor["inventory"]["beer"] >= 1),
               Step("sit", _chair, lambda world, actor, project: actor.get("seat_id") == project["target"]),
               Step("drink", _nothing, lambda world, actor, project: actor["inventory"]["beer"] == 0)),
        lasts=150.0, error=_settle_error),
})


def project_error(world: Mapping[str, Any], actor: Mapping[str, Any], kind: str, target: str | None) -> str | None:
    """Tell why a guest cannot begin a project.

    Args:
        world: Current world.
        actor: The guest.
        kind: A kind of `PROJECTS`.
        target: The chair or place it is about.

    Returns:
        A refusal reason, or None when they can.
    """
    if on_project(world, actor["id"]):
        return f"{actor['name']} is busy with a plan already"
    return PROJECTS[kind].error(world, actor, target)


def open_project(world: World, actor: Actor, kind: str, target: str | None) -> dict[str, Any]:
    """Begin a project for a guest.

    Args:
        world: World whose `projects` receive it.
        actor: The guest, who may not already have one.
        kind: A kind of `PROJECTS`.
        target: The chair or place it is about.

    Returns:
        Acceptance as `world.start_action` reports it: refused with the reason when `project_error` finds one.
    """
    reason = project_error(world, actor, kind, target)
    if reason:
        return {"accepted": False, "reason": reason}
    assert target is not None  # Every kind's `error` refuses a missing target.
    world["projects"].append(Project(kind=kind, by=actor["id"], target=target, step=0, of=len(PROJECTS[kind].steps),
                                     running=False, started_at=world["time"]))
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
            dropped without a word. Otherwise it expires once `lasts` has passed; and when the guest is idle and not
            in a conversation, finished steps are passed over, a started step that came to nothing ends the project
            (as dropped when an interrupt came after it began, else as failed), and the next step is started, a refusal
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
            words = {"done": f"{kind.done_words}", "expired": f"gave up {kind.gerund}",
                     "dropped": f"was called away from {kind.gerund}"}
            message = words[outcome[0]] if outcome[0] in words else f"could not {kind.wording}: {outcome[1]}"
            record_event(world, actor, f"project_{outcome[0]}", f"{actor['name']} {message} ({project['kind']})")


def _carry_on(world: World, actor: Actor, project: Project, start: Start) -> tuple[str, str] | None:
    # Returns how the project ended (its outcome and the reason, for a failure), or None while it goes on.
    kind = PROJECTS[project["kind"]]
    if world["time"] - project["started_at"] >= kind.lasts:
        return "expired", ""
    if actor["status"] != "idle" or conversation_of(world, actor["id"]) is not None:
        return None
    while project["step"] < project["of"] and kind.steps[project["step"]].done(world, actor, project):
        project["step"] += 1
        project["running"] = False
    if project["step"] == project["of"]:
        return "done", ""
    if project["running"]:
        interrupted = actor["interrupted_at"] is not None and actor["interrupted_at"] >= project["started_at"]
        return ("dropped", "") if interrupted else ("failed", f"{kind.steps[project['step']].verb.replace('_', ' ')} "
                                                              "came to nothing")
    step = kind.steps[project["step"]]
    target = step.target(world, actor, project)
    if target is None and step.target is not _nothing:
        return "failed", f"nowhere to {step.verb.replace('_', ' ')}"
    result = start(world, actor["id"], {"id": step.verb if target is None else f"{step.verb}:{target}",
                                        "verb": step.verb, "target_id": target})
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
            a guest in the hall, a chair at a table, a start not in the future, and at most one project per guest.
    """
    projects = world.get("projects")
    if not isinstance(projects, list):
        raise ValueError("Saved projects must be a list")
    guests = {item["id"] for item in world["actors"]}
    chairs = {item["id"] for item in world["map"]["objects"] if item["kind"] == "chair" and item.get("table_id")}
    for item in projects:
        if not isinstance(item, dict) or set(item) != set(Project.__annotations__) or item["kind"] not in PROJECTS \
                or item["by"] not in guests or item["target"] not in chairs or type(item["running"]) is not bool \
                or type(item["step"]) is not int or type(item["of"]) is not int \
                or item["of"] != len(PROJECTS[item["kind"]].steps) or not 0 <= item["step"] < item["of"]:
            raise ValueError(f"Invalid saved project {item!r}")
        number(item["started_at"], "Saved project start", 0, world["time"])
    if len({item["by"] for item in projects}) != len(projects):
        raise ValueError("A saved guest has more than one project")
