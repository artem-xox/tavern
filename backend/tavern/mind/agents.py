"""How a guest chooses among their candidates: the model or the local policy, in stages."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.body.projects import PROJECTS
from tavern.mind.briefing import brief
from tavern.mind.candidates import Action, action, build_candidates, build_seat_candidates
from tavern.mind.families import family_scores
from tavern.mind.hall_view import line_place
from tavern.mind.local_policy import ASK_FLOOR, local_aim_scores, local_answer_scores, local_scores, local_seat_scores
from tavern.mind.options import aim_text, answer_text
from tavern.mind.selection import bounded, drawable, read_answers, read_temperature, select, spread, worth_asking
from tavern.social.aims import AIM_VERBS, aim_candidates, offered_aims
from tavern.social.invitations import answer_act


class EvaluatorError(RuntimeError):
    """A recoverable failure of a model evaluator, safe to display in snapshots (`jev.JevError`).

    `status` is the HTTP status that caused it, when there was one.
    """

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


# Scores each candidate 0–1 from the evaluator view, the candidates and the AI config;
# raises EvaluatorError on a recoverable model failure, which falls back to the local policy.
Evaluator = Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]], Mapping[str, Any]], Awaitable[dict[str, float]]]


@dataclass(frozen=True)
class Evaluators:
    """The model port of a decision: one evaluator per stage of choosing.

    `actions` scores the first stage, one option per activity family; `seats` the chairs
    after `seating`; `family` the actions within another chosen family. Without `family`,
    `actions` scores those too: they are ordinary actions. `aims` scores the aims of a chosen social
    option; a model cannot be asked without it. `answers` scores how
    an invitee answers (`selection.read_answers`), likewise.
    """

    actions: Evaluator
    seats: Evaluator
    family: Evaluator | None = None
    aims: Evaluator | None = None
    answers: Evaluator | None = None


async def _unwired(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                   config: Mapping[str, Any]) -> dict[str, float]:
    raise ValueError("Asking a model needs evaluators; the shell supplies them")



async def choose_action(
    observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random,
    evaluators: Evaluators | None = None, limit: int = 8,
) -> dict[str, Any]:
    """Evaluate and select a candidate without blocking the world simulation.

    Args:
        observation: Private actor observation; no other NPC's state is used.
        config: Explicit API key, model, timeout and selection temperature.
        rng: Seeded random generator owned by the calling simulation.
        evaluators: Model port asked when the config holds a key. New callers pass it;
            None asks no model: a config with a model key then fails loudly.
        limit: Most options one request may hold; the local policy keeps the best ones.

    Returns:
        Action, normalized scores, actual decision source and visible fallback error.
        A missing key selects intentional local mode with no error. The first stage scores
        one option per activity family. When the visitor chooses `seating`, a second
        evaluation picks the chair and `seat` holds that stage's source, scores and error;
        when they choose a family of several actions, a second evaluation picks one of them
        and `family` holds the family's name and that stage's source, scores and error.

    Raises:
        ValueError: Observation, configuration or limit is malformed.
    """
    evaluators = evaluators or Evaluators(_unwired, _unwired)
    # The observation says which kinds of project exist (`_settling` reads it).
    observation = {**observation, "projects": list(PROJECTS)}
    options, temperature = build_candidates(observation), read_temperature(config)
    # Every concrete action is scored together, so a family is worth its best member.
    local = local_scores(observation, [item for option in options for item in option.get("members", [option])])
    draw = (config, rng, temperature, limit)
    decision = await _decide(observation, options, family_scores(options, local), evaluators.actions, *draw)
    chosen = decision["action"]
    if "members" in chosen:
        member = await _decide(observation, chosen["members"], local, evaluators.family or evaluators.actions, *draw)
        decision = {**decision, "action": member["action"], "family": {"name": chosen["id"], **_stage(member)}}
    action = decision["action"]
    if ACTIVITIES[action["verb"]].chooses_chair:
        # A second decision picks the chair; the verb that wished for one (sitting, or settling in) takes it.
        seats = build_seat_candidates(observation)
        seat = await _decide(observation, seats, local_seat_scores(observation, seats), evaluators.seats, *draw)
        return {**decision, "action": _at_chair(action, seat["action"]), "seat": _stage(seat)}
    return await _aimed(observation, decision, evaluators, draw)


def _at_chair(wish: Mapping[str, Any], seat: Mapping[str, Any]) -> Action:
    # `seating` becomes the chair's own `sit`; any other wish for a chair keeps its verb and names the chair.
    return action(seat["verb"] if wish["verb"] == "seating" else wish["verb"], seat["target_id"])


async def _aimed(observation: Mapping[str, Any], decision: dict[str, Any], evaluators: Evaluators,
                 draw: tuple[Mapping[str, Any], Random, float, int]) -> dict[str, Any]:
    # The third stage: a social option is followed by what the guest means by it. One aim is
    # set without a request, and shows no stage.
    action, config = decision["action"], draw[0]
    if action["verb"] not in AIM_VERBS:
        return decision
    aims = offered_aims(observation, action)
    if len(aims) == 1:
        return {**decision, "action": {**action, "aim": aims[0]}}
    if config.get("typesafe_api_key") and evaluators.aims is None:
        raise ValueError("A model is asked but no evaluator of aims is wired")
    candidates = aim_candidates(action, aims)
    stage = await _decide(observation, candidates, local_aim_scores(observation, candidates),
                          evaluators.aims or _unwired, *draw, view=_aim_view)
    aim = stage["action"]["aim"]
    return {**decision, "action": {**action, "aim": aim}, "aim": {"name": aim, **_stage(stage)}}


async def choose_answer(observation: Mapping[str, Any], invitation: Mapping[str, Any], options: Sequence[str],
                        config: Mapping[str, Any], rng: Random, evaluators: Evaluators | None = None,
                        limit: int = 8) -> dict[str, Any]:
    """Choose how an invitee answers the invitation waiting for them.

    Args:
        observation: The invitee's observation, with the people in sight.
        invitation: The pending invitation (`kind`, `from`, `to`).
        options: The answers open to them (`invitations.answer_options`).
        config: Explicit API key, model, timeout and selection temperature.
        rng: Seeded random generator owned by the calling simulation.
        evaluators: Model port; its `answers` is asked when the config holds a key.
        limit: Most options one request may hold.

    Returns:
        `answer` (one of the options), the `source` of the choice (`jev` or `local`), the `scores` per option and
        the visible fallback `error`, as for a decision.

    Raises:
        ValueError: There are no options, an option is not an answer, the config is malformed, or a key is set with
            the answers setting on but no evaluator of answers is wired.
    """
    if not options:
        raise ValueError("An invitee needs at least one way to answer")
    evaluators = evaluators or Evaluators(_unwired, _unwired)
    if config.get("typesafe_api_key") and read_answers(config) and evaluators.answers is None:
        raise ValueError("The answers setting is on but no evaluator of answers is wired")
    candidates = [{"id": option, "verb": answer_act(option), "target_id": invitation["from"], "answer": option}
                  for option in options]

    def view(seen: Mapping[str, Any], shown: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {**_evaluator_view(seen, []), "options": {item["id"]: answer_text(seen, invitation, item["answer"])
                                                         for item in shown}}

    decision = await _decide(observation, candidates, local_answer_scores(observation, invitation, candidates),
                             evaluators.answers or _unwired, config, rng, read_temperature(config), limit, view=view)
    return {"answer": decision["action"]["answer"], **_stage(decision)}


def _stage(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {key: decision[key] for key in ("source", "scores", "error")}


def _evaluator_view(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # The evaluator reads the situation in plain words plus the visitor's exact numbers;
    # raw cell lists, maps and earlier scores are noise to it.
    actor = observation["actor"]
    keys = ("name", "needs", "traits", "inventory", "visit", "seat_id", "favorite_seat_id")
    return {**brief(observation, candidates), "self": {key: actor.get(key) for key in keys}}


def _in_line(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> set[str]:
    # Keeping one's place in a line is never a fixture to drop, however little the place is wanted.
    places = {item["id"]: item for item in observation["objects"] if "queue_spots" in item}
    return {action["id"] for action in candidates
            if action.get("target_id") in places and line_place(observation, places[action["target_id"]])[1]}


def _aim_view(observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # The same picture of the guest as for any choice, with each option told as an aim of the action.
    return {**_evaluator_view(observation, []), "options": {item["id"]: aim_text(observation, item)
                                                            for item in candidates}}


async def _decide(
    observation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], local: Mapping[str, float], remote: Evaluator,
    config: Mapping[str, Any], rng: Random, temperature: float, limit: int,
    view: Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]]], dict[str, Any]] = _evaluator_view,
) -> dict[str, Any]:
    asks = bool(config.get("typesafe_api_key"))
    # Only a model's request is made lean: the local policy already ranks by these scores, so a model-less evening
    # draws from the same options.
    if asks:
        candidates = worth_asking(candidates, local, ASK_FLOOR, _in_line(observation, candidates))
    candidates = bounded(candidates, local, limit)
    scores, source, error = {action["id"]: local[action["id"]] for action in candidates}, "local", None
    if asks:
        try:
            scores = await remote(view(observation, candidates), candidates, config)
            source = "jev"
        except EvaluatorError as failure:
            error = str(failure)
    # Everyone draws from the options near their best, but how near and how evenly depends on who they are.
    draw = spread(observation["actor"], temperature)
    return {"action": select(drawable(candidates, scores, draw.window), scores, draw.temperature, rng),
            "source": source, "scores": scores, "error": error}
