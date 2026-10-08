"""Whose table is whose, and who is welcome at it."""

from typing import Any

import pytest

from tavern.social.tables import liked


def relation(opinion: float = 0.0, familiarity: str = "acquaintance") -> dict[str, Any]:
    """Describe what Ada thinks of Bea."""
    return {"name": "Bea", "opinion": opinion, "familiarity": familiarity}


@pytest.mark.parametrize("actor, expected", [
    pytest.param({}, False, id="no-relations-at-all"),
    pytest.param({"relations": {"bea": relation(0.0, "stranger")}}, False, id="a-stranger"),
    pytest.param({"relations": {"bea": relation(9.0)}}, False, id="just-below-liked"),
    pytest.param({"relations": {"bea": relation(10.0)}}, True, id="liked"),
    pytest.param({"relations": {"bea": relation(0.0, "friend")}}, True, id="a-friend-of-no-opinion"),
    pytest.param({"relations": {"bea": relation(-40.0, "friend")}}, True, id="an-old-friend-is-still-a-friend"),
    pytest.param({"relations": {"bea": relation(5.0)},
                  "thoughts": [{"kind": "chat", "about": "bea", "text": "x", "mood": 3.0, "opinion": 6.0,
                                "expires_at": 100.0, "source_event": "chat"}]}, True,
                 id="a-pleasant-chat-tips-it"),
    pytest.param({"relations": {"cid": relation(50.0)}}, False, id="liking-someone-else"),
])
def test_a_guest_likes_someone_they_think_well_of_or_count_a_friend(actor: dict[str, Any], expected: bool) -> None:
    assert liked(actor, "bea", 50.0) is expected
