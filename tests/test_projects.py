"""Projects: a plan of several steps a guest takes on with one choice, and carries out without asking again."""

import asyncio
import json
from random import Random
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.body.activities import ACTIVITIES, FAMILIES
from tavern.body.projects import PROJECTS, honor_projects
from tavern.evening.decisions import free_to_decide
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world
from tavern.mind.agents import Evaluators, build_candidates, choose_action
from tavern.mind.local_policy import local_scores
from tavern.social.scenes import conversation_of, start_conversation
from social_hall import actor, advance, command, know, spotted_hall


def newcomer(thirst: float = 80.0) -> dict[str, Any]:
    """Cid stands in the far corner, thirsty, with no seat, knowing the tap and the near table's chairs."""
    data = spotted_hall()
    data["actors"][2].update(x=2, y=6)
    world = create_world(data, 4)
    know(world, "cid", "tap", "w", "e", "n", "near")
    actor(world, "cid")["needs"]["thirst"] = thirst
    return world


def seen_by_cid(world: dict[str, Any]) -> dict[str, Any]:
    """Cid's observation, told that the world has projects."""
    return {**observe_actor(world, "cid"), "people": observe_people(world, "cid"), "projects": ["settle_in"]}


def settle(world: dict[str, Any], chair: str = "n") -> dict[str, Any]:
    """Cid sets out to settle in at a chair."""
    return start_action(world, "cid", command("settle_in", chair))


def events_of(world: dict[str, Any], kind: str) -> list[str]:
    """The messages of the logged events of a kind."""
    return [item["message"] for item in world["events"] if item["type"] == kind]


def test_settling_in_is_a_project_not_an_action_of_its_own() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    cid = actor(world, "cid")
    assert (world["projects"], cid["action"], free_to_decide(world, cid)) == (
        [{"kind": "settle_in", "by": "cid", "target": "n", "step": 0, "of": 3, "running": False,
          "started_at": world["time"]}], None, False)


def test_a_project_is_carried_out_step_by_step_and_ends_in_a_logged_outcome() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    advance(world, 90)
    cid = actor(world, "cid")
    started = [item["message"] for item in world["events"] if item["type"] == "action_started" and item["actor_id"] == "cid"]
    assert (started, cid["seat_id"], cid["inventory"]["beer"], world["projects"], events_of(world, "project_done")) == (
        ["Cid chose take_beer", "Cid chose sit", "Cid chose drink"], "n", 0, [],
        ["Cid settled in with an ale (settle_in)"])
    assert free_to_decide(world, cid)


@pytest.mark.parametrize("spoil, reason", [
    pytest.param(lambda world: next(item for item in world["map"]["objects"] if item["id"] == "tap").update(stock=0),
                 "empty", id="the-tap-runs-dry-before-the-first-step"),
    pytest.param(lambda world: actor(world, "dan").update(x=3, y=1), "taken", id="the-chair-is-taken"),
])
def test_a_step_the_world_refuses_ends_the_project_as_failed(spoil: Any, reason: str) -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    if reason == "taken":
        # Dan takes the chair before Cid can sit on it.
        assert start_action(world, "dan", command("sit", "n"))["accepted"]
        advance(world, 3)
    spoil(world)
    advance(world, 90)
    failed = events_of(world, "project_failed")
    assert (len(failed), failed[0].startswith("Cid could not settle in: "), failed[0].endswith("(settle_in)"),
            world["projects"], free_to_decide(world, actor(world, "cid"))) == (1, True, True, [], True)


def test_an_interrupt_drops_the_project() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    advance(world, 2)
    cid = actor(world, "cid")
    cid.update(interrupted_at=world["time"] + 0.05, action=None, status="idle", path=[])
    advance(world, 1)
    assert (events_of(world, "project_dropped"), world["projects"]) == (
        ["Cid was called away from settling in (settle_in)"], [])


def test_a_project_that_takes_too_long_lapses() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    advance(world, 1)
    actor(world, "cid").update(action=None, status="idle", path=[])
    world["projects"][0]["running"] = False
    world["projects"][0]["started_at"] -= PROJECTS["settle_in"].lasts
    advance(world, 1)
    assert (events_of(world, "project_expired"), world["projects"]) == (["Cid gave up settling in (settle_in)"], [])


def test_the_project_of_a_guest_who_went_home_goes_with_them() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    world["actors"].remove(actor(world, "cid"))
    advance(world, 1)
    assert (world["projects"], [item for item in world["events"] if item["type"].startswith("project_")]) == ([], [])


def test_a_guest_in_a_conversation_is_not_pulled_away_by_the_next_step() -> None:
    world = newcomer()
    assert settle(world)["accepted"]
    started: list[Any] = []

    def start(world: Any, actor_id: str, action: Any) -> dict[str, Any]:
        started.append(action["verb"])
        return {"accepted": True, "reason": None}

    start_conversation(world, actor(world, "dan"), actor(world, "cid"))
    honor_projects(world, start)
    during = list(started)
    world["conversations"].clear()
    honor_projects(world, start)
    assert (during, started) == ([], ["take_beer"])


@pytest.mark.parametrize("prepare, offered", [
    pytest.param(lambda world: None, True, id="seatless-thirsty-guest-who-knows-a-tap-and-a-chair"),
    pytest.param(lambda world: actor(world, "cid")["inventory"].update(beer=1), False, id="already-holding-a-mug"),
    pytest.param(lambda world: actor(world, "cid")["needs"].update(thirst=20.0), False, id="not-thirsty"),
    pytest.param(lambda world: actor(world, "cid").update(seat_id="fw"), False, id="already-seated"),
    pytest.param(lambda world: next(item for item in actor(world, "cid")["knowledge"]["objects"].values()
                                    if item["id"] == "tap").update(stock=0), False, id="tap-seen-dry"),
    pytest.param(lambda world: actor(world, "cid")["knowledge"]["objects"].pop("tap"), False, id="no-tap-known"),
])
def test_settling_in_is_offered_to_a_seatless_thirsty_guest_with_somewhere_to_go(prepare: Any, offered: bool) -> None:
    world = newcomer()
    prepare(world)
    view = seen_by_cid(world)
    found = [item for option in build_candidates(view) for item in option.get("members", [option])
             if item["verb"] == "settle_in"]
    assert bool(found) is offered


def test_settling_in_is_not_offered_where_projects_are_not_on() -> None:
    world = newcomer()
    view = {key: value for key, value in seen_by_cid(world).items() if key != "projects"}
    assert all(item["verb"] != "settle_in" for option in build_candidates(view) for item in option.get("members", [option]))


def test_it_shares_a_family_with_taking_a_beer_and_scores_a_little_above_it() -> None:
    world = newcomer()
    view = seen_by_cid(world)
    [refreshment] = [option for option in build_candidates(view) if option["id"] == "refreshment"]
    scores = local_scores(view, refreshment["members"])
    assert [item["verb"] for item in refreshment["members"]] == ["take_beer", "settle_in"]
    assert scores["settle_in"] - scores["take_beer:tap"] == pytest.approx(0.1)


def test_choosing_it_takes_three_levels_the_family_the_verb_and_the_chair() -> None:
    world = newcomer()
    view = seen_by_cid(world)
    seen: list[str] = []

    def favouring(prefix: str, label: str) -> Any:
        async def evaluate(observation: Any, candidates: Any, settings: Any) -> dict[str, float]:
            seen.append(label)
            return {item["id"]: float(item["id"].startswith(prefix)) for item in candidates}
        return evaluate

    config = {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 1.0, "temperature": 0.0, "projects": True}
    result = asyncio.run(choose_action(view, config, Random(0), Evaluators(
        favouring("refreshment", "actions"), favouring("sit:n", "seats"), family=favouring("settle_in", "family"))))
    assert (result["action"]["id"], seen, result["family"]["name"], "seat" in result) == (
        "settle_in:n", ["actions", "family", "seats"], "refreshment", True)


def test_the_activity_is_in_the_refreshment_family() -> None:
    assert (ACTIVITIES["settle_in"].family, "refreshment" in FAMILIES, ACTIVITIES["settle_in"].duration) == (
        "refreshment", True, None)


def saved_mid_project(tmp_path: Any, mutate: Any = None) -> Any:
    world = newcomer()
    assert settle(world)["accepted"]
    advance(world, 5)
    path = tmp_path / "world.json"
    save_world(world, path)
    if mutate:
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))
    return path


def test_a_project_survives_a_save(tmp_path: Any) -> None:
    world = load_world(saved_mid_project(tmp_path))
    advance(world, 90)
    assert events_of(world, "project_done") == ["Cid settled in with an ale (settle_in)"]


@pytest.mark.parametrize("mutate", [
    pytest.param(lambda data: data["projects"][0].update(kind="dance"), id="unknown-kind"),
    pytest.param(lambda data: data["projects"][0].update(step=3), id="step-past-the-last"),
    pytest.param(lambda data: data["projects"][0].update(step=-1), id="negative-step"),
    pytest.param(lambda data: data["projects"][0].update(of=2), id="step-count-that-is-not-the-kinds"),
    pytest.param(lambda data: data["projects"][0].update(by="eve"), id="a-missing-guest"),
    pytest.param(lambda data: data["projects"][0].update(running="yes"), id="running-not-a-bool"),
    pytest.param(lambda data: data["projects"][0].update(target="tap"), id="target-that-is-not-a-chair"),
    pytest.param(lambda data: data["projects"][0].update(started_at=1e9), id="started-in-the-future"),
    pytest.param(lambda data: data["projects"].append(dict(data["projects"][0])), id="two-projects-of-one-guest"),
    pytest.param(lambda data: data.pop("projects"), id="projects-missing"),
])
def test_a_saved_project_that_is_not_one_is_rejected(tmp_path: Any, mutate: Any) -> None:
    with pytest.raises(ValueError):
        load_world(saved_mid_project(tmp_path, mutate))


@pytest.mark.parametrize("chair, prepare", [
    pytest.param("tap", None, id="a-target-that-is-no-chair"),
    pytest.param("n", lambda world: actor(world, "cid")["inventory"].update(beer=1), id="a-mug-in-hand"),
    pytest.param("n", lambda world: actor(world, "cid")["knowledge"]["objects"].pop("tap"), id="no-tap-known"),
])
def test_a_project_that_cannot_begin_is_refused(chair: str, prepare: Any) -> None:
    world = newcomer()
    if prepare:
        prepare(world)
    assert (settle(world, chair)["accepted"], world["projects"]) == (False, [])
