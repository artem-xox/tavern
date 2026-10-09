"""What a scenario's guests carry into the evening."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.evening.scenario import open_evening, parse_scenario
from tavern.mind.cards import parse_cards
from staff_hall import LAYOUT, plan

ROOT = Path(__file__).resolve().parents[1]


def carrying(**fields: Any) -> dict[str, Any]:
    """A two-guest evening in which Ada comes in carrying what the fields say."""
    data = plan(guests=2)
    data["guests"][0].update(fields)
    return data


@pytest.mark.parametrize("carries,expected", [
    pytest.param({"remedy": 2}, {"beer": 0, "remedy": 2, "keepsake": 0}, id="two-remedies"),
    pytest.param({"keepsake": 1, "beer": 1}, {"beer": 1, "remedy": 0, "keepsake": 1}, id="several-kinds"),
    pytest.param({}, {"beer": 0, "remedy": 0, "keepsake": 0}, id="nothing"),
])
def test_a_guest_comes_in_with_what_the_scenario_says_they_carry(carries: dict[str, int],
                                                                  expected: dict[str, int]) -> None:
    world = open_evening(LAYOUT, parse_scenario(carrying(carries=carries)), seed=1)
    guests = {item["id"]: item for item in world["actors"]}
    assert (guests["ada"]["inventory"], guests["bea"]["inventory"]) == (expected, {"beer": 0, "remedy": 0, "keepsake": 0})


def test_a_late_guest_brings_what_they_carry_through_the_door() -> None:
    data = carrying(carries={"remedy": 1}, arrives_at=50)
    world = open_evening(LAYOUT, parse_scenario(data), seed=1)
    assert [item["id"] for item in world["actors"]] == ["bea"]
    assert world["expected"][0]["carries"] == {"remedy": 1}


@pytest.mark.parametrize("carries", [
    pytest.param({"wine": 1}, id="unknown-kind"),
    pytest.param({"remedy": 9}, id="more-than-hands"),
    pytest.param(["remedy"], id="not-a-mapping"),
])
def test_a_scenario_guest_who_carries_something_impossible_is_refused(carries: Any) -> None:
    with pytest.raises(ValueError, match="arries|nventory|remedy|wine"):
        parse_scenario(carrying(carries=carries))


def test_the_first_evening_has_edda_carry_remedies_and_toren_keepsakes() -> None:
    cards = parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])
    scenario = parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()), cards)
    assert {item["name"]: item["carries"] for item in scenario.guests if "carries" in item} == {
        "Edda": {"remedy": 3}, "Toren": {"keepsake": 2}}
