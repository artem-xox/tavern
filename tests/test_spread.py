"""Temperament in the draw: the hot-headed and the drunk spread their choices wider, the patient narrower."""

import asyncio
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import Evaluators, choose_action
from tavern.mind.selection import Spread, drawable, spread


def guest(temper: float | None = 0.5, patience: float | None = 0.5, drunkenness: float | None = 0.0) -> dict[str, Any]:
    """A guest with the traits the draw reads; None leaves one out."""
    traits = {key: value for key, value in (("temper", temper), ("patience", patience)) if value is not None}
    return {"traits": traits, **({} if drunkenness is None else {"drunkenness": drunkenness})}


@pytest.mark.parametrize("actor, temperature, expected", [
    pytest.param(guest(), 0.25, Spread(0.15, 0.25), id="an-ordinary-sober-guest-draws-as-the-config-says"),
    pytest.param(guest(0.0, 1.0), 0.25, Spread(0.08, 0.125), id="a-patient-sober-guest-is-capped-narrow"),
    pytest.param(guest(0.2, 0.7), 0.25, Spread(0.105, 0.175), id="a-calm-guest-a-little-narrower"),
    pytest.param(guest(0.8, 0.3, 0.5), 0.25, Spread(0.255, 0.425), id="a-hot-head-in-drink-spreads-wide"),
    pytest.param(guest(1.0, 0.0, 1.0), 0.25, Spread(0.3, 0.5), id="the-hottest-and-drunkest-are-capped-at-twice"),
    pytest.param(guest(None, None, None), 0.25, Spread(0.15, 0.25), id="traits-a-stage-0-visitor-lacks-read-as-ordinary"),
    pytest.param(guest(1.0, 0.0, 1.0), 0.0, Spread(0.3, 0.0), id="zero-temperature-stays-zero"),
    pytest.param({}, 0.25, Spread(0.15, 0.25), id="no-traits-at-all"),
])
def test_the_spread_of_a_draw_follows_temper_patience_and_drink(actor: dict[str, Any], temperature: float,
                                                                expected: Spread) -> None:
    result = spread(actor, temperature)
    assert (result.window, result.temperature) == (pytest.approx(expected.window), pytest.approx(expected.temperature))


@pytest.mark.parametrize("actor, temperature", [
    pytest.param(guest(temper=1.5), 0.25, id="temper-above-one"),
    pytest.param(guest(patience=-0.1), 0.25, id="patience-below-zero"),
    pytest.param(guest(drunkenness=1.2), 0.25, id="drunkenness-above-one"),
    pytest.param(guest(), -0.1, id="negative-temperature"),
])
def test_a_spread_of_impossible_input_fails_loudly(actor: dict[str, Any], temperature: float) -> None:
    with pytest.raises(ValueError):
        spread(actor, temperature)


def act(item: str) -> dict[str, Any]:
    """A candidate."""
    return {"id": item, "verb": item, "target_id": None}


@pytest.mark.parametrize("window, expected", [
    pytest.param(0.15, ["a", "b"], id="the-default-window"),
    pytest.param(0.08, ["a"], id="a-narrow-window"),
    pytest.param(0.3, ["a", "b", "c"], id="a-wide-window"),
])
def test_the_draw_reaches_the_options_inside_the_window(window: float, expected: list[str]) -> None:
    scores = {"a": 0.9, "b": 0.8, "c": 0.65}
    kept = drawable([act("a"), act("b"), act("c")], scores, window)
    assert [item["id"] for item in kept] == expected


def test_the_window_defaults_to_fifteen_hundredths() -> None:
    assert [item["id"] for item in drawable([act("a"), act("b"), act("c")], {"a": 0.9, "b": 0.76, "c": 0.7})] == ["a", "b"]


def drawn(actor_fields: dict[str, Any]) -> set[str]:
    """The verbs a guest ends up taking over many seeds, when a model scores `sit` 1.0 and `wait` 0.8."""
    async def evaluate(view: Any, candidates: Any, settings: Any) -> dict[str, float]:
        return {item["id"]: {"sit": 1.0, "wait": 0.8}.get(item["verb"], 0.0) for item in candidates}

    chair = {"id": "chair", "kind": "chair", "x": 3, "y": 2, "reserved_by": None, "table_id": "table"}
    view = {"actor": {"id": "ada", "name": "Ada", "x": 1, "y": 1, "inventory": {"beer": 0},
                      "needs": {"thirst": 20, "fatigue": 20, "bladder": 20},
                      "favorite_seat_id": "chair", **actor_fields,
                      "traits": {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5, **actor_fields.get("traits", {})}},
            "objects": [chair], "memory": []}
    settings = {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 1.0, "temperature": 0.25}
    return {asyncio.run(choose_action(view, settings, Random(seed), Evaluators(evaluate, evaluate)))["action"]["verb"]
            for seed in range(200)}


def test_an_ordinary_guest_never_takes_what_a_model_rates_far_below_the_best() -> None:
    assert drawn({}) == {"sit"}


def test_a_hot_headed_drunk_sometimes_does() -> None:
    assert drawn({"drunkenness": 1.0, "traits": {"temper": 1.0, "patience": 0.0}}) == {"sit", "wait"}
