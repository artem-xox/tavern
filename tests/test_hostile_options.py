"""Hostile options in a guest's choice: offered only after a grudge, as one family, weighed low, told plainly."""

from typing import Any

import pytest

from tavern.body.activities import FAMILIES
from tavern.mind.agents import build_candidates
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.mind.options import family_text, option_text
from hostile_view import QUARREL, view

HOSTILE = ("shove", "start_fight")


def offered(observation: dict[str, Any]) -> list[Any]:
    """The first-stage options a guest is offered: an action's ID, or a family's with its members' IDs."""
    return [option["id"] if "members" not in option else (option["id"], [item["id"] for item in option["members"]])
            for option in build_candidates(observation)]


@pytest.mark.parametrize("observation", [
    pytest.param(view(), id="no-grudge"),
    pytest.param(view(QUARREL, temper=0.3, opinion=-40.0), id="a-grudge-but-a-calm-temper"),
    pytest.param(view(QUARREL, opinion=-40.0, closed=True), id="the-inn-has-closed"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[]), id="nobody-in-sight"),
])
def test_peaceful_requests_hold_no_confront_family(observation: dict[str, Any]) -> None:
    options = offered(observation)
    assert not [option for option in options if option == "confront" or "shove" in str(option)
                or "start_fight" in str(option)]


@pytest.mark.parametrize("observation, expected", [
    pytest.param(view(QUARREL, opinion=-40.0), "shove:bea", id="a-sober-hothead-may-only-shove"),
    pytest.param(view(QUARREL, opinion=-40.0, temper=1.0), ("confront", ["shove:bea", "start_fight:bea"]),
                 id="a-furious-guest-may-also-fight"),
])
def test_a_grudge_offers_the_hostile_acts_as_one_family(observation: dict[str, Any], expected: Any) -> None:
    assert expected in offered(observation)


def test_hostile_acts_come_after_the_peaceful_ones_and_leave_them_alone() -> None:
    peaceful, hostile = offered(view()), offered(view(QUARREL, opinion=-40.0))
    assert hostile == [*peaceful, "shove:bea"]


def scores(**fields: Any) -> tuple[float, float]:
    """What Ada would score a shove and a fight of Bea's, from the temper and drink given."""
    observation = view(QUARREL, opinion=-40.0, **fields)
    actions = [{"id": f"{verb}:bea", "verb": verb, "target_id": "bea"} for verb in HOSTILE]
    result = local_scores(observation, actions)
    return result["shove:bea"], result["start_fight:bea"]


@pytest.mark.parametrize("fields, expected", [
    pytest.param({"temper": 0.2}, (0.16, 0.09), id="calm"),
    pytest.param({"temper": 0.5}, (0.25, 0.15), id="touchy"),
    pytest.param({"temper": 0.5, "drunkenness": 0.5}, (0.355, 0.22), id="touchy-and-drunk"),
    pytest.param({"temper": 1.0, "drunkenness": 0.9}, (0.4, 0.25), id="urge-is-capped-at-one"),
])
def test_hostile_acts_score_low_and_rise_with_the_urge(fields: dict[str, float], expected: tuple[float, float]) -> None:
    assert scores(**fields) == pytest.approx(expected)


def test_a_guest_who_is_resting_still_prefers_her_seat_to_a_shove() -> None:
    observation = view(QUARREL, opinion=-40.0, temper=1.0, drunkenness=0.9)
    actions = [{"id": "sit:w", "verb": "sit", "target_id": "w"}, {"id": "shove:bea", "verb": "shove",
                                                                    "target_id": "bea"}]
    result = local_scores(observation, actions)
    assert result["sit:w"] > result["shove:bea"]


@pytest.mark.parametrize("verb, expected", [
    pytest.param("shove", "shove Bea, who sits at their table, hard enough that the whole room turns to look "
                          "(a rough act, and Bea will not forget it)", id="shove"),
    pytest.param("start_fight", "pick a fight with Bea, who sits at their table: a brawl the whole room will hear, "
                                "which Bea will not forget and which may leave someone hurt", id="start-fight"),
])
def test_options_tell_what_a_hostile_act_costs(verb: str, expected: str) -> None:
    assert option_text(view(QUARREL, opinion=-40.0), {"id": f"{verb}:bea", "verb": verb, "target_id": "bea"}) == expected


def test_a_guest_beside_the_target_is_told_so() -> None:
    observation = view(QUARREL, opinion=-40.0, people=[{"id": "bea", "name": "Bea", "x": 3, "y": 2, "seat_id": None,
                                                        "table_id": None, "beside": True}])
    assert "who stands beside them" in option_text(observation, {"id": "shove:bea", "verb": "shove",
                                                                 "target_id": "bea"})


def test_the_briefing_offers_the_family_in_words() -> None:
    observation = view(QUARREL, opinion=-40.0, temper=1.0)
    options = build_candidates(observation)
    family = next(option for option in options if option["id"] == "confront")
    text = family_text(observation, family)
    assert text.startswith(f"{FAMILIES['confront']}: shove Bea") and "pick a fight with Bea" in text
    assert brief(observation, options)["options"]["confront"] == text
