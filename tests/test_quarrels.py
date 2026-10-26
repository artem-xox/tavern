"""How hot a quarrel has run: the length of the insult run that ends a scene."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.social.quarrels import BOIL, heat
from social_hall import actor, advance, say, scene_of as scene_in, seated_talk


def turn(speaker: str, act: str, addressee: str | None) -> dict[str, Any]:
    """Build a spoken turn; the words and the time do not matter to the heat."""
    return {"speaker": speaker, "addressee": addressee, "line": "Well now.", "act": act, "time": 0.0}


def scene_of(*turns: dict[str, Any]) -> dict[str, Any]:
    """Build a scene holding only the turns."""
    return {"turns": list(turns)}


@pytest.mark.parametrize("turns, expected", [
    pytest.param([], 0, id="no-turns"),
    pytest.param([turn("ada", "insult", "bea")], 1, id="one-insult"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada")], 2, id="two-traded"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("ada", "insult", "bea"),
                  turn("bea", "insult", "ada")], 4, id="four-traded"),
    pytest.param([turn("ada", "greet", "bea"), turn("bea", "insult", "ada")], 1, id="insult-after-a-greeting"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("ada", "remark", "bea")], 0,
                 id="other-act-last"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "remark", "ada"), turn("ada", "insult", "bea"),
                  turn("bea", "insult", "ada")], 2, id="other-act-breaks-the-run"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", "ada"), turn("cid", "insult", "ada")], 1,
                 id="third-speaker-starts-a-new-run"),
    pytest.param([turn("ada", "insult", "bea"), turn("ada", "insult", "bea")], 1, id="same-speaker-twice"),
    pytest.param([turn("ada", "insult", "bea"), turn("bea", "insult", None)], 0, id="insult-to-everyone-last"),
    pytest.param([turn("ada", "insult", None), turn("bea", "insult", "ada")], 1, id="insult-to-everyone-breaks-the-run"),
])
def test_heat_is_the_insult_run_ending_the_scene(turns: list[dict[str, Any]], expected: int) -> None:
    assert heat(scene_of(*turns)) == expected


def foes(world: dict[str, Any]) -> None:
    """Ada and Bea think ill of each other, so each may insult the other and answers in kind."""
    for one, other in (("ada", "bea"), ("bea", "ada")):
        actor(world, one)["relations"][other] = {"name": other.title(), "opinion": -40.0, "familiarity": "acquaintance"}


def hot(world: dict[str, Any], guest: str, temper: float, drunkenness: float) -> None:
    """Give a guest a temper and a measure of drink."""
    actor(world, guest)["traits"]["temper"] = temper
    actor(world, guest)["drunkenness"] = drunkenness


def trade_insults(world: dict[str, Any], count: int) -> str:
    """Let Ada and Bea trade `count` insults; return who spoke last."""
    return [say(world, "insult") for _ in range(count)][-1]


def quarrel_outcome(world: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """Tell whether Ada's scene stands, who attacked in each fight, and who stormed off from whom."""
    advance(world, 3)
    return (scene_in(world) is not None, [fight["a"] for fight in world["fights"]],
            sorted({event["message"] for event in world["events"] if event["type"] == "stormed_off"}))


def test_a_quarrel_below_the_boil_goes_on() -> None:
    world = seated_talk()
    foes(world)
    hot(world, "ada", 1.0, 0.5)
    trade_insults(world, BOIL - 1)
    assert quarrel_outcome(world) == (True, [], [])


@pytest.mark.parametrize("prepare, outcome", [
    pytest.param(lambda world: None, "stormed", id="calm-sober-pair-storm-off"),
    pytest.param(lambda world: hot(world, "ada", 1.0, 0.5), "ada", id="drunk-hothead-attacks"),
    pytest.param(lambda world: hot(world, "bea", 1.0, 0.5), "bea", id="drunk-hothead-attacks-even-if-she-spoke-last"),
    pytest.param(lambda world: (hot(world, "ada", 0.6, 0.5), hot(world, "bea", 1.0, 0.5)), "bea",
                 id="the-hotter-head-attacks"),
])
def test_a_quarrel_at_the_boil_ends_in_a_fight_or_a_walk_off(prepare: Callable[[dict[str, Any]], None],
                                                            outcome: str) -> None:
    world = seated_talk()
    foes(world)
    prepare(world)
    last = trade_insults(world, BOIL)
    insulted = "bea" if last == "ada" else "ada"
    expected = ((False, [], [f"{insulted.title()} stormed off from {last.title()}"]) if outcome == "stormed"
                else (False, [outcome], []))
    assert quarrel_outcome(world) == expected


def test_a_boiled_quarrel_is_not_taken_up_again_at_once() -> None:
    world = seated_talk()
    foes(world)
    trade_insults(world, BOIL)
    advance(world, 3)
    assert all(item.get("answered") for guest in ("ada", "bea") for item in actor(world, guest)["thoughts"]
               if item["kind"] == "quarrel")
