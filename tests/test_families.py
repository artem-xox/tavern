"""Bounded choices: an activity family first, then a concrete option within it."""

import asyncio
import json
from random import Random
from typing import Any

import httpx
import pytest

from tavern.body.activities import ACTIVITIES, FAMILIES
from tavern.mind.agents import Evaluator, Evaluators, build_candidates, choose_action
from tavern.mind.briefing import brief
from tavern.evening.decisions import apply_decision
from tavern.mind.families import family_scores, group_families
from tavern.adapters.jev import JevError, evaluate_actions
from tavern.evening.lockstep import Evening, Pace, run_evening
from tavern.evening.recording import Record, format_record, parse_records, record_calls, replay_calls
from tavern.mind.selection import bounded
from tavern.hall.world import create_world


def act(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build a concrete candidate action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def place(kind: str, object_id: str, x: int = 2, **fields: Any) -> dict[str, Any]:
    """Describe a known place with one spot to use it from."""
    return {"id": object_id, "kind": kind, "x": x, "y": 3, "interaction_spots": [[x, 4]], "reserved_by": None,
            **fields}


def view(objects: list[dict[str, Any]], needs: dict[str, float] | None = None,
         visitors: list[dict[str, Any]] | None = None, **actor: Any) -> dict[str, Any]:
    """Build Ada's personal observation; keywords override her own state."""
    calm = {"thirst": 10, "fatigue": 10, "bladder": 10, "social": 10, "boredom": 10}
    own = {"id": "ada", "name": "Ada", "x": 5, "y": 5, "inventory": {"beer": 0}, "needs": {**calm, **(needs or {})},
           "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5}, "favorite_seat_id": None,
           "visit": {"seconds": 120.0, "beers": 1, "grievances": []}}
    return {"actor": {**own, **actor}, "objects": objects, "visitors": visitors or [], "memory": []}


def pastimes() -> list[dict[str, Any]]:
    """The darts board and the fireplace: two ways to pass the time."""
    return [place("darts", "darts", 8), place("fireplace", "hearth", 1)]


def config(**fields: Any) -> dict[str, Any]:
    """Build an offline decision configuration unless a key is supplied."""
    return {"typesafe_api_key": None, "model": "jev-latest", "timeout": 2.0, "temperature": 0.0, **fields}


def preferring(*verbs: str) -> Evaluator:
    """Build a fake evaluator that scores the given verbs highest."""
    async def evaluate(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: float(action["verb"] in verbs) for action in candidates}
    return evaluate


async def timing_out(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
    """Fail like the Jev adapter does on a timeout."""
    raise JevError("Jev request timed out")


@pytest.mark.parametrize("verb", [pytest.param(verb, id=verb) for verb in ACTIVITIES])
def test_every_activity_belongs_to_a_described_family(verb: str) -> None:
    assert (ACTIVITIES[verb].family in FAMILIES, ACTIVITIES[verb].family in ACTIVITIES) == (True, False)


@pytest.mark.parametrize("candidates, expected", [
    pytest.param([], [], id="empty"),
    pytest.param([act("wait")], [("wait", None)], id="single-action-stands-for-its-family"),
    pytest.param([act("drink"), act("inspect"), act("wait")], [("drink", None), ("inspect", None), ("wait", None)],
                 id="one-action-per-family-unchanged"),
    pytest.param([act("play_darts", "darts"), act("wait"), act("watch", "hearth")],
                 [("pastime", ["play_darts:darts", "watch:hearth"]), ("wait", None)],
                 id="duplicate-family-collapses-where-it-first-appears"),
    pytest.param([act("talk", "bea"), act("talk", "cid"), act("talk", "dan")],
                 [("company", ["talk:bea", "talk:cid", "talk:dan"])], id="every-tablemate-in-one-family"),
])
def test_candidates_are_grouped_into_one_option_per_family(candidates: list[dict[str, Any]],
                                                           expected: list[tuple[str, Any]]) -> None:
    options = group_families(candidates)
    assert [(option["id"], [item["id"] for item in option["members"]] if "members" in option else None)
            for option in options] == expected


def test_unknown_verb_has_no_family() -> None:
    with pytest.raises(ValueError, match="fly"):
        group_families([act("fly")])


@pytest.mark.parametrize("options, scores, expected", [
    pytest.param([], {}, {}, id="empty"),
    pytest.param([act("wait")], {"wait": 0.2}, {"wait": 0.2}, id="single-action-keeps-its-score"),
    pytest.param(group_families([act("play_darts", "darts"), act("watch", "hearth"), act("watch", "window")]),
                 {"play_darts:darts": 0.3, "watch:hearth": 0.7, "watch:window": 0.7}, {"pastime": 0.7},
                 id="duplicate-best-scores-family-is-worth-its-best-member"),
])
def test_a_family_scores_as_its_best_member(options: list[dict[str, Any]], scores: dict[str, float],
                                            expected: dict[str, float]) -> None:
    assert family_scores(options, scores) == expected


def test_a_family_without_member_scores_fails_loudly() -> None:
    with pytest.raises(KeyError):
        family_scores(group_families([act("talk", "bea"), act("talk", "cid")]), {"talk:bea": 0.5})


@pytest.mark.parametrize("ids, scores, limit, expected", [
    pytest.param([], {}, 2, [], id="empty"),
    pytest.param(["a"], {"a": 0.1}, 2, ["a"], id="single-under-the-limit"),
    pytest.param(["a", "b", "c"], {"a": 0.5, "b": 0.5, "c": 0.5}, 2, ["a", "b"], id="duplicate-scores-keep-order"),
    pytest.param(["a", "b", "c"], {"a": 0.1, "b": 0.9, "c": 0.5}, 2, ["b", "c"], id="worst-dropped-order-kept"),
])
def test_requests_are_bounded_to_the_best_options(ids: list[str], scores: dict[str, float], limit: int,
                                                  expected: list[str]) -> None:
    candidates = [act(item) for item in ids]
    assert [item["id"] for item in bounded(candidates, scores, limit)] == expected


def test_a_limit_below_one_fails_loudly() -> None:
    with pytest.raises(ValueError, match="limit"):
        bounded([act("wait")], {"wait": 1.0}, 0)


def test_known_pastimes_are_one_first_stage_option() -> None:
    assert [option["id"] for option in build_candidates(view(pastimes()))] == ["pastime", "inspect", "wait"]


@pytest.mark.parametrize("comfort, boredom, expected", [
    pytest.param(0.9, 40, "watch:hearth", id="cosy-soul-watches-the-fire"),
    pytest.param(0.1, 90, "play_darts:darts", id="restless-soul-plays-darts"),
])
def test_local_policy_picks_the_family_then_the_member(comfort: float, boredom: float, expected: str) -> None:
    observation = view(pastimes(), needs={"boredom": boredom},
                       traits={"patience": 0.5, "comfort": comfort, "curiosity": 0.5})
    result = asyncio.run(choose_action(observation, config(), Random(0)))
    assert (result["action"]["id"], max(result["scores"], key=result["scores"].get),
            result["family"]["name"], sorted(result["family"]["scores"]), result["family"]["source"]) == (
        expected, "pastime", "pastime", ["play_darts:darts", "watch:hearth"], "local")


@pytest.mark.parametrize("objects, evaluators, expected", [
    pytest.param(pastimes(), Evaluators(preferring("pastime"), preferring("sit"), preferring("play_darts")),
                 ("play_darts:darts", "jev", None), id="family-evaluator-picks-the-member"),
    pytest.param(pastimes(), Evaluators(preferring("pastime", "watch"), preferring("sit")),
                 ("watch:hearth", "jev", None), id="without-a-family-evaluator-the-action-evaluator-is-asked"),
    pytest.param(pastimes(), Evaluators(preferring("pastime"), preferring("sit"), timing_out),
                 ("watch:hearth", "local", "Jev request timed out"), id="failed-member-choice-falls-back-visibly"),
    pytest.param([place("darts", "darts")], Evaluators(preferring("play_darts"), preferring("sit"), timing_out),
                 ("play_darts:darts", None, None), id="single-member-family-skips-the-second-stage"),
])
def test_jev_scores_the_family_then_the_members(objects: list[dict[str, Any]], evaluators: Evaluators,
                                                expected: tuple[Any, ...]) -> None:
    observation = view(objects, traits={"patience": 0.5, "comfort": 0.9, "curiosity": 0.5})
    result = asyncio.run(choose_action(observation, config(typesafe_api_key="test"), Random(0), evaluators))
    stage = result.get("family", {})
    assert (result["action"]["id"], stage.get("source"), stage.get("error")) == expected


@pytest.mark.parametrize("leave_score, drawn", [
    pytest.param(0.25, False, id="slightly-worthwhile-exit-never-drawn"),
    pytest.param(0.5, True, id="moderately-worthwhile-exit-may-be-drawn"),
])
def test_going_home_by_either_door_still_needs_endorsement(leave_score: float, drawn: bool) -> None:
    async def actions(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {action["id"]: leave_score if action["verb"] == "going_home" else 0.5 for action in candidates}

    evaluators = Evaluators(actions, preferring("sit"), preferring("leave"))
    doors = [place("door", "front"), place("door", "back")]
    settings = config(typesafe_api_key="test", temperature=0.25)
    verbs = {asyncio.run(choose_action(view(doors), settings, Random(seed), evaluators))["action"]["verb"]
             for seed in range(60)}
    assert ("leave" in verbs) == drawn


def crowded_inn() -> dict[str, Any]:
    """Ada seated with four tablemates in a big hall; Eli sits at another table with free chairs."""
    tables = [place("table", f"t{index}", index * 3) for index in range(6)]
    chairs = [place("chair", f"t{table}-{side}", table * 3 + side, table_id=f"t{table}")
              for table in range(6) for side in range(5)]
    loose = [place("chair", f"stool-{index}", index) for index in range(3)]
    sights = [place("window", f"window-{index}", index) for index in range(4)]
    places = [place("tap", f"tap-{index}", index, stock=9) for index in range(3)] + [
        place("toilet", "wc-1"), place("toilet", "wc-2"), place("door", "front"), place("door", "back"),
        place("darts", "darts"), place("fireplace", "hearth")]
    mates = [{"id": name, "name": name.title(), "x": 1, "y": 3, "seat_id": f"t0-{side}", "table_id": "t0",
              "available": True} for side, name in enumerate(("bea", "cid", "dan", "eve"), start=1)]
    stranger = {"id": "eli", "name": "Eli", "x": 9, "y": 3, "seat_id": "t3-0", "table_id": "t3", "available": True}
    return view([*tables, *chairs, *loose, *sights, *places], needs={"thirst": 60}, visitors=[*mates, stranger],
                seat_id="t0-0", favorite_seat_id="t0-0")


@pytest.mark.parametrize("verb", [pytest.param(verb, id=verb) for verb in
                                  ("seating", "company", "pastime", "refreshment", "wc", "going_home", "resting")])
def test_a_flooded_choice_never_asks_about_more_than_the_limit(verb: str) -> None:
    sizes: list[int] = []

    def counting(chosen: str) -> Evaluator:
        async def evaluate(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
            sizes.append(len(candidates))
            return {action["id"]: float(action["verb"] == chosen) for action in candidates}
        return evaluate

    evaluators = Evaluators(counting(verb), counting("sit"), counting("none"))
    result = asyncio.run(choose_action(crowded_inn(), config(typesafe_api_key="test"), Random(0), evaluators,
                                       limit=8))
    concrete = sum(len(option.get("members", [option])) for option in build_candidates(crowded_inn()))
    assert (len(sizes), max(sizes) <= 8, concrete > 8) == (2, True, True), result


def mates(count: int) -> dict[str, Any]:
    """Ada seated at a long table with `count` tablemates free to chat."""
    names = ["bea", "cid", "dan", "eve", "fay"][:count]
    chairs = [place("chair", f"long-{index}", index, table_id="long") for index in range(count + 1)]
    company = [{"id": name, "name": name.title(), "x": 1, "y": 3, "seat_id": f"long-{index}", "table_id": "long",
                "available": True} for index, name in enumerate(names, start=1)]
    return view(chairs, visitors=company, seat_id="long-0", favorite_seat_id="long-0")


@pytest.mark.parametrize("observation, option, phrases", [
    pytest.param(view(pastimes()), "pastime", ["pass the time", "darts board", "flames in the fireplace"],
                 id="pastime-lists-each-way-to-pass-the-time"),
    pytest.param(mates(2), "company", ["chat with someone", "Bea", "Cid"], id="company-names-both-tablemates"),
    pytest.param(mates(5), "company", ["Bea", "Cid", "Dan", "2 more"], id="duplicate-heavy-family-is-summarized"),
])
def test_a_family_is_briefed_with_its_concrete_options(observation: dict[str, Any], option: str,
                                                       phrases: list[str]) -> None:
    text = brief(observation, build_candidates(observation))["options"][option]
    assert [phrase for phrase in phrases if phrase not in text] == [], text


def family_question(option: dict[str, Any]) -> dict[str, Any]:
    """Capture the Score question Jev would be asked about one first-stage option."""
    captured: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"answers": {option["id"]: {"type": "score", "score": 2}}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await evaluate_actions(view(pastimes()), [option], config(typesafe_api_key="test"), client)
    asyncio.run(run())
    return captured[0]["questions"][option["id"]]


def pastime_hall() -> dict[str, Any]:
    """A 9×6 hall with a door, darts and a fireplace, and Ada inside."""
    def spot(kind: str, x: int, y: int) -> dict[str, Any]:
        return {"id": kind, "kind": kind, "name": kind.title(), "x": x, "y": y, "interaction_spots": [[x, 4]]}
    return {"width": 9, "height": 6, "blocked": [],
            "objects": [spot("door", 4, 5), spot("darts", 8, 3), {**spot("fireplace", 0, 3), "appeal": 0.5, "reach": 3}],
            "actors": [{"id": "ada", "name": "Ada", "x": 4, "y": 4}]}


@pytest.mark.parametrize("stages", [
    pytest.param({}, id="empty-single-stage"),
    pytest.param({"family": {"name": "pastime", "source": "jev", "scores": {"play_darts:darts": 1.0}, "error": None}},
                 id="single-family-stage"),
    pytest.param({"seat": {"source": "local", "scores": {}, "error": None},
                  "family": {"name": "pastime", "source": "local", "scores": {}, "error": "Jev HTTP 500"}},
                 id="duplicate-second-stages-both-kept"),
])
def test_the_visible_decision_keeps_every_second_stage(stages: dict[str, Any]) -> None:
    world = create_world(pastime_hall())
    ada = world["actors"][0]
    apply_decision(world, ada, lambda: {"action": act("play_darts", "darts"), "source": "jev",
                                        "scores": {"pastime": 1.0}, "error": None, **stages})
    assert {key: ada["decision"][key] for key in ada["decision"] if key not in ("source", "scores", "error")} == stages


def metered(preferred: str) -> Any:
    """A fake metered model that prefers one verb and charges ten tokens per candidate."""
    async def evaluate(observation: Any, candidates: Any, settings: Any) -> Any:
        scores = {action["id"]: float(action["verb"] == preferred) for action in candidates}
        return scores, {"input_tokens": 10 * len(candidates), "output_tokens": 0}
    return evaluate


def pastime_evening(evaluators: Evaluators) -> Evening:
    """Let Ada choose for half a minute in the pastime hall."""
    settings = config(typesafe_api_key="fake", temperature=0.25)
    return asyncio.run(run_evening(create_world(pastime_hall(), 2), settings, Random(2), evaluators,
                                   Pace(step=0.1, model_latency=1.0, time_limit=30.0)))


def test_a_recorded_family_stage_replays_to_the_same_evening() -> None:
    records: list[Record] = []
    clock = iter(range(10_000)).__next__
    live = pastime_evening(Evaluators(*(record_calls(kind, metered(verb), records.append, clock, JevError)
                                        for kind, verb in (("actions", "pastime"), ("seats", "sit"),
                                                           ("family", "watch")))))
    stored = parse_records("".join(map(format_record, records)))
    replay = pastime_evening(Evaluators(*(replay_calls(kind, stored, JevError) for kind in ("actions", "seats",
                                                                                         "family"))))
    assert (replay.events, replay.choices) == (live.events, live.choices)
    assert ({item["kind"] for item in records}, {item["kind"] for item in live.choices}) == (
        {"actions", "family"}, {"actions", "family"})


@pytest.mark.parametrize("members", [
    pytest.param(None, id="missing-members"),
    pytest.param([], id="empty-members"),
    pytest.param([act("fly")], id="malformed-member-verb"),
])
def test_a_family_option_without_known_members_cannot_be_asked(members: Any) -> None:
    option = {"id": "pastime", "verb": "pastime", "target_id": None,
              **({} if members is None else {"members": members})}
    with pytest.raises(ValueError, match="member"):
        family_question(option)


def test_a_family_question_carries_its_members_guidance() -> None:
    option = group_families([act("play_darts", "darts"), act("watch", "hearth")])[0]
    instructions = family_question(option)["instructions"]
    assert [phrase for phrase in ("pass the time", ACTIVITIES["play_darts"].guidance, ACTIVITIES["watch"].guidance,
                                  "second decision") if phrase not in instructions] == []
