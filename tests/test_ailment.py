"""A guest who comes in unwell, and the remedy that cures them: the draw, the cure, what others see, and saves."""

import json
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.ailment import RELIEF
from tavern.body.items import ITEMS, empty_inventory
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.staff import guests
from tavern.hall.world import create_world, observe_people, start_action, step_world
from social_hall import actor, advance, command, hall

FEVER = 80.0


def seated() -> dict[str, Any]:
    """Ada and Bea sit at the near table, Cid at the far one, and Dan stands by the fire."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    return world


def hold(world: dict[str, Any], actor_id: str, **counts: int) -> None:
    """Put exactly these things in a guest's hands and pockets."""
    actor(world, actor_id)["inventory"].update({**empty_inventory(), **counts})


def give(item: str, receiver: str = "bea") -> dict[str, Any]:
    """Build the action of handing an item to someone."""
    return {"id": f"give:{item}:{receiver}", "verb": "give", "target_id": receiver, "item": item}


def handed(world: dict[str, Any], giver: str, action: dict[str, Any]) -> None:
    """Start a gift and let it finish."""
    assert start_action(world, giver, action) == {"accepted": True, "reason": None}
    advance(world, 2.0)


def kinds_about(world: dict[str, Any], holder: str, about: str) -> list[str]:
    """The kinds of thought a guest holds about another."""
    return [item["kind"] for item in actor(world, holder)["thoughts"] if item["about"] == about]


def unwell(world: dict[str, Any], actor_id: str = "bea", fatigue: float = FEVER) -> dict[str, Any]:
    """Make a guest ailing and weak."""
    actor(world, actor_id).update(ailing=True)
    actor(world, actor_id)["needs"]["fatigue"] = fatigue
    return world


def test_a_remedy_is_the_one_item_that_cures() -> None:
    assert [kind for kind, item in ITEMS.items() if item.cures] == ["remedy"]


@pytest.mark.parametrize("kind, fatigue, cured, tired_after, theirs, thought", [
    pytest.param("remedy", 80.0, True, 80.0 - RELIEF, 0, "cured", id="a-remedy-cures-and-is-used-up"),
    pytest.param("remedy", 30.0, True, 0.0, 0, "cured", id="the-relief-stops-at-full-energy"),
    pytest.param("keepsake", 80.0, False, 80.0, 1, "gifted", id="a-keepsake-cures-nothing"),
    pytest.param("beer", 80.0, False, 80.0, 1, "treated", id="a-mug-cures-nothing"),
])
def test_a_remedy_cures_a_sick_guest_and_nothing_else_does(kind: str, fatigue: float, cured: bool, tired_after: float,
                                                           theirs: int, thought: str) -> None:
    world = unwell(seated(), fatigue=fatigue)
    hold(world, "ada", **{kind: 2})
    handed(world, "ada", give(kind))
    bea = actor(world, "bea")
    # Tiredness drifts up a little over the two seconds the hand-over takes.
    assert (bea["ailing"], bea["needs"]["fatigue"], actor(world, "ada")["inventory"][kind], bea["inventory"][kind],
            kinds_about(world, "bea", "ada"), kinds_about(world, "ada", "bea")) == (
        not cured, pytest.approx(tired_after, abs=0.5), 1, theirs, [thought], ["generous"])


def test_a_remedy_given_to_a_well_guest_is_as_it_always_was() -> None:
    world = seated()
    hold(world, "ada", remedy=2)
    handed(world, "ada", give("remedy"))
    bea = actor(world, "bea")
    assert (bea["ailing"], bea["inventory"]["remedy"], kinds_about(world, "bea", "ada")) == (False, 1, ["cared_for"])


def test_both_remember_the_cure() -> None:
    world = unwell(seated())
    hold(world, "ada", remedy=1)
    handed(world, "ada", give("remedy"))
    messages = {who: [item["message"] for item in actor(world, who)["memory"] if item["type"] == "cured"]
                for who in ("ada", "bea")}
    assert messages == {"ada": ["Bea took Ada's herbal remedy and looks better already"],
                        "bea": ["Bea took Ada's herbal remedy and looks better already"]}
    assert (actor(world, "bea")["emote"] or {}).get("kind") == "affection"


def test_a_sick_guest_who_would_not_take_it_stays_sick() -> None:
    world = unwell(seated())
    hold(world, "ada", remedy=1)
    actor(world, "bea")["relations"]["ada"] = {"name": "Ada", "opinion": -50.0, "familiarity": "acquaintance",
                                               "knows_name": True}
    handed(world, "ada", give("remedy"))
    bea = actor(world, "bea")
    assert (bea["ailing"], bea["needs"]["fatigue"], actor(world, "ada")["inventory"]["remedy"]) == (
        True, pytest.approx(FEVER, abs=0.5), 1)


def test_others_see_who_looks_unwell() -> None:
    world = unwell(seated())
    assert {item["id"]: item["ailing"] for item in observe_people(world, "ada")} == {"bea": True, "cid": False, "dan": False}


def test_nobody_is_ailing_unless_the_scenario_says_so() -> None:
    assert [item["ailing"] for item in create_world(hall(), 4)["actors"]] == [False] * 4


def guest(guest_id: str, arrives_at: float = 0, **fields: Any) -> dict[str, Any]:
    """Describe a guest the way a scenario file does."""
    return {"id": guest_id, "name": guest_id.title(), "color": "#c09060", "sprite": "visitor",
            "traits": {"patience": 0.5}, "arrives_at": arrives_at, **fields}


def scenario(**fields: Any) -> dict[str, Any]:
    """Describe an evening of Ada (with two remedies), Bea, Cid and Dan, plus the given fields."""
    return {"guests": [guest("ada", carries={"remedy": 2}), guest("bea"), guest("cid", 30), guest("dan", 60)],
            "arrival": {"needs": {"thirst": [50, 90], "fatigue": [0, 0]}}, "closes_at": 300, **fields}


def room() -> dict[str, Any]:
    """Build a 10×7 hall with a door with room for four guests at once, and a tap."""
    return {"width": 10, "height": 7, "blocked": [[x, 6] for x in range(10) if x != 5], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 5, "y": 6,
         "interaction_spots": [[5, 5], [4, 5], [6, 5], [3, 5]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5}]}


def evening(seed: int, **fields: Any) -> dict[str, Any]:
    """Open the evening and let time pass without decisions, so that every guest has come in."""
    world = open_evening(room(), parse_scenario(scenario(**fields)), seed)
    for _ in range(140):
        step_world(world, 0.5)
    return world


def needs_of(world: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Every guest's needs, in the hall and still expected."""
    return {item["id"]: item["needs"] for item in [*guests(world), *world["expected"]]}


def sick(world: dict[str, Any]) -> list[str]:
    """The IDs of the guests who are ailing."""
    return [item["id"] for item in guests(world) if item["ailing"]]


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in range(12)])
def test_one_guest_who_carries_no_cure_comes_in_ailing(seed: int) -> None:
    world = evening(seed, ailment={"fatigue": FEVER})
    (name,) = sick(world)
    assert name != "ada" and actor(world, name)["needs"]["fatigue"] >= FEVER


def test_the_same_seed_makes_the_same_guest_ill() -> None:
    assert sick(evening(3, ailment={"fatigue": FEVER})) == sick(evening(3, ailment={"fatigue": FEVER}))


def test_over_several_seeds_it_is_not_always_the_same_guest() -> None:
    assert len({tuple(sick(evening(seed, ailment={"fatigue": FEVER}))) for seed in range(12)}) >= 2


def test_the_sick_guest_arrives_unwell_whenever_they_arrive() -> None:
    opened = open_evening(room(), parse_scenario(scenario(ailment={"fatigue": FEVER})), 5)
    ailing_ids = [item["id"] for item in [*guests(opened), *opened["expected"]] if item.get("ailing")]
    assert len(ailing_ids) == 1
    assert [item["message"] for item in opened["events"] if item["type"] == "arrived_unwell"] in ([], [
        f"{ailing_ids[0].title()} came in looking pale and feverish"])


def test_only_the_sick_guests_fatigue_changes() -> None:
    plain = open_evening(room(), parse_scenario(scenario()), 5)
    ill = open_evening(room(), parse_scenario(scenario(ailment={"fatigue": FEVER})), 5)
    before, after = needs_of(plain), needs_of(ill)
    (name,) = [guest_id for guest_id in before if before[guest_id] != after[guest_id]]
    assert {key: value for key, value in after[name].items() if key != "fatigue"} == {
        key: value for key, value in before[name].items() if key != "fatigue"}


@pytest.mark.parametrize("ailment", [
    pytest.param({}, id="no-fatigue"),
    pytest.param({"fatigue": 80, "cough": 1}, id="unknown-key"),
    pytest.param({"fatigue": -1}, id="negative"),
    pytest.param({"fatigue": 101}, id="over-100"),
    pytest.param({"fatigue": "high"}, id="text"),
    pytest.param(80, id="not-a-mapping"),
])
def test_a_malformed_ailment_fails_loudly(ailment: Any) -> None:
    with pytest.raises(ValueError, match="ailment|fatigue"):
        parse_scenario(scenario(ailment=ailment))


def test_an_evening_where_everyone_carries_a_cure_has_nobody_to_fall_ill() -> None:
    data = scenario(ailment={"fatigue": FEVER})
    data["guests"] = [guest("ada", carries={"remedy": 1}), guest("bea", carries={"remedy": 2})]
    with pytest.raises(ValueError, match="ailment"):
        parse_scenario(data)


def reloaded(world: dict[str, Any]) -> dict[str, Any]:
    """Save a world and load it back."""
    return parse_world(json.dumps(world))


def test_a_sick_guest_in_the_hall_reloads() -> None:
    world = unwell(create_world(hall(), 4))
    assert actor(reloaded(world), "bea")["ailing"] is True


def test_a_sick_guest_still_expected_reloads() -> None:
    world = open_evening(room(), parse_scenario(scenario(ailment={"fatigue": FEVER})), 5)
    expected = [item for item in world["expected"] if item.get("ailing")]
    loaded = reloaded(world)
    assert [item["id"] for item in loaded["expected"] if item.get("ailing")] == [item["id"] for item in expected]


@pytest.mark.parametrize("change", [
    pytest.param(lambda world: actor(world, "ada").update(ailing="yes"), id="text"),
    pytest.param(lambda world: actor(world, "ada").update(ailing=1), id="number"),
    pytest.param(lambda world: actor(world, "ada").pop("ailing"), id="missing"),
    pytest.param(lambda world: world.update(schema_version=16), id="version-16-save"),
])
def test_a_save_with_a_malformed_ailing_flag_is_refused(change: Any) -> None:
    world = create_world(hall(), 4)
    change(world)
    with pytest.raises(ValueError):
        parse_world(json.dumps(world))


def test_a_departed_sick_guest_with_a_malformed_flag_is_refused() -> None:
    world = create_world(hall(), 4)
    assert start_action(world, "ada", command("leave", "door"))["accepted"]
    advance(world, 6)
    gone = next(item for item in world["departed"] if item["id"] == "ada")
    gone["ailing"] = "yes"
    with pytest.raises(ValueError):
        parse_world(json.dumps(world))
