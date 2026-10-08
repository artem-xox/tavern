"""Plain-language briefings give the evaluator a visitor's situation and options."""

from typing import Any, Callable

import pytest

from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world
from tavern.social.thoughts import think


def table(table_id: str, name: str, x: int, y: int) -> list[dict[str, Any]]:
    """Build a one-cell table with a chair on each side."""
    def chair(side: str, dx: int) -> dict[str, Any]:
        return {"id": f"{table_id}-{side}", "kind": "chair", "name": f"{name} · {side}", "x": x + dx, "y": y,
                "walkable": True, "table_id": table_id, "interaction_spots": [[x + dx, y]]}
    return [{"id": table_id, "kind": "table", "name": name, "x": x, "y": y}, chair("west", -1), chair("east", 1)]


def tavern() -> dict[str, Any]:
    """Build a small hall: a door, a tap, darts, a fireplace and two two-seat tables."""
    return {"width": 12, "height": 9, "blocked": [[x, 8] for x in range(12) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Front door", "x": 5, "y": 8, "interaction_spots": [[5, 7]]},
        {"id": "tap", "kind": "tap", "name": "House ale", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 7},
        {"id": "darts", "kind": "darts", "name": "Darts", "x": 11, "y": 6, "interaction_spots": [[10, 6]]},
        {"id": "fireplace", "kind": "fireplace", "name": "Fireplace", "x": 9, "y": 0, "appeal": 0.5, "reach": 3,
         "interaction_spots": [[9, 1]]},
        *table("hearth", "Hearth table", 9, 3), *table("plain", "Plain table", 3, 4),
    ], "actors": [
        {"id": "ada", "name": "Ada", "x": 4, "y": 7, "traits": {"patience": 0.2, "comfort": 0.9, "curiosity": 0.5}},
        {"id": "bea", "name": "Bea", "x": 6, "y": 7},
    ], "arrival": {"needs": {"thirst": [60, 60]}}}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance physical state without requesting decisions."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def look(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Observe a visitor the way the runtime does before a decision."""
    return {**observe_actor(world, actor_id), "people": observe_people(world, actor_id)}


def newcomer() -> dict[str, Any]:
    """Observe Ada just inside the door."""
    return look(create_world(tavern()), "ada")


def settled() -> dict[str, Any]:
    """Observe Ada seated at the hearth with a beer, Bea opposite, after a slight from Bea."""
    world = create_world(tavern())
    for actor_id, seat in (("ada", "hearth-west"), ("bea", "hearth-east")):
        assert start_action(world, actor_id, {"id": "sit", "verb": "sit", "target_id": seat})["accepted"]
    advance(world, 20)
    ada, bea = world["actors"][0], world["actors"][1]
    ada["inventory"]["beer"] = 1
    think(ada, "quarrel", world["time"], "Quarreled with Bea about the inn's beer", "quarrel", about=bea)
    return look(world, "ada")


@pytest.mark.parametrize("scene, field, phrase", [
    pytest.param(newcomer, "situation", "just arrived", id="newcomer-has-just-arrived"),
    pytest.param(newcomer, "situation", "not chosen a seat", id="newcomer-has-no-seat-yet"),
    pytest.param(newcomer, "situation", "short-tempered", id="temperament-in-words"),
    pytest.param(newcomer, "situation", "Bea", id="people-in-sight"),
    pytest.param(newcomer, "take_beer:tap", "7 servings", id="tap-stock-when-last-seen"),
    pytest.param(newcomer, "leave:door", "go home", id="leaving-means-going-home"),
    pytest.param(newcomer, "seating", "Hearth table", id="seating-names-the-free-tables"),
    pytest.param(newcomer, "situation", "Hearth table (by the fire", id="the-fire-table-is-named-by-its-fire"),
    pytest.param(settled, "situation", "holding a full mug", id="mug-in-hand"),
    pytest.param(settled, "situation", "Hearth table · west", id="own-seat-by-name"),
    pytest.param(settled, "situation", "Quarreled with Bea", id="a-slight-still-rankles"),
    pytest.param(settled, "sit:hearth-west", "stay", id="own-seat-means-staying-put"),
    pytest.param(settled, "talk:bea", "across the table", id="talk-partner-at-the-table"),
    pytest.param(settled, "drink", "sip", id="drinking-seated"),
])
def test_briefing_puts_the_situation_into_words(scene: Callable[[], dict[str, Any]], field: str, phrase: str) -> None:
    observation = scene()
    briefing = brief(observation, build_candidates(observation))
    assert phrase in (briefing["situation"] if field == "situation" else briefing["options"][field])


@pytest.mark.parametrize("field", [
    pytest.param("situation", id="tables-in-the-situation"),
    pytest.param("seating", id="tables-in-the-seating-option"),
])
def test_briefing_gives_no_appeal_numbers(field: str) -> None:
    observation = newcomer()
    briefing = brief(observation, build_candidates(observation))
    assert "appeal" not in (briefing["situation"] if field == "situation" else briefing["options"][field])


def test_briefing_lists_the_tables_nearest_first() -> None:
    observation = newcomer()
    situation = brief(observation, build_candidates(observation))["situation"]
    assert situation.index("Plain table") < situation.index("Hearth table")


@pytest.mark.parametrize("candidates, expected", [
    pytest.param([], [], id="empty-candidates"),
    pytest.param([{"id": "wait", "verb": "wait", "target_id": None}], ["wait"], id="single-option"),
    pytest.param([{"id": "wait", "verb": "wait", "target_id": None}] * 2, ["wait"], id="duplicate-option"),
])
def test_briefing_describes_each_option_once(candidates: list[dict[str, Any]], expected: list[str]) -> None:
    assert sorted(brief(newcomer(), candidates)["options"]) == expected


def test_unknown_option_cannot_be_briefed() -> None:
    with pytest.raises(ValueError):
        brief(newcomer(), [{"id": "fly", "verb": "fly", "target_id": None}])
