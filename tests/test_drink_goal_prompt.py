"""What a guest's mind is shown about bringing someone a drink: the occasion, the goal kind, and the shared prefix."""

from pathlib import Path
from typing import Any

import pytest

from tavern.hall.world import start_action
from tavern.mind.intention_prompt import intention_question
from tavern.mind.intentions import intention_view
from social_hall import actor, advance, command, know
from test_bring_drink import fetching

PREFIX = (Path(__file__).resolve().parents[1] / "data" / "minds" / "intention_prefix.md").read_text()
MOMENT = {"kind": "interval", "text": "A while passed", "time": 0.0}


def seen_by_ada(world: dict[str, Any]) -> dict[str, Any]:
    """What Ada's mind is shown when she takes stock."""
    return intention_view(world, actor(world, "ada"), MOMENT)


def with_a_mug(world: dict[str, Any]) -> None:
    actor(world, "bea")["inventory"]["beer"] = 1


def with_full_hands(world: dict[str, Any]) -> None:
    actor(world, "ada")["inventory"]["beer"] = 2


def not_knowing_the_tap(world: dict[str, Any]) -> None:
    del actor(world, "ada")["knowledge"]["objects"]["tap"]


def on_an_errand(world: dict[str, Any]) -> None:
    world["invitations"].append({"kind": "buy_drink", "from": "cid", "to": "bea", "stage": "accepted", "held": 0})


@pytest.mark.parametrize("change, expected", [
    pytest.param(lambda world: None, {"bea": "Bea"}, id="a-tablemate-with-empty-hands"),
    pytest.param(with_a_mug, {}, id="the-tablemate-holds-a-mug"),
    pytest.param(with_full_hands, {}, id="no-free-hand"),
    pytest.param(not_knowing_the_tap, {}, id="no-tap-known"),
    pytest.param(on_an_errand, {}, id="the-tablemate-is-already-being-served"),
])
def test_the_mind_is_shown_who_it_could_bring_a_drink(change: Any, expected: dict[str, str]) -> None:
    world = fetching()
    change(world)
    assert seen_by_ada(world)["fetchable"] == expected


def test_the_question_names_those_a_drink_could_be_brought_to() -> None:
    content = intention_question(PREFIX, seen_by_ada(fetching()))["content"]
    assert ("Company they could bring a mug of ale, with a hand free and a tap they know: Bea (id \"bea\")." in content,
            "bring_drink = bring that guest a drink" in content) == (True, True)


def test_the_question_says_nothing_of_it_when_there_is_nobody() -> None:
    world = fetching()
    with_a_mug(world)
    assert "Company they could bring" not in intention_question(PREFIX, seen_by_ada(world))["content"]


@pytest.mark.parametrize("wanted", [
    pytest.param("- `bring_drink`:", id="the-goal-kind-is-explained"),
    pytest.param("bring someone at their table or beside them a mug of ale", id="the-activity-is-on-the-list"),
    pytest.param("hand them something they carry", id="handing-over-is-on-the-list"),
    pytest.param("Example 37", id="there-is-an-example-of-the-goal"),
])
def test_the_shared_prefix_tells_the_mind_a_drink_can_be_brought(wanted: str) -> None:
    assert wanted in PREFIX


def test_the_shared_prefix_no_longer_says_a_drink_cannot_be_brought() -> None:
    assert "such as bringing someone a drink, belongs in no goal" not in PREFIX
