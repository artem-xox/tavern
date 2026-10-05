"""How a guest's sociability tilts the local policy's taste for company."""

from typing import Any

import pytest

from tavern.mind.local_policy import local_scores


def observation(sociability: float | None, social: float = 50) -> dict[str, Any]:
    """A calm guest with nothing pressing; `sociability` None leaves the trait off the record."""
    traits = {} if sociability is None else {"sociability": sociability}
    return {"actor": {"id": "ada", "name": "Ada", "traits": traits, "inventory": {"beer": 0}, "visit": {},
                      "needs": {"thirst": 0, "fatigue": 0, "bladder": 0, "social": social, "boredom": 0}},
            "objects": [], "people": [], "invitations": []}


def score(verb: str, sociability: float | None, social: float = 50) -> float:
    """The local score of one company-seeking action."""
    action = {"id": f"{verb}:x", "verb": verb, "target_id": "x"}
    return local_scores(observation(sociability, social), [action])[action["id"]]


@pytest.mark.parametrize("verb", [
    pytest.param("talk", id="start-a-chat"),
    pytest.param("join_conversation", id="join-a-chat"),
    pytest.param("stand_at_bar", id="chat-at-the-bar"),
])
def test_the_sociable_seek_company_more_than_loners(verb: str) -> None:
    assert score(verb, 0.9) > score(verb, 0.5) > score(verb, 0.1)


@pytest.mark.parametrize("verb", [
    pytest.param("talk", id="start-a-chat"),
    pytest.param("join_conversation", id="join-a-chat"),
    pytest.param("stand_at_bar", id="chat-at-the-bar"),
])
def test_a_guest_without_the_trait_is_ordinary(verb: str) -> None:
    assert score(verb, None) == pytest.approx(score(verb, 0.5))


@pytest.mark.parametrize("sociability, social", [
    pytest.param(1.0, 100, id="most-sociable-and-lonely"),
    pytest.param(0.0, 0, id="loner-with-company-enough"),
])
def test_scores_stay_within_zero_and_one(sociability: float, social: float) -> None:
    assert all(0.0 <= score(verb, sociability, social) <= 1.0 for verb in ("talk", "join_conversation", "stand_at_bar"))
