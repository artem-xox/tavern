"""Seeded chance: one draw per evening, tick and set of keys, the same on every replay."""

from random import Random
from typing import Any

import pytest

from tavern.hall.chance import roll


def world_at(seed: int, tick: int) -> dict[str, Any]:
    """A stand-in world: a roll reads only its seed and tick."""
    return {"seed": seed, "tick": tick}


def test_the_same_world_and_keys_give_the_same_number() -> None:
    assert roll(world_at(5, 40), "mara", "ivo") == roll(world_at(5, 40), "mara", "ivo")


@pytest.mark.parametrize("other_world, other_keys", [
    pytest.param(world_at(6, 40), ("mara", "ivo"), id="another-seed"),
    pytest.param(world_at(5, 41), ("mara", "ivo"), id="another-tick"),
    pytest.param(world_at(5, 40), ("ivo", "mara"), id="keys-in-another-order"),
    pytest.param(world_at(5, 40), ("mara", "ivo", "doze"), id="another-key"),
    pytest.param(world_at(5, 40), (), id="no-keys"),
])
def test_another_seed_tick_or_key_gives_another_number(other_world: dict[str, Any], other_keys: tuple[str, ...]) -> None:
    assert roll(other_world, *other_keys) != roll(world_at(5, 40), "mara", "ivo")


@pytest.mark.parametrize("keys", [
    pytest.param(("mara", "ivo"), id="a-pair"),
    pytest.param(("mara", "doze"), id="one-guest-and-a-reason"),
    pytest.param((), id="no-keys"),
])
def test_a_roll_keeps_the_string_form_recorded_evenings_were_played_with(keys: tuple[str, ...]) -> None:
    form = ":".join(["5", "40", *keys])
    assert roll(world_at(5, 40), *keys) == Random(form).random()


@pytest.mark.parametrize("tick", [pytest.param(tick, id=f"tick-{tick}") for tick in range(0, 500, 50)])
def test_a_roll_is_below_one_and_not_negative(tick: int) -> None:
    assert 0.0 <= roll(world_at(1, tick), "a", "b") < 1.0
