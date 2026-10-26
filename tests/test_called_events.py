"""A wrong that calls for an answer is logged once, when the wronged guest first has the thought."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.hall.world import create_world
from tavern.social.thoughts import think
from social_hall import actor, advance, hall


def called_events(world: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in world["events"] if item["type"] == "called"]


def wronged(kind: str, about: str | None) -> dict[str, Any]:
    """Ada thinks a thought of `kind` about someone, in a hall that has run on for a second."""
    world = create_world(hall(), 4)
    ada = actor(world, "ada")
    think(ada, kind, world["time"], "x", "x", about=actor(world, about) if about else None)
    advance(world, 1)
    return world


@pytest.mark.parametrize("kind, about, expected", [
    pytest.param("insulted", "bea", 1, id="an-insult-calls-for-an-answer"),
    pytest.param("lost_at_dice", "cid", 1, id="a-loss-calls-for-an-answer"),
    pytest.param("chat", "bea", 0, id="a-chat-calls-for-none"),
    pytest.param("insulted", None, 0, id="a-thought-about-nobody"),
])
def test_a_thought_that_calls_for_an_answer_is_logged_once(kind: str, about: str | None, expected: int) -> None:
    world = wronged(kind, about)
    advance(world, 5)
    assert len(called_events(world)) == expected


def test_the_event_belongs_to_the_wronged_guest_and_names_the_wrong() -> None:
    event = called_events(wronged("insulted", "bea"))[0]
    assert (event["actor_id"], event["message"]) == ("ada", "Ada is called to answer Bea, who insulted them")


def test_a_called_mark_survives_a_save() -> None:
    world = wronged("insulted", "bea")
    assert actor(world, "ada")["thoughts"][0]["called"] is True
    assert parse_world(json.dumps(world)) == world
