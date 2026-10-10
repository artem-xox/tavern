"""The formula of a fight (`body/blows.py`): single swings, how a bout ends, and the rates it gives over many."""

from dataclasses import replace
from random import Random

import pytest

from tavern.body.blows import (ENDINGS, EXCHANGE_SECONDS, KNOCKOUT, MAX_SECONDS, MIN_SECONDS, Ending, Fighter,
                               damage, ending, hit_chance, swing, toughness, yield_line)


def fighter(strength: float = 0.5, brawling: float = 0.5, courage: float = 0.5, temper: float = 0.4,
            drunkenness: float = 0.0, sex: str | None = None, weapon: str = "fists", health: float = 100.0,
            fatigue: float = 30.0) -> Fighter:
    return Fighter(strength, sex, brawling, courage, temper, drunkenness, health, fatigue, weapon)


def bout(first: Fighter, second: Fighter, seed: int) -> tuple[Ending, float]:
    """Play a fight out the way the world does: both swing each second, then the end is checked."""
    rng, elapsed = Random(seed), 0.0
    while True:
        elapsed += EXCHANGE_SECONDS
        second_health = swing(first, second, rng.random(), rng.random(), elapsed)
        first_health = swing(second, first, rng.random(), rng.random(), elapsed)
        first, second = replace(first, health=first_health, fatigue=first.fatigue + 2.5), \
            replace(second, health=second_health, fatigue=second.fatigue + 2.5)
        finished = ending(first, second, elapsed)
        if finished:
            return finished, elapsed


@pytest.mark.parametrize("weaker, stronger", [
    pytest.param(fighter(drunkenness=0.6), fighter(), id="a-drunk-aims-worse"),
    pytest.param(fighter(brawling=0.2), fighter(brawling=0.8), id="skill-lands-more"),
    pytest.param(fighter(weapon="fists"), fighter(weapon="cudgel"), id="a-cudgel-is-easier-to-land"),
])
def test_hit_chance_rises_with_the_attackers_edge(weaker: Fighter, stronger: Fighter) -> None:
    target = fighter()
    assert hit_chance(weaker, target) < hit_chance(stronger, target)


def test_a_drunk_defender_is_easier_to_hit() -> None:
    assert hit_chance(fighter(), fighter(drunkenness=0.8)) > hit_chance(fighter(), fighter())


@pytest.mark.parametrize("attacker, defender, expected", [
    pytest.param(fighter(brawling=1.0, weapon="cudgel"), fighter(brawling=0.0, drunkenness=0.9), 0.95, id="capped"),
    pytest.param(fighter(brawling=0.0), fighter(brawling=1.0), 0.15, id="a-hopeless-swing-still-lands-sometimes"),
])
def test_hit_chance_stays_within_its_bounds(attacker: Fighter, defender: Fighter, expected: float) -> None:
    assert hit_chance(attacker, defender) == pytest.approx(expected)


def test_sex_never_changes_the_chance_to_land_a_blow() -> None:
    assert hit_chance(fighter(sex="female"), fighter()) == hit_chance(fighter(sex="male"), fighter())


@pytest.mark.parametrize("light, heavy", [
    pytest.param(fighter(strength=0.2), fighter(strength=0.9), id="strength"),
    pytest.param(fighter(), fighter(weapon="cudgel"), id="a-cudgel"),
])
def test_damage_grows_with_the_attacker(light: Fighter, heavy: Fighter) -> None:
    assert damage(light, fighter(), 0.5) < damage(heavy, fighter(), 0.5)


@pytest.mark.parametrize("tender, tough", [
    pytest.param(fighter(strength=0.2), fighter(strength=0.9), id="a-strong-defender"),
    pytest.param(fighter(sex="female"), fighter(sex="male"), id="a-man-of-the-same-strength"),
])
def test_damage_shrinks_against_a_tough_defender(tender: Fighter, tough: Fighter) -> None:
    assert damage(fighter(), tender, 0.5) > damage(fighter(), tough, 0.5)


@pytest.mark.parametrize("sex, expected", [
    pytest.param(None, 0.5, id="no-sex-no-bonus"),
    pytest.param("female", 0.5, id="female"),
    pytest.param("male", 0.6, id="male"),
])
def test_toughness_adds_the_sex_bonus_to_strength(sex: str | None, expected: float) -> None:
    assert toughness(fighter(sex=sex)) == pytest.approx(expected)


def test_toughness_is_capped_at_one() -> None:
    assert toughness(fighter(strength=0.98, sex="male")) == 1.0


@pytest.mark.parametrize("hit_roll, elapsed, expected", [
    pytest.param(0.99, 5.0, 100.0, id="a-miss-leaves-them-whole"),
    pytest.param(0.0, 5.0, None, id="a-hit-hurts"),
])
def test_a_swing_hurts_only_when_it_lands(hit_roll: float, elapsed: float, expected: float | None) -> None:
    health = swing(fighter(), fighter(), hit_roll, 0.5, elapsed)
    assert (health < 100.0) if expected is None else health == expected


def test_nobody_is_felled_before_the_minimum_time() -> None:
    frail = fighter(health=17.0)
    assert swing(fighter(strength=1.0, weapon="cudgel"), frail, 0.0, 1.0, MIN_SECONDS - 0.5) == KNOCKOUT + 1.0


def test_a_blow_after_the_minimum_time_can_fell() -> None:
    assert swing(fighter(strength=1.0, weapon="cudgel"), fighter(health=17.0), 0.0, 1.0, MIN_SECONDS) <= KNOCKOUT


def test_a_swing_never_takes_health_below_zero() -> None:
    assert swing(fighter(strength=1.0, weapon="cudgel"), fighter(health=2.0), 0.0, 1.0, 9.0) == 0.0


def test_a_swing_never_heals_a_fighter_already_under_the_floor() -> None:
    assert swing(fighter(), fighter(health=5.0), 0.0, 0.5, 1.0) == 5.0


@pytest.mark.parametrize("courage, drunkenness, expected", [
    pytest.param(1.0, 0.0, 0.0, id="the-fearless-never-yield"),
    pytest.param(0.5, 0.0, 25.0, id="ordinary"),
    pytest.param(0.0, 0.0, 50.0, id="a-coward"),
    pytest.param(0.5, 1.0, 12.5, id="drink-keeps-them-in"),
])
def test_yield_line(courage: float, drunkenness: float, expected: float) -> None:
    assert yield_line(fighter(courage=courage, drunkenness=drunkenness)) == pytest.approx(expected)


@pytest.mark.parametrize("first, second, elapsed, expected", [
    pytest.param(fighter(health=5.0), fighter(), MIN_SECONDS - 0.1, None, id="nothing-before-the-minimum"),
    pytest.param(fighter(), fighter(), 5.0, None, id="both-stand"),
    pytest.param(fighter(health=10.0), fighter(), 4.0, Ending("knockout", "a"), id="first-knocked-out"),
    pytest.param(fighter(), fighter(health=KNOCKOUT), 4.0, Ending("knockout", "b"), id="second-knocked-out"),
    pytest.param(fighter(health=10.0), fighter(health=3.0), 4.0, Ending("double_knockout", None), id="both"),
    pytest.param(fighter(courage=0.0, health=40.0), fighter(), 4.0, Ending("yielded", "a"), id="a-coward-yields"),
    pytest.param(fighter(courage=0.0, health=30.0), fighter(courage=0.0, health=20.0), 4.0,
                 Ending("yielded", "b"), id="the-worse-hurt-of-two-who-yield"),
    pytest.param(fighter(temper=0.2), fighter(temper=0.3), MAX_SECONDS, Ending("parted", None), id="cool-heads-part"),
    pytest.param(fighter(temper=0.2), fighter(temper=0.7), MAX_SECONDS, Ending("shouting", None), id="a-hot-head-shouts"),
    pytest.param(fighter(fatigue=95.0), fighter(fatigue=92.0), 5.0, Ending("parted", None), id="both-winded"),
    pytest.param(fighter(fatigue=95.0), fighter(fatigue=60.0), 5.0, None, id="one-winded-fights-on"),
])
def test_how_a_fight_ends(first: Fighter, second: Fighter, elapsed: float, expected: Ending | None) -> None:
    assert ending(first, second, elapsed) == expected


# Rates over many seeded fights: the case list is the spec of the formula's balance.
SEEDS = range(500)
STRONG_SOBER = fighter(strength=0.8, brawling=0.7, courage=0.75, temper=0.3, sex="male")
WEAK_DRUNK = fighter(strength=0.2, brawling=0.1, courage=0.35, temper=0.6, drunkenness=0.6, sex="female")


def _share(first: Fighter, second: Fighter, wanted: str) -> float:
    kinds = [bout(first, second, seed)[0] for seed in SEEDS]
    if wanted == "first_wins":
        return sum(1 for item in kinds if item.loser == "b") / len(kinds)
    if wanted == "second_wins":
        return sum(1 for item in kinds if item.loser == "a") / len(kinds)
    if wanted == "no_knockout":
        return sum(1 for item in kinds if item.kind not in ("knockout", "double_knockout")) / len(kinds)
    return sum(1 for item in kinds if item.kind == wanted) / len(kinds)


@pytest.mark.parametrize("first, second, wanted, low, high", [
    pytest.param(STRONG_SOBER, WEAK_DRUNK, "first_wins", 0.8, 1.0, id="strong-sober-beats-weak-drunk"),
    pytest.param(WEAK_DRUNK, STRONG_SOBER, "second_wins", 0.8, 1.0, id="the-same-seen-from-the-other-side"),
    pytest.param(fighter(), fighter(), "first_wins", 0.25, 0.5, id="equals-split-the-wins-first"),
    pytest.param(fighter(), fighter(), "second_wins", 0.25, 0.5, id="equals-split-the-wins-second"),
    pytest.param(fighter(weapon="cudgel"), fighter(), "first_wins", 0.75, 1.0, id="a-cudgel-beats-fists"),
    pytest.param(fighter(), fighter(), "no_knockout", 0.2, 1.0, id="fists-often-end-without-a-knockout"),
    pytest.param(fighter(weapon="cudgel"), fighter(weapon="cudgel"), "double_knockout", 0.01, 0.08,
                 id="cudgels-sometimes-fell-both"),
    pytest.param(fighter(), fighter(), "double_knockout", 0.0, 0.03, id="fists-rarely-fell-both"),
])
def test_rates_over_many_fights(first: Fighter, second: Fighter, wanted: str, low: float, high: float) -> None:
    assert low <= _share(first, second, wanted) <= high


def test_the_drunk_yield_less_often_than_the_sober() -> None:
    sober = [bout(fighter(courage=0.3), fighter(), seed)[0].kind for seed in SEEDS]
    drunk = [bout(fighter(courage=0.3, drunkenness=0.8), fighter(), seed)[0].kind for seed in SEEDS]
    assert drunk.count("yielded") < sober.count("yielded")


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in (0, 7, 41)])
def test_a_fight_lasts_at_least_the_minimum_and_ends_in_a_known_way(seed: int) -> None:
    finished, elapsed = bout(STRONG_SOBER, WEAK_DRUNK, seed)
    assert MIN_SECONDS <= elapsed <= MAX_SECONDS and finished.kind in ENDINGS


def test_a_seeded_fight_replays_identically() -> None:
    assert bout(STRONG_SOBER, WEAK_DRUNK, 3) == bout(STRONG_SOBER, WEAK_DRUNK, 3)
