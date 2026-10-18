"""Fun: how much each verb relieves boredom, and what a guest does with a drink in company."""

from types import MappingProxyType
from typing import Any

import pytest

from tavern.body.activities import ACTIVITIES, Activity


@pytest.mark.parametrize("verb, fun", [
    pytest.param("play_dice", 0.9, id="dice-together"),
    pytest.param("play_darts", 0.7, id="darts"),
    pytest.param("watch_dice", 0.6, id="a-crowd-at-the-game"),
    pytest.param("stand_at_bar", 0.3, id="leaning-on-the-bar"),
    pytest.param("watch", 0.4, id="the-fire-or-the-view"),
    pytest.param("sit", 0.0, id="sitting"),
    pytest.param("wait", 0.0, id="waiting"),
])
def test_each_verb_is_as_much_fun_as_the_table_says(verb: str, fun: float) -> None:
    assert ACTIVITIES[verb].fun == fun


@pytest.mark.parametrize("verb", [pytest.param(verb, id=verb) for verb in ACTIVITIES])
def test_an_activity_eases_boredom_by_its_fun_and_nothing_else_does(verb: str) -> None:
    activity = ACTIVITIES[verb]
    assert activity.needs.get("boredom", 0.0) == pytest.approx(-100 * activity.fun)


def activity(**fields: Any) -> Activity:
    """A bare activity with the fields given."""
    return Activity(verb="idle", what="idle", guidance="never", duration=1.0, family="resting", **fields)


@pytest.mark.parametrize("fields, boredom", [
    pytest.param({}, None, id="no-fun-no-relief"),
    pytest.param({"fun": 0.5}, -50.0, id="half-fun-halves-boredom"),
    pytest.param({"fun": 1.0}, -100.0, id="full-fun-clears-it"),
    pytest.param({"fun": 0.0, "needs": MappingProxyType({"social": -5})}, None, id="other-needs-stay"),
])
def test_fun_becomes_relief_from_boredom(fields: dict[str, Any], boredom: float | None) -> None:
    assert activity(**fields).needs.get("boredom") == boredom


@pytest.mark.parametrize("fields", [
    pytest.param({"fun": -0.1}, id="negative-fun"),
    pytest.param({"fun": 1.5}, id="more-than-total-fun"),
    pytest.param({"fun": 0.5, "needs": MappingProxyType({"boredom": -20})}, id="two-sources-of-relief"),
])
def test_a_malformed_fun_is_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        activity(**fields)


# --- drinking: what a drink in company does ---------------------------------------------------------------------

from tavern.hall.world import create_world, observe_actor, observe_people, start_action, step_world  # noqa: E402
from tavern.mind.agents import build_candidates  # noqa: E402
from tavern.mind.briefing import brief  # noqa: E402
from tavern.mind.local_policy import local_aim_scores, local_scores  # noqa: E402


def table_hall(*, dice: bool = False, mates: int = 0) -> dict[str, Any]:
    """A table with Ada's chair and up to two mates' chairs; optionally a dice table and a tap."""
    chairs = [{"id": f"c{index}", "kind": "chair", "name": f"Table · {index}", "x": 2 + index, "y": 2,
               "walkable": True, "table_id": "table", "interaction_spots": [[2 + index, 2]]} for index in range(3)]
    objects = [{"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 3, "width": 3, "height": 1}, *chairs,
               {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5}]
    if dice:
        objects += [{"id": "dice", "kind": "dice_table", "name": "Dice table", "x": 5, "y": 1, "width": 1, "height": 1,
                     "interaction_spots": [[5, 2]]}]
    people = [{"id": "ada", "name": "Ada", "x": 2, "y": 2},
              *({"id": f"mate{index}", "name": f"Mate {index}", "x": 3 + index, "y": 2} for index in range(mates))]
    return {"width": 9, "height": 6, "tile_size": 32, "blocked": [], "objects": objects, "actors": people}


def seated(world: dict[str, Any], *who: str) -> dict[str, Any]:
    """Seat Ada and the mates named in the chairs of their table, and let them settle."""
    for index, name in enumerate(who):
        assert start_action(world, name, {"id": f"sit:c{index}", "verb": "sit", "target_id": f"c{index}"})["accepted"]
    for _ in range(100):
        step_world(world, 0.1)
    return world


def seen_by_ada(world: dict[str, Any]) -> dict[str, Any]:
    """Ada's observation, with the people she sees."""
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}


def sated(world: dict[str, Any], drunkenness: float = 0.0, **needs: float) -> dict[str, Any]:
    """Ada has no thirst, and is as drunk as told; other needs as told."""
    ada = world["actors"][0]
    ada["needs"].update(thirst=0.0, **needs)
    ada["drunkenness"] = drunkenness
    return world


def take_beer_score(world: dict[str, Any]) -> float:
    """What Ada would score fetching another ale."""
    action = {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}
    return local_scores(seen_by_ada(world), [action])[action["id"]]


@pytest.mark.parametrize("start, tolerance, events", [
    pytest.param(0.0, 0.5, [], id="sober-to-tipsy"),
    pytest.param(0.1, 0.5, [], id="tipsy-stays-tipsy"),
    pytest.param(0.3, 0.5, ["got_drunk"], id="tipsy-to-drunk"),
    pytest.param(0.5, 0.5, [], id="drunk-stays-drunk"),
    pytest.param(0.6, 0.5, ["got_wasted"], id="drunk-to-wasted"),
    pytest.param(0.8, 0.5, [], id="wasted-stays-wasted"),
    pytest.param(0.4, 0.0, ["got_drunk"], id="a-lightweight-jumps-a-stage"),
])
def test_crossing_into_drunk_or_wasted_is_logged_once(start: float, tolerance: float, events: list[str]) -> None:
    world = create_world(table_hall())
    ada = world["actors"][0]
    ada.update(drunkenness=start)
    ada["traits"]["tolerance"] = tolerance
    ada["inventory"]["beer"] = 1
    assert start_action(world, "ada", {"id": "drink", "verb": "drink", "target_id": None})["accepted"]
    for _ in range(35):
        step_world(world, 0.1)
    assert [item["type"] for item in world["events"] if item["type"].startswith("got_")] == events


@pytest.mark.parametrize("mates, drunkenness, bladder, expected_more", [
    pytest.param(2, 0.0, 0.0, True, id="two-drinking-mates-tempt-a-sated-guest"),
    pytest.param(1, 0.0, 0.0, True, id="one-mate-tempts-a-little"),
    pytest.param(0, 0.0, 0.0, False, id="alone-nothing-tempts-them"),
    pytest.param(2, 0.8, 0.0, False, id="wasted-nobody-pushes-another-on-them"),
    pytest.param(2, 0.0, 100.0, False, id="a-full-bladder-outweighs-the-company"),
])
def test_a_sated_guest_at_a_lively_table_fetches_another_ale(mates: int, drunkenness: float, bladder: float,
                                                              expected_more: bool) -> None:
    world = sated(seated(create_world(table_hall(mates=mates)), "ada", *(f"mate{i}" for i in range(mates))),
                  drunkenness, bladder=bladder)
    assert (take_beer_score(world) > 0.0) is expected_more


@pytest.mark.parametrize("mates, drunkenness, thirst, offered", [
    pytest.param(2, 0.0, 0.0, True, id="a-lively-table-offers-another-ale-to-the-sated"),
    pytest.param(1, 0.0, 0.0, True, id="one-mate-is-company-enough"),
    pytest.param(0, 0.0, 0.0, False, id="alone-the-sated-do-not-fetch"),
    pytest.param(2, 0.8, 0.0, False, id="wasted-guests-are-not-offered-another"),
    pytest.param(0, 0.0, 60.0, True, id="the-thirsty-fetch-as-before"),
])
def test_the_tap_is_offered_to_a_sated_guest_only_in_company(mates: int, drunkenness: float, thirst: float,
                                                              offered: bool) -> None:
    world = sated(seated(create_world(table_hall(mates=mates)), "ada", *(f"mate{i}" for i in range(mates))), drunkenness)
    world["actors"][0]["needs"]["thirst"] = thirst
    assert any(item["verb"] == "take_beer" for item in build_candidates(seen_by_ada(world))) is offered


def test_the_sociable_are_tempted_more_than_loners_by_the_same_table() -> None:
    scores = []
    for sociability in (0.1, 0.5, 0.9):
        world = sated(seated(create_world(table_hall(mates=2)), "ada", "mate0", "mate1"))
        world["actors"][0]["traits"]["sociability"] = sociability
        scores.append(take_beer_score(world))
    assert scores[0] < scores[1] < scores[2]


def test_the_pull_of_company_leaves_a_thirsty_guests_score_within_one() -> None:
    world = seated(create_world(table_hall(mates=2)), "ada", "mate0", "mate1")
    world["actors"][0]["needs"]["thirst"] = 100.0
    assert 0.0 <= take_beer_score(world) <= 1.0


# --- dice: the bold and the drunk gamble ---------------------------------------------------------------------------

def dice_score(world: dict[str, Any], aim: str = "invite:dice_together") -> float:
    """What Ada would score meaning to propose dice to Mate 0."""
    candidate = {"id": f"talk:mate0:{aim}", "verb": "talk", "target_id": "mate0", "aim": aim}
    return local_aim_scores(seen_by_ada(world), [candidate])[candidate["id"]]


def bored(drunkenness: float = 0.0, courage: float = 0.5, boredom: float = 60.0) -> dict[str, Any]:
    """Ada, bored, at a table with a mate."""
    world = seated(create_world(table_hall(dice=True, mates=1)), "ada", "mate0")
    ada = world["actors"][0]
    ada["needs"]["boredom"] = boredom
    ada["drunkenness"] = drunkenness
    ada["traits"]["courage"] = courage
    return world


@pytest.mark.parametrize("worse, better", [
    pytest.param({"drunkenness": 0.0}, {"drunkenness": 0.5}, id="drink-makes-a-game-tempting"),
    pytest.param({"courage": 0.2}, {"courage": 0.9}, id="the-bold-gamble-more"),
])
def test_dice_tempt_the_drunk_and_the_bold(worse: dict[str, float], better: dict[str, float]) -> None:
    assert dice_score(bored(**worse)) < dice_score(bored(**better))


def test_a_game_of_dice_tempts_a_bored_guest_more_than_darts() -> None:
    world = bored()
    assert dice_score(world) > dice_score(world, "invite:darts_together")


def test_an_ordinary_sober_guest_is_tempted_by_boredom_alone() -> None:
    assert dice_score(bored(boredom=60.0)) == pytest.approx(0.25 + 0.5 * 0.6)


# --- the briefing says what would be fun ------------------------------------------------------------------------

def told(world: dict[str, Any]) -> str:
    """What Ada is told of her situation."""
    return brief(seen_by_ada(world), [])["situation"]


def test_the_briefing_names_a_free_dice_table_to_a_bored_guest() -> None:
    assert "Fun, if they want it" in told(bored(boredom=70.0)) and "Dice table" in told(bored(boredom=70.0))


def test_the_briefing_names_no_fun_to_a_content_guest_alone() -> None:
    world = seated(create_world(table_hall(dice=True)), "ada")
    world["actors"][0]["needs"]["boredom"] = 0.0
    assert "Fun, if they want it" not in told(world)


def test_the_briefing_says_a_lively_table_is_a_place_for_another_round() -> None:
    world = sated(seated(create_world(table_hall(mates=2)), "ada", "mate0", "mate1"))
    assert "another round" in told(world)


def test_the_briefing_never_pushes_another_round_on_a_wasted_guest() -> None:
    world = sated(seated(create_world(table_hall(mates=2)), "ada", "mate0", "mate1"), 0.9)
    assert "another round" not in told(world)


# --- a healer does not go home past someone she could mend ---------------------------------------------------------

def leaving(remedies: int, unwell: bool, seconds: float = 400.0) -> float:
    """What a guest who has had three beers scores for going home, with a healer's remedies as told and someone in sight."""
    person = {"id": "bea", "name": "Bea", "ailing": unwell}
    observation = {"actor": {"id": "ada", "name": "Ada", "traits": {}, "inventory": {"beer": 0, "remedy": remedies},
                             "visit": {"seconds": seconds, "beers": 3},
                             "needs": {"thirst": 0, "fatigue": 0, "bladder": 0, "social": 0, "boredom": 0}},
                   "objects": [], "people": [person], "invitations": []}
    action = {"id": "leave:door", "verb": "leave", "target_id": "door"}
    return local_scores(observation, [action])[action["id"]]


@pytest.mark.parametrize("remedies, unwell, holds", [
    pytest.param(3, True, True, id="a-healer-stays-for-the-unwell"),
    pytest.param(3, False, False, id="a-healer-goes-home-when-nobody-needs-her"),
    pytest.param(0, True, False, id="a-guest-without-a-remedy-cannot-help-and-goes"),
])
def test_a_healer_does_not_go_home_while_someone_in_sight_is_unwell(remedies: int, unwell: bool, holds: bool) -> None:
    assert (leaving(remedies, unwell) < 0.3) is holds
