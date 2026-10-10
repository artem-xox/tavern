"""A shove that lands: it may stagger or throw the one shoved, who is held where they are until they are up again."""

import pytest

from tavern.hall.world import start_action
from social_hall import actor, advance, command
from fight_hall import table_of_three


def shoved_by(seed: int, shover: str = "ada") -> dict:
    """Ada is the strong one and Bea the frail one; `shover` shoves the other."""
    world = table_of_three(seed, strong="ada")
    assert start_action(world, shover, command("shove", "bea" if shover == "ada" else "ada"))["accepted"]
    advance(world, 1.3)
    return world


def test_a_strong_shover_staggers_or_throws_the_frail_and_sometimes_misses() -> None:
    conditions = [actor(shoved_by(seed), "bea")["condition"] for seed in range(30)]
    assert {"staggered", "down", "ok"} <= set(conditions)


def test_a_weak_shover_seldom_moves_the_strong() -> None:
    conditions = [actor(shoved_by(seed, shover="bea"), "ada")["condition"] for seed in range(30)]
    assert conditions.count("ok") > conditions.count("down") + conditions.count("staggered")


@pytest.mark.parametrize("seconds, condition", [pytest.param(2.0, "staggered", id="reeling"), pytest.param(6.0, "down", id="thrown")])
def test_one_shoved_is_held_for_a_few_seconds_then_stands_again(seconds: float, condition: str) -> None:
    for seed in range(60):
        world = shoved_by(seed)
        bea = actor(world, "bea")
        if bea["condition"] != condition:
            continue
        assert bea["action"]["verb"] == "recover"
        advance(world, seconds + 0.5)
        assert (bea["condition"], bea["action"]) == ("ok", None)
        return
    raise AssertionError(f"nobody was {condition}")


def test_one_thrown_down_cannot_be_talked_to_or_shoved_again() -> None:
    for seed in range(60):
        world = shoved_by(seed)
        if actor(world, "bea")["condition"] != "down":
            continue
        assert start_action(world, "cid", command("talk", "bea")) == {"accepted": False, "reason": "Bea is on the floor"}
        assert start_action(world, "cid", command("shove", "bea")) == {"accepted": False, "reason": "Bea is on the floor"}
        return
    raise AssertionError("nobody was thrown down")
