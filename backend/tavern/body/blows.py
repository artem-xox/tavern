"""How a blow lands and how a bout ends: the formula of a fight, from two fighters' traits and nothing else."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tavern.body.drunkenness import fight_accuracy


@dataclass(frozen=True)
class Weapon:
    """What a fighter strikes with.

    Attributes:
        kind: Inventory kind or `fists`, saved with a fight.
        base: Damage of a blow before strength counts.
        scale: Further damage of a blow at full strength (and an average roll).
        accuracy: Added to the chance of landing a blow.
    """

    kind: str
    base: float
    scale: float
    accuracy: float


WEAPONS: Mapping[str, Weapon] = MappingProxyType({
    "fists": Weapon("fists", 5.0, 20.0, 0.0),
    # A cudgel hurts about twice as much as a fist and is a little easier to land.
    "cudgel": Weapon("cudgel", 10.0, 24.0, 0.1),
})

# Seconds between exchanges: both fighters swing once each.
EXCHANGE_SECONDS = 1.0
# A fight lasts at least this long (the first exchanges always land and nobody falls), and is called off, one way or
# another, after the longer time.
MIN_SECONDS = 3.0
MAX_SECONDS = 12.0
# At or below this health a fighter is knocked out.
KNOCKOUT = 15.0
# Tiredness (0-100) at which both fighters are too winded to go on.
WINDED = 90.0
# A temper from which two who are done fighting go on cursing each other.
SHOUTING_TEMPER = 0.5
# How much more punishment a man of the same strength takes: the one place sex enters the formula, and never the
# chance to land a blow. A card with none counts as no bonus.
SEX_TOUGHNESS: Mapping[str, float] = MappingProxyType({"female": 0.0, "male": 0.1})
# How much of damage a fully tough fighter (toughness 1) shrugs off.
SHRUGGED = 0.3

ENDINGS = ("knockout", "double_knockout", "yielded", "shouting", "parted")
# The two ways a shove lays someone low, and how far one's strength and drink move the odds of each.
SHOVE_EDGE = 0.6
SHOVE_DRINK = 0.25


@dataclass(frozen=True)
class Fighter:
    """Everything the formula reads of one fighter, at the moment of an exchange.

    Attributes:
        strength: 0-1, how hard they hit and how much they take.
        sex: `female`, `male` or None.
        brawling: 0-1, skill: landing blows and dodging them.
        courage: 0-1, how long they stand before they yield.
        temper: 0-1, whether they go on cursing afterwards.
        drunkenness: 0-1.
        health: 0-100.
        fatigue: 0-100.
        weapon: A key of `WEAPONS`.
    """

    strength: float
    sex: str | None
    brawling: float
    courage: float
    temper: float
    drunkenness: float
    health: float
    fatigue: float
    weapon: str


@dataclass(frozen=True)
class Ending:
    """How a fight ended: one of `ENDINGS`, and who lost it ("a" or "b") where there is a loser."""

    kind: str
    loser: str | None


def toughness(fighter: Fighter) -> float:
    """Tell how much punishment a fighter takes, 0-1.

    Args:
        fighter: The one who is struck.

    Returns:
        Their strength plus their sex's bonus, within 0-1.
    """
    return min(1.0, fighter.strength + SEX_TOUGHNESS.get(fighter.sex or "", 0.0))


def hit_chance(attacker: Fighter, defender: Fighter) -> float:
    """Tell how likely a swing is to land.

    Args:
        attacker: The one who swings.
        defender: The one swung at.

    Returns:
        A chance from 0 to 0.95: skill against skill, scaled by how well the attacker still aims drunk and
        raised by how badly the defender dodges, plus the weapon's ease.
    """
    skill = min(0.9, max(0.15, 0.5 + 0.35 * (attacker.brawling - defender.brawling)))
    aim = fight_accuracy(attacker.drunkenness)
    dodge = 1 + 0.5 * (1 - fight_accuracy(defender.drunkenness))
    return min(0.95, skill * aim * dodge + WEAPONS[attacker.weapon].accuracy)


def damage(attacker: Fighter, defender: Fighter, roll: float) -> float:
    """Tell how much a blow that landed takes off the defender.

    Args:
        attacker: The one who struck.
        defender: The one struck.
        roll: A draw from 0 to 1 for how well it landed.

    Returns:
        Health lost: the weapon's base plus its scale by strength and the roll, less what the defender shrugs off.
    """
    weapon = WEAPONS[attacker.weapon]
    raw = weapon.base + weapon.scale * attacker.strength * (0.5 + roll)
    return raw * (1 - SHRUGGED * toughness(defender))


def swing(attacker: Fighter, defender: Fighter, hit_roll: float, damage_roll: float, elapsed: float) -> float:
    """Resolve one swing and tell the defender's health afterwards.

    Args:
        attacker: The one who swings.
        defender: The one swung at.
        hit_roll: A draw from 0 to 1; the swing lands below the hit chance.
        damage_roll: A draw from 0 to 1 for how well it lands.
        elapsed: Seconds since the fight began; before `MIN_SECONDS` nobody is felled, so the first exchanges always
            land and a fight is never over in a blink.

    Returns:
        The defender's health, 0-100.
    """
    if hit_roll >= hit_chance(attacker, defender):
        return defender.health
    floor = KNOCKOUT + 1.0 if elapsed < MIN_SECONDS else 0.0
    return max(min(defender.health, floor), defender.health - damage(attacker, defender, damage_roll))


def yield_line(fighter: Fighter) -> float:
    """Tell the health below which a fighter gives up.

    Args:
        fighter: The fighter.

    Returns:
        Fifty less what courage holds, and drink keeps a guest in a fight they should leave.
    """
    return 50.0 * (1 - fighter.courage) * (1 - 0.5 * fighter.drunkenness)


def shove_result(shover: Fighter, shoved: Fighter, roll: float) -> str:
    """Tell what a shove does to the one shoved.

    Args:
        shover: The one who shoves.
        shoved: The one shoved.
        roll: A draw from 0 to 1.

    Returns:
        `down` (thrown to the floor), `staggered` (a step back) or `nothing`: strength against toughness, with a
        drunk shover pushing worse and a drunk one shoved holding their feet worse.
    """
    force = 0.35 + SHOVE_EDGE * (shover.strength - toughness(shoved)) + SHOVE_DRINK * (shoved.drunkenness
                                                                                       - shover.drunkenness)
    force = min(0.9, max(0.05, force))
    return "down" if roll < 0.4 * force else "staggered" if roll < force else "nothing"


def ending(a: Fighter, b: Fighter, elapsed: float) -> Ending | None:
    """Tell whether the fight is over and how, checked after each exchange.

    Args:
        a: One fighter, as they are now.
        b: The other.
        elapsed: Seconds since it began.

    Returns:
        None before `MIN_SECONDS` and while both stand and neither will give up. Then, in this order: both at or
        below `KNOCKOUT` (`double_knockout`), one (`knockout`), one below their yield line (`yielded`, the one with the
        less health if both), and past `MAX_SECONDS` or with both winded `shouting` when either has a temper of
        `SHOUTING_TEMPER` or more, else `parted`.
    """
    if elapsed < MIN_SECONDS:
        return None
    down_a, down_b = a.health <= KNOCKOUT, b.health <= KNOCKOUT
    if down_a and down_b:
        return Ending("double_knockout", None)
    if down_a or down_b:
        return Ending("knockout", "a" if down_a else "b")
    quitting = [(fighter.health, key) for key, fighter in (("a", a), ("b", b)) if fighter.health < yield_line(fighter)]
    if quitting:
        return Ending("yielded", min(quitting)[1])
    if elapsed >= MAX_SECONDS or (a.fatigue >= WINDED and b.fatigue >= WINDED):
        hot = max(a.temper, b.temper) >= SHOUTING_TEMPER
        return Ending("shouting" if hot else "parted", None)
    return None

