"""The third stage of a choice: after a social option is chosen, the aim."""

import asyncio
from random import Random
from typing import Any

import httpx
import pytest

from tavern.adapters.jev import JevError, evaluate_aims, evaluate_aims_metered, request_body
from tavern.hall.world import create_world, observe_actor, observe_people, start_action
from tavern.mind.agents import Evaluator, Evaluators, choose_action
from tavern.mind.local_policy import local_aim_scores
from tavern.mind.selection import read_aims
from social_hall import advance, command, know, spotted_hall


def ada_sees_bea(social: float = 95.0, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ada's observation, seated across from Bea, who is free to talk."""
    world = create_world(spotted_hall(), 4)
    for name, chair in (("ada", "w"), ("bea", "e")):
        assert start_action(world, name, command("sit", chair))["accepted"]
    advance(world, 8)
    for item in world["actors"]:
        item["needs"]["social"] = social
        know(world, item["id"], "near", "w", "e", "n", "far", "fw", "fe", "darts")
    for fact_id, topic in (facts or {}).items():
        next(item for item in world["actors"] if item["id"] == "ada")["knowledge"]["facts"][fact_id] = {
            "topic": topic, "told_as": "x", "heard_from": None, "heard_at": 0.0, "confidence": 1.0, "hops": 0,
            "overheard": False}
    return {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}


def settings(key: str | None = "test", **fields: Any) -> dict[str, Any]:
    """The AI config with the aims stage on unless said otherwise."""
    return {"typesafe_api_key": key, "model": "jev-latest", "timeout": 2.0, "temperature": 0.0, "aims": True, **fields}


def favouring(prefix: str | tuple[str, ...], seen: list[Any] | None = None) -> Evaluator:
    """A fake evaluator that scores highest the options whose ID starts with a prefix, and notes what it was asked."""
    async def evaluate(view: Any, candidates: Any, config: Any) -> dict[str, float]:
        if seen is not None:
            seen.append([item["id"] for item in candidates])
        return {item["id"]: float(item["id"].startswith(prefix)) for item in candidates}
    return evaluate


async def refusing(view: Any, candidates: Any, config: Any) -> dict[str, float]:
    """Fail the way the Jev adapter does."""
    raise JevError("Jev request timed out")


def decide(view: dict[str, Any], evaluators: Evaluators, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a choice."""
    return asyncio.run(choose_action(view, config or settings(), Random(0), evaluators))


def test_the_aim_is_chosen_after_the_action_and_travels_with_it() -> None:
    asked: list[Any] = []
    result = decide(ada_sees_bea(), Evaluators(favouring("talk"), favouring("sit"), aims=favouring("win_over", asked)))
    assert (result["action"], result["aim"]["name"], result["aim"]["source"], result["aim"]["error"]) == (
        {"id": "talk:bea", "verb": "talk", "target_id": "bea", "aim": "win_over"}, "win_over", "jev", None)
    assert asked == [["pass_time@talk:bea", "invite:darts_together@talk:bea", "win_over@talk:bea"]]


def test_the_aims_come_from_the_world_the_guest_knows() -> None:
    asked: list[Any] = []
    decide(ada_sees_bea(facts={"fever": "the fever"}),
           Evaluators(favouring("talk"), favouring("sit"), aims=favouring("tell_news", asked)))
    assert "tell_news:fever@talk:bea" in asked[0]


def test_a_lone_aim_is_set_without_asking() -> None:
    view = ada_sees_bea()
    view["objects"] = [item for item in view["objects"] if item["kind"] != "darts"]
    view["actor"]["relations"] = {"bea": {"name": "Bea", "opinion": 0.0, "familiarity": "friend"}}
    view["actor"]["thoughts"] = []
    asked: list[Any] = []
    result = decide(view, Evaluators(favouring("talk"), favouring("sit"), aims=favouring("x", asked)))
    assert asked == [] and "aim" not in result and result["action"]["aim"] == "pass_time"


def test_a_failing_aims_evaluator_falls_back_to_the_local_scores_and_says_so() -> None:
    result = decide(ada_sees_bea(), Evaluators(favouring("talk"), favouring("sit"), aims=refusing))
    assert (result["aim"]["source"], result["aim"]["error"], result["action"]["aim"] in result["aim"]["name"]) == (
        "local", "Jev request timed out", True)


@pytest.mark.parametrize("config", [
    pytest.param(settings(aims=False), id="aims-off"),
    pytest.param({k: v for k, v in settings().items() if k != "aims"}, id="aims-absent"),
])
def test_without_the_setting_no_aim_is_chosen(config: dict[str, Any]) -> None:
    result = decide(ada_sees_bea(), Evaluators(favouring("talk"), favouring("sit"), aims=favouring("win_over")), config)
    assert ("aim" in result, "aim" in result["action"]) == (False, False)


def test_an_action_that_is_not_social_takes_no_aim() -> None:
    result = decide(ada_sees_bea(), Evaluators(favouring("sit"), favouring("sit"), aims=favouring("win_over")))
    assert (result["action"]["verb"], "aim" in result["action"], "aim" in result) == ("sit", False, False)


def test_without_a_key_the_aim_is_chosen_locally_and_no_model_is_asked() -> None:
    result = decide(ada_sees_bea(), Evaluators(favouring("talk"), favouring("sit"), aims=refusing), settings(key=None))
    assert (result["source"], result["aim"]["source"], result["aim"]["error"]) == ("local", "local", None)


def test_an_aims_setting_with_a_key_and_no_aims_evaluator_fails_loudly() -> None:
    with pytest.raises(ValueError, match="aims"):
        decide(ada_sees_bea(), Evaluators(favouring("talk"), favouring("sit")))


@pytest.mark.parametrize("config, expected", [
    pytest.param({}, False, id="absent-is-off"),
    pytest.param({"aims": True}, True, id="on"),
    pytest.param({"aims": False}, False, id="off"),
])
def test_the_aims_setting_is_read_from_the_config(config: dict[str, Any], expected: bool) -> None:
    assert read_aims(config) is expected


@pytest.mark.parametrize("config", [
    pytest.param({"aims": "yes"}, id="a-string"),
    pytest.param({"aims": None}, id="none"),
])
def test_an_aims_setting_that_is_not_a_bool_fails_loudly(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="aims"):
        read_aims(config)


def candidates_for(*aims: str) -> list[dict[str, Any]]:
    """Aim candidates for `talk:bea`."""
    return [{"id": f"{aim}@talk:bea", "verb": "talk", "target_id": "bea", "aim": aim} for aim in aims]


@pytest.mark.parametrize("aim, key, value, extra", [
    pytest.param("needle", "temper", 1.0, 0.1 + 0.5 * 0.5, id="a-hot-temper-needles-more"),
    pytest.param("needle", "temper", 0.0, 0.1, id="a-cool-temper-barely-needles"),
    pytest.param("have_it_out", "temper", 1.0, 0.7, id="a-hot-temper-has-it-out"),
    pytest.param("have_it_out", "temper", 0.0, 0.2, id="a-cool-temper-has-it-out-less"),
    pytest.param("win_over", "sociability", 1.0, 0.6, id="a-sociable-guest-wins-over"),
    pytest.param("win_over", "sociability", 0.0, 0.2, id="a-shy-guest-wins-over-less"),
])
def test_the_local_aim_scores_follow_the_guests_character(aim: str, key: str, value: float, extra: float) -> None:
    view = ada_sees_bea()
    view["actor"]["traits"].update({"temper": 0.5, "sociability": 0.5, key: value})
    view["actor"]["relations"] = {"bea": {"name": "Bea", "opinion": -50.0, "familiarity": "acquaintance"}}
    view["actor"]["thoughts"] = []
    assert local_aim_scores(view, candidates_for(aim))[f"{aim}@talk:bea"] == pytest.approx(extra)


def test_every_offered_aim_gets_a_local_score_between_zero_and_one() -> None:
    from tavern.social.aims import AIMS
    view = ada_sees_bea(facts={"fever": "the fever"})
    names = ["pass_time", "tell_news:fever", "invite:darts_together", "invite:dice_together", "invite:buy_drink",
             "invite:join_table", "win_over", "needle", "have_it_out", "thank", "rematch"]
    scores = local_aim_scores(view, candidates_for(*names))
    assert (set(scores), all(0.0 <= score <= 1.0 for score in scores.values()), {n.partition(":")[0] for n in names}
            == set(AIMS)) == ({f"{name}@talk:bea" for name in names}, True, True)


def jev_view() -> dict[str, Any]:
    """What the Jev adapter is given for the aim question."""
    return {"situation": "Ada sits at a table.", "options": {"win_over@talk:bea": "chat with Bea, meaning to win her over"},
            "self": {"name": "Ada"}}


def test_the_aim_question_asks_how_natural_the_aim_is_and_says_when() -> None:
    body = request_body(jev_view(), candidates_for("win_over"), "jev-latest", aims=True)
    text = body["questions"]["win_over@talk:bea"]["instructions"]
    assert ("chat with Bea, meaning to win her over" in text, "someone they hardly know" in text,
            len(body["questions"]["win_over@talk:bea"]["criteria"])) == (True, True, 5)


def test_aims_are_scored_by_the_jev_adapter() -> None:
    payload = {"answers": {"win_over@talk:bea": {"type": "score", "score": 3}},
               "usage": {"input_tokens": 12, "output_tokens": 1}}

    async def run() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
            config = {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 2.0}
            return (await evaluate_aims(jev_view(), candidates_for("win_over"), config, client),
                    await evaluate_aims_metered(jev_view(), candidates_for("win_over"), config, client))
    assert asyncio.run(run()) == ({"win_over@talk:bea": 0.75}, ({"win_over@talk:bea": 0.75},
                                                                  {"input_tokens": 12, "output_tokens": 1}))
