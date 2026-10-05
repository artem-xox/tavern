"""Gifts in a guest's choice: offered to company who could take them, weighed low and kindly, told plainly."""

import asyncio
from random import Random
from typing import Any

import pytest

from tavern.body.activities import FAMILIES
from tavern.body.items import carried_words, empty_inventory
from tavern.hall.rules import default_rules
from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import Evaluators, build_candidates, choose_action
from tavern.mind.briefing import brief
from tavern.mind.local_policy import local_scores
from tavern.mind.options import option_text
from hostile_view import NOW, person, thought, view
from social_hall import actor, advance, command, hall

WINDOW = default_rules()["giving"]["again_after"]


def carrying(counts: dict[str, int] | None = None, people: list[dict[str, Any]] | None = None,
             thoughts: list[dict[str, Any]] | None = None, needs: dict[str, float] | None = None,
             **fields: Any) -> dict[str, Any]:
    """Ada's observation, holding what `counts` says, with the world's giving rules."""
    observation = view(thoughts, people, **fields)
    observation["actor"]["inventory"] = {**empty_inventory(), **(counts or {})}
    observation["giving"] = default_rules()["giving"]
    observation["actor"]["needs"].update(needs or {})
    return observation


def gifts(observation: dict[str, Any]) -> list[str]:
    """The IDs of the gifts a guest is offered, whichever family option holds them."""
    options = build_candidates(observation)
    concrete = [item for option in options for item in option.get("members", [option])]
    return [item["id"] for item in concrete if item["verb"] == "give"]


@pytest.mark.parametrize("observation, expected", [
    pytest.param(carrying({"remedy": 1}), ["give:remedy:bea"], id="a-remedy-for-a-tablemate"),
    pytest.param(carrying({"remedy": 1, "keepsake": 2}), ["give:remedy:bea", "give:keepsake:bea"],
                 id="each-kind-held"),
    pytest.param(carrying({"remedy": 1}, people=[person("bea"), person("cid", id="cid", seat_id="n")]),
                 ["give:remedy:bea", "give:remedy:cid"], id="each-person-near"),
    pytest.param(carrying({"remedy": 1}, people=[person("dan", seat_id=None, table_id=None, beside=True)]),
                 ["give:remedy:dan"], id="someone-standing-beside"),
    pytest.param(carrying({"beer": 1}, people=[person("bea", holding={"beer": 1})]), ["give:beer:bea"],
                 id="a-second-mug-for-someone-holding-one"),
    pytest.param(carrying(), [], id="nothing-to-give"),
    pytest.param(carrying({"remedy": 1}, people=[]), [], id="nobody-in-sight"),
    pytest.param(carrying({"remedy": 1}, people=[person("cid", seat_id="fw", table_id="far")]), [],
                 id="someone-at-another-table"),
    pytest.param(carrying({"remedy": 1}, people=[person("hob", post="Bar")]), [], id="the-barkeep-takes-no-gifts"),
    pytest.param(carrying({"beer": 1}, people=[person("bea", holding={"beer": 2})]), [], id="hands-visibly-full"),
    pytest.param(carrying({"remedy": 1}, closed=True), [], id="the-inn-has-closed"),
    pytest.param(carrying({"beer": 1}, needs={"thirst": 49}), ["give:beer:bea"], id="a-mild-thirst-gives-way"),
    pytest.param(carrying({"beer": 1}, needs={"thirst": 50}), [], id="a-thirsty-guest-keeps-their-mug"),
    pytest.param(carrying({"beer": 1, "remedy": 1}, needs={"thirst": 90}), ["give:remedy:bea"],
                 id="a-thirsty-guest-may-still-give-what-is-in-a-pocket"),
])
def test_a_guest_is_offered_to_hand_over_what_they_carry_to_company_who_could_take_it(
        observation: dict[str, Any], expected: list[str]) -> None:
    assert gifts(observation) == expected


@pytest.mark.parametrize("held, ago, expected", [
    pytest.param("cared_for", 30.0, [], id="bea-gave-ada-a-remedy-a-moment-ago"),
    pytest.param("treated", 30.0, [], id="bea-bought-ada-a-drink-a-moment-ago"),
    pytest.param("generous", 30.0, [], id="ada-just-gave-bea-something"),
    pytest.param("rebuffed", 30.0, [], id="bea-refused-ada-a-moment-ago"),
    pytest.param("generous", WINDOW + 5.0, ["give:remedy:bea"], id="long-enough-since-ada-gave"),
    pytest.param("rebuffed", WINDOW + 5.0, ["give:remedy:bea"], id="long-enough-since-the-refusal"),
    pytest.param("chat", 30.0, ["give:remedy:bea"], id="a-chat-is-no-reason-to-wait"),
])
def test_a_guest_does_not_offer_again_soon_after_a_gift_either_way_or_a_refusal(
        held: str, ago: float, expected: list[str]) -> None:
    assert gifts(carrying({"remedy": 1}, thoughts=[thought(held, "bea", ago)])) == expected


@pytest.mark.parametrize("fields", [
    pytest.param({"time": None}, id="no-clock"),
    pytest.param({"giving": None}, id="no-rules"),
])
def test_without_a_clock_or_the_rules_no_gift_can_be_judged_recent_so_none_is_offered(fields: dict[str, Any]) -> None:
    observation = carrying({"remedy": 1})
    for key, value in fields.items():
        observation.pop(key) if value is None else observation.update({key: value})
    assert gifts(observation) == []


def test_gifts_belong_to_the_company_family_the_model_is_asked_about() -> None:
    options = build_candidates(carrying({"remedy": 1}, people=[person("bea"), person("cid", seat_id="n")]))
    assert [[item["id"] for item in option["members"]] for option in options if option["verb"] == "company"] == [
        ["give:remedy:bea", "give:remedy:cid"]]
    assert "hand someone something they carry" in FAMILIES["company"]


def score(observation: dict[str, Any], action_id: str) -> float:
    concrete = [item for option in build_candidates(observation) for item in option.get("members", [option])]
    return local_scores(observation, concrete)[action_id]


@pytest.mark.parametrize("worse, better", [
    pytest.param(carrying({"remedy": 1}, opinion=-10.0), carrying({"remedy": 1}, opinion=60.0), id="liking"),
    pytest.param(carrying({"remedy": 1}, opinion=-10.0), carrying({"remedy": 1}, opinion=0.0), id="not-disliking"),
])
def test_a_guest_is_warmer_to_a_gift_for_someone_they_like(worse: dict[str, Any], better: dict[str, Any]) -> None:
    assert score(worse, "give:remedy:bea") < score(better, "give:remedy:bea")


def test_a_sociable_guest_gives_more_readily() -> None:
    quiet, warm = carrying({"remedy": 1}), carrying({"remedy": 1})
    quiet["actor"]["traits"]["sociability"], warm["actor"]["traits"]["sociability"] = 0.1, 0.9
    assert score(quiet, "give:remedy:bea") < score(warm, "give:remedy:bea")


def test_a_mug_is_a_better_gift_to_hands_that_visibly_hold_none() -> None:
    empty = carrying({"beer": 1}, people=[person("bea", holding={})])
    holding = carrying({"beer": 1}, people=[person("bea", holding={"beer": 1})])
    assert score(holding, "give:beer:bea") < score(empty, "give:beer:bea")


def test_a_guest_with_a_mild_thirst_is_less_ready_to_give_their_mug() -> None:
    parched, content = carrying({"beer": 1}, needs={"thirst": 45}), carrying({"beer": 1}, needs={"thirst": 5})
    assert score(parched, "give:beer:bea") < score(content, "give:beer:bea")


def test_a_gift_is_low_on_its_own_and_always_a_score() -> None:
    best = carrying({"beer": 1}, opinion=100.0, people=[person("bea", holding={})])
    best["actor"]["traits"]["sociability"] = 1.0
    assert 0.0 <= score(carrying({"remedy": 1}, opinion=-100.0), "give:remedy:bea") <= score(best, "give:beer:bea") < 0.75


def test_a_gift_is_told_with_what_is_handed_and_who_takes_it() -> None:
    observation = carrying({"remedy": 1})
    assert option_text(observation, {"id": "give:remedy:bea", "verb": "give", "target_id": "bea", "item": "remedy"}) == (
        "hand a herbal remedy they are carrying to Bea, who sits at their table "
        "(it is theirs to give up, and Bea may refuse it if there is bad blood between them)")


@pytest.mark.parametrize("counts, expected", [
    pytest.param({}, None, id="nothing"),
    pytest.param({"beer": 1}, None, id="a-mug-is-in-the-hand-not-the-pocket"),
    pytest.param({"remedy": 1}, "a herbal remedy", id="one-remedy"),
    pytest.param({"remedy": 2}, "two herbal remedies", id="two-remedies"),
    pytest.param({"remedy": 3, "keepsake": 1}, "three herbal remedies and a keepsake", id="several-kinds"),
])
def test_what_is_carried_out_of_sight_is_counted_in_words(counts: dict[str, int], expected: str | None) -> None:
    assert carried_words({**empty_inventory(), **counts}) == expected


@pytest.mark.parametrize("counts, said", [
    pytest.param({"remedy": 2}, True, id="two-remedies"),
    pytest.param({"keepsake": 1, "remedy": 1}, True, id="several-kinds"),
    pytest.param({"beer": 1}, False, id="a-mug-only"),
    pytest.param({}, False, id="nothing"),
])
def test_the_briefing_says_what_a_guest_carries_in_their_pockets(counts: dict[str, int], said: bool) -> None:
    observation = carrying(counts)
    assert ("carrying" in brief(observation, [])["situation"]) is said


def test_the_briefing_counts_the_remedies() -> None:
    assert "They are also carrying two herbal remedies." in brief(carrying({"remedy": 2}), [])["situation"]


def seated() -> dict[str, Any]:
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 1)
    return world


@pytest.mark.parametrize("counts, holding", [
    pytest.param({"beer": 1}, {"beer": 1}, id="a-mug-is-seen"),
    pytest.param({"beer": 2, "remedy": 3}, {"beer": 2}, id="a-pocket-is-not"),
    pytest.param({"keepsake": 2}, {}, id="nothing-in-sight"),
    pytest.param({}, {}, id="empty-handed"),
])
def test_others_see_only_what_is_in_a_persons_hands(counts: dict[str, int], holding: dict[str, int]) -> None:
    world = seated()
    actor(world, "bea")["inventory"].update({**empty_inventory(), **counts})
    assert next(item for item in observe_people(world, "ada") if item["id"] == "bea")["holding"] == holding


def test_the_observation_carries_the_rules_of_giving() -> None:
    assert observe_actor(seated(), "ada")["giving"] == default_rules()["giving"]


def test_a_guest_who_decides_to_give_in_the_world_does_and_is_not_offered_it_again() -> None:
    world = seated()
    actor(world, "ada")["inventory"].update(remedy=2)

    async def prefer(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {item["id"]: float(item["verb"] in ("company", "give")) for item in candidates}

    def decide() -> dict[str, Any]:
        observation = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
        config = {"typesafe_api_key": "key", "model": "jev-latest", "timeout": 2.0, "temperature": 0.0}
        return asyncio.run(choose_action(observation, config, Random(1), Evaluators(prefer, prefer)))

    chosen = decide()["action"]
    assert chosen == {"id": "give:remedy:bea", "verb": "give", "target_id": "bea", "item": "remedy"}
    assert start_action(world, "ada", chosen) == {"accepted": True, "reason": None}
    advance(world, 2.0)
    assert (actor(world, "bea")["inventory"]["remedy"], actor(world, "ada")["inventory"]["remedy"]) == (1, 1)
    assert decide()["action"]["verb"] != "give"  # she still holds a remedy, but Bea has just had one
