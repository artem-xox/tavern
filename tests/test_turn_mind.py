"""A turn writer sees who the speaker is and what they feel about the company: the speaker's side of `turn_view`."""

from typing import Any

import pytest

from tavern.scenes import conversation_of
from tavern.thoughts import think
from tavern.turns import turn_view
from tavern.world import create_world, start_action

CARD = {"id": "ada", "sprite": "visitor", "name": "Ada", "occupation": "salt trader",
        "background": "Ada drives salt over the pass.", "temperament": "Warm but shrewd.",
        "speech": "Quick, full of prices.", "quirks": "Counts coins aloud.", "secret": "She owes the miller.",
        "goal": "Sell her last sack of salt.", "params": {}}


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def scene_world(card: dict[str, Any] | None) -> dict[str, Any]:
    """Seat Ada (with the card, if any), Bea and Cid at one table; Ada talks to Bea and Cid joins."""
    world = create_world({"width": 8, "height": 5, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2, "width": 2, "height": 1},
        chair("west", 2, 2), chair("east", 5, 2), chair("north", 3, 1)],
        "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2, "card": card},
                   {"id": "bea", "name": "Bea", "x": 5, "y": 2}, {"id": "cid", "name": "Cid", "x": 3, "y": 1}]}, 3)
    for actor_id, seat in (("ada", "west"), ("bea", "east"), ("cid", "north")):
        assert start_action(world, actor_id, {"id": f"sit:{seat}", "verb": "sit", "target_id": seat})["accepted"]
        people(world)[actor_id]["needs"]["social"] = 90.0
    assert start_action(world, "ada", {"id": "talk:bea", "verb": "talk", "target_id": "bea"})["accepted"]
    assert start_action(world, "cid", {"id": "join_conversation:ada", "verb": "join_conversation",
                                       "target_id": "ada"})["accepted"]
    return world


def people(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Guests by ID."""
    return {item["id"]: item for item in world["actors"]}


def speaker_view(world: dict[str, Any]) -> dict[str, Any]:
    """The view of the scene's first turn: Ada speaks."""
    return turn_view(world, conversation_of(world, "ada"))["speaker"]


@pytest.mark.parametrize("card, expected", [
    pytest.param(None, None, id="no-card"),
    pytest.param(CARD, {key: CARD[key] for key in ("name", "occupation", "background", "temperament", "speech",
                                                    "quirks", "secret", "goal")}, id="card-words-only"),
])
def test_speaker_card_words_are_in_the_view(card: dict[str, Any] | None, expected: dict[str, str] | None) -> None:
    me = speaker_view(scene_world(card))
    assert me["card"] == expected
    assert ("salt trader" in me["portrait"]) == (card is not None)


@pytest.mark.parametrize("quarrels, chats, opinions", [
    pytest.param(0, 0, {"bea": 0.0, "cid": 0.0}, id="empty-no-thoughts"),
    pytest.param(1, 0, {"bea": -20.0, "cid": 0.0}, id="single-quarrel"),
    pytest.param(2, 1, {"bea": -40.0, "cid": 6.0}, id="duplicate-quarrels-stack"),
])
def test_company_lists_opinions_and_thoughts_about_those_present(quarrels: int, chats: int,
                                                                 opinions: dict[str, float]) -> None:
    world = scene_world(None)
    ada, bea, cid = (people(world)[key] for key in ("ada", "bea", "cid"))
    for _ in range(quarrels):
        think(ada, "quarrel", world["time"], "Quarreled with Bea about ale", "quarrel", about=bea)
    for _ in range(chats):
        think(ada, "chat", world["time"], "Chatted with Cid about the road", "chat", about=cid)
    company = speaker_view(world)["company"]
    assert {item["id"]: item["opinion"] for item in company} == opinions
    assert [item["thoughts"] for item in company] == [["Quarreled with Bea about ale"] * quarrels,
                                                      ["Chatted with Cid about the road"] * chats]
    assert [item["familiarity"] for item in company] == [
        "acquaintance" if quarrels else "stranger", "acquaintance" if chats else "stranger"]


@pytest.mark.parametrize("level, feelings_mention_drink", [
    pytest.param(0.0, False, id="sober"),
    pytest.param(0.5, False, id="drunk-speech-kept-apart"),
])
def test_drink_is_given_apart_from_feelings(level: float, feelings_mention_drink: bool) -> None:
    world = scene_world(None)
    people(world)["ada"]["drunkenness"] = level
    me = speaker_view(world)
    assert (me["drunkenness"], "drunk" in me["feelings"]) == (level, feelings_mention_drink)
    assert me["feelings"].startswith("They are in")


def test_malformed_speaker_fails_loudly() -> None:
    world = scene_world(None)
    del people(world)["ada"]["drunkenness"]
    with pytest.raises(KeyError):
        speaker_view(world)
