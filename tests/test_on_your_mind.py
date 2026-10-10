"""What a writer is shown a speaker has on their mind about someone: chats merged, and the other as the speaker calls them now."""

from typing import Any

import pytest

from tavern.mind.intentions import intention_view
from tavern.social.thoughts import think
from test_turn_mind import people, scene_world, speaker_view


def cid_thoughts(texts: list[tuple[str, str]], knows_name: bool = True) -> list[str]:
    """Give Ada thoughts (kind, text) about Cid, a rider she may know the name of, and show what is on her mind."""
    world = scene_world(None)
    ada, cid = people(world)["ada"], people(world)["cid"]
    cid["card"] = {"looks": "the lean rider"}
    for kind, text in texts:
        think(ada, kind, world["time"], text, kind, about=cid)
    ada["relations"].setdefault("cid", {"opinion": 0.0, "familiarity": "acquaintance"})["knows_name"] = knows_name
    return next(item["thoughts"] for item in speaker_view(world)["company"] if item["id"] == "cid")


@pytest.mark.parametrize("texts, expected", [
    pytest.param([("chat", "Chatted with Cid about the road")], ["Chatted with Cid about the road"], id="one-chat"),
    pytest.param([("chat", "Chatted with Cid about the road"), ("chat", "Chatted with Cid about ale"),
                  ("chat", "Chatted with Cid about darts")], ["Chatted with Cid about the road, ale and darts"],
                 id="three-chats-in-one-line"),
    pytest.param([("chat", "Chatted with Cid about ale"), ("chat", "Chatted with Cid about ale")],
                 ["Chatted with Cid about ale"], id="the-same-topic-twice"),
    pytest.param([("chat", "Chatted with Cid about ale"), ("quarrel", "Quarreled with Cid about a seat"),
                  ("chat", "Chatted with Cid about darts")],
                 ["Chatted with Cid about ale and darts", "Quarreled with Cid about a seat"],
                 id="other-thoughts-stay-as-they-are"),
    pytest.param([("chat", "Had a pleasant chat")], ["Had a pleasant chat"], id="a-chat-in-other-words-is-left-alone"),
    pytest.param([("chat", "Chatted with the lean rider about the road"), ("chat", "Chatted with Cid about ale")],
                 ["Chatted with Cid about the road and ale"], id="named-as-the-speaker-calls-them-now"),
])
def test_chats_about_one_person_are_one_line_naming_them_as_the_speaker_does(texts: list[tuple[str, str]],
                                                                            expected: list[str]) -> None:
    assert cid_thoughts(texts) == expected


def test_someone_whose_name_is_not_known_is_still_called_by_their_looks() -> None:
    assert cid_thoughts([("chat", "Chatted with Cid about the road"), ("chat", "Chatted with Cid about ale")],
                        knows_name=False) == ["Chatted with the lean rider about the road and ale"]


def test_a_guest_taking_stock_has_their_chats_merged_too() -> None:
    world = scene_world(None)
    ada, cid = people(world)["ada"], people(world)["cid"]
    for topic in ("the road", "ale"):
        think(ada, "chat", world["time"], f"Chatted with Cid about {topic}", "chat", about=cid)
    think(ada, "quarrel", world["time"], "Quarreled with Bea about a seat", "quarrel", about=people(world)["bea"])
    view = intention_view(world, ada, {"kind": "interval", "text": "A pause", "time": world["time"]})
    assert view["thoughts"] == ["Chatted with Cid about the road and ale", "Quarreled with Bea about a seat"]
