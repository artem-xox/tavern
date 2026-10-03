"""Thoughts at work: events cause them, and the briefing, leaving, hearing, inspector and saves read them."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import choose_action
from tavern.server.runtime import TavernRuntime
from tavern.mind.briefing import brief
from tavern.hall.memory import record_event
from tavern.adapters.persistence import load_world, save_world
from tavern.social.thoughts import THOUGHTS, familiarity_of, opinion_of, think
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world


def table_room() -> dict[str, Any]:
    """Build a room with a door and a table whose two chairs hold Ada and Bea."""
    def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
        return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
                "table_id": "table", "interaction_spots": [[x, y]]}
    return {"width": 8, "height": 6, "tile_size": 32, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2}, chair("west", 2, 2), chair("east", 4, 2),
        {"id": "door", "kind": "door", "name": "Door", "x": 7, "y": 5, "interaction_spots": [[6, 5]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 4, "y": 2}]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a visitor."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def seated(beers: int = 0) -> dict[str, Any]:
    """Seat Ada and Bea at the table; with beers, impatient and sure to quarrel when they talk."""
    world = create_world(table_room())
    for actor_id, seat in (("ada", "west"), ("bea", "east")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    world["rules"].update(quarrel_per_beer=1.0, quarrel_max=1.0)
    for guest in world["actors"]:
        guest["visit"]["beers"], guest["traits"]["patience"] = beers, 0.0
    return world


def took_seat() -> dict[str, Any]:
    """Bea takes Ada's own seat while Ada stands."""
    world = seated()
    advance(world, 15)
    assert start_action(world, "ada", command("leave", "door"))["accepted"]
    assert start_action(world, "bea", command("sit", "west"))["accepted"]
    advance(world, 3)
    return world


def talked(beers: int) -> Callable[[], dict[str, Any]]:
    """Ada talks to Bea; sober they chat, after beers they quarrel."""
    def scene() -> dict[str, Any]:
        world = seated(beers)
        assert start_action(world, "ada", command("talk", "bea"))["accepted"]
        advance(world, 9)
        return world
    return scene


@pytest.mark.parametrize("scene, kind, familiarity", [
    pytest.param(took_seat, "seat_taken", "stranger", id="a-taken-seat"),
    pytest.param(talked(3), "quarrel", "acquaintance", id="a-quarrel"),
    pytest.param(talked(0), "chat", "acquaintance", id="a-pleasant-chat"),
])
def test_events_leave_thoughts_about_who_caused_them(scene: Callable[[], dict[str, Any]], kind: str,
                                                     familiarity: str) -> None:
    world = scene()
    ada = actor(world, "ada")
    assert ([(item["kind"], item["about"]) for item in ada["thoughts"]], familiarity_of(ada, "bea"),
            opinion_of(ada, "bea", world["time"])) == ([(kind, "bea")], familiarity, THOUGHTS[kind].opinion)


def test_thoughts_are_forgotten_once_they_expire() -> None:
    world = took_seat()
    ada = actor(world, "ada")
    world["time"] = ada["thoughts"][0]["expires_at"]
    step_world(world, 0.1)
    assert (ada["thoughts"], ada["visit"]["grievances"], opinion_of(ada, "bea", world["time"])) == ([], [], 0.0)


def look(world: dict[str, Any], actor_id: str = "ada") -> dict[str, Any]:
    """Observe a visitor the way the runtime does before a decision."""
    return {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}


def sour() -> dict[str, Any]:
    """Ada, seated, after Bea took her seat and quarreled with her."""
    world = seated()
    ada, bea = actor(world, "ada"), actor(world, "bea")
    think(ada, "seat_taken", world["time"], "Bea took my seat", "Bea took Ada's seat", about=bea)
    think(ada, "quarrel", world["time"], "Quarreled with Bea about darts", "Ada and Bea quarreled", about=bea)
    return look(world)


def among_friends() -> dict[str, Any]:
    """Ada, seated across from her old friend Bea."""
    world = seated()
    actor(world, "ada")["relations"]["bea"] = {"name": "Bea", "opinion": 50.0, "familiarity": "friend"}
    return look(world)


@pytest.mark.parametrize("scene, phrase", [
    pytest.param(sour, "They are in a foul mood", id="mood-in-words"),
    pytest.param(sour, "They dislike Bea, who quarreled with them", id="opinion-with-its-latest-reason"),
    pytest.param(sour, "Bea took my seat", id="grievances-still-listed"),
    pytest.param(among_friends, "They are in an even mood", id="calm-mood"),
    pytest.param(among_friends, "They like Bea, an old friend", id="old-friend"),
])
def test_briefing_tells_mood_and_opinions(scene: Callable[[], dict[str, Any]], phrase: str) -> None:
    assert phrase in brief(scene(), [])["situation"]


def view(thoughts: list[dict[str, Any]], time: float) -> dict[str, Any]:
    """Observe Ada two minutes in, middling needs, impatient, with only the door in mind."""
    needs = {"thirst": 40, "fatigue": 40, "bladder": 40, "social": 10, "boredom": 10}
    own = {"id": "ada", "name": "Ada", "x": 5, "y": 5, "inventory": {"beer": 0}, "needs": needs,
           "traits": {"patience": 0.3, "comfort": 0.5, "curiosity": 0.5}, "favorite_seat_id": None,
           "visit": {"seconds": 120.0, "beers": 0, "grievances": []}, "thoughts": thoughts, "relations": {}}
    door = {"id": "door", "kind": "door", "x": 5, "y": 9, "reserved_by": None}
    return {"actor": own, "objects": [door], "visitors": [], "memory": [], "time": time}


def quarrels(count: int) -> list[dict[str, Any]]:
    """Ada's thoughts after quarreling with Bea a number of times at the start of the evening."""
    rule = THOUGHTS["quarrel"]
    return [{"kind": "quarrel", "about": "bea", "text": "Quarreled with Bea", "mood": rule.mood,
             "opinion": rule.opinion, "expires_at": rule.seconds, "source_event": "quarrel"}] * count


@pytest.mark.parametrize("thoughts, time, leaves", [
    pytest.param([], 120.0, False, id="no-thoughts-stays"),
    pytest.param(quarrels(1), 120.0, False, id="single-quarrel-stays"),
    pytest.param(quarrels(2), 120.0, True, id="duplicate-quarrels-walk-out"),
    pytest.param(quarrels(2), THOUGHTS["quarrel"].seconds, False, id="forgotten-quarrels-stay"),
])
def test_bad_thoughts_send_a_guest_home(thoughts: list[dict[str, Any]], time: float, leaves: bool) -> None:
    result = asyncio.run(choose_action(view(thoughts, time), {"typesafe_api_key": None, "temperature": 0.0},
                                       Random(0)))
    assert (result["action"]["verb"] == "leave") == leaves


def test_the_inspector_lists_thoughts_and_opinions(tmp_path: Path) -> None:
    runtime = TavernRuntime(table_room(), tmp_path / "save.json", {"typesafe_api_key": None})
    ada, bea = runtime.world["actors"]
    think(ada, "seat_taken", 0.0, "Bea took my seat", "Bea took Ada's seat", about=bea)
    mind = runtime.snapshot()["minds"]["ada"]
    assert ([item["text"] for item in mind["thoughts"]], mind["opinions"], mind["mood"]) == (
        ["Bea took my seat"], [{"id": "bea", "name": "Bea", "opinion": THOUGHTS["seat_taken"].opinion,
                                "familiarity": "stranger"}], THOUGHTS["seat_taken"].mood)


def open_hall() -> dict[str, Any]:
    """Ada idles at one end of an open hall; Bea and Cid stand 14 and 15 cells away."""
    guests = [{"id": "ada", "name": "Ada", "x": 0, "y": 1}, {"id": "bea", "name": "Bea", "x": 14, "y": 1},
              {"id": "cid", "name": "Cid", "x": 15, "y": 1}]
    return create_world({"width": 30, "height": 3, "blocked": [], "objects": [], "actors": guests})


@pytest.mark.parametrize("familiarity, interrupted", [
    pytest.param(None, False, id="strangers-quarrel-draws-a-glance"),
    pytest.param("acquaintance", False, id="acquaintances-quarrel-draws-a-glance"),
    pytest.param("friend", True, id="a-friends-quarrel-turns-her-head"),
])
def test_a_friends_quarrel_matters_more(familiarity: str | None, interrupted: bool) -> None:
    world = open_hall()
    if familiarity:
        actor(world, "ada")["relations"]["bea"] = {"name": "Bea", "opinion": 0.0, "familiarity": familiarity}
    for actor_id in ("bea", "cid"):
        record_event(world, actor(world, actor_id), "quarrel", "Bea and Cid quarreled about the inn's beer")
    step_world(world, 0.1)
    assert (actor(world, "ada")["interrupted_at"] is not None) == interrupted


def test_thoughts_and_relations_survive_save_and_load(tmp_path: Path) -> None:
    world = took_seat()
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -40.0, "familiarity": "acquaintance"}
    save_world(world, tmp_path / "world.json")
    assert load_world(tmp_path / "world.json") == world


def first_thought(world: dict[str, Any]) -> dict[str, Any]:
    """Ada's first thought, to corrupt."""
    return actor(world, "ada")["thoughts"][0]


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: actor(world, "ada").update(thoughts={}), id="malformed-thoughts"),
    pytest.param(lambda world: first_thought(world).update(kind="envy"), id="unknown-thought-kind"),
    pytest.param(lambda world: first_thought(world).pop("expires_at"), id="thought-without-expiry"),
    pytest.param(lambda world: first_thought(world).update(mood="sour"), id="non-numeric-mood"),
    pytest.param(lambda world: actor(world, "ada").update(relations=[]), id="malformed-relations"),
    pytest.param(lambda world: actor(world, "ada")["relations"]["bea"].update(familiarity="lover"),
                 id="unknown-familiarity"),
    pytest.param(lambda world: actor(world, "ada")["relations"]["bea"].update(opinion=101), id="opinion-out-of-range"),
])
def test_corrupt_thoughts_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = took_seat()
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")
