"""A hall with a fight in it, for the tests of reactions and of mending (helpers, not tests)."""

from typing import Any

from tavern.hall.world import create_world, start_action
from social_hall import actor, advance, command, spotted_hall


def table_of_three(seed: int = 4, strong: str = "ada", weak_courage: float = 1.0) -> dict[str, Any]:
    """Ada, Bea and Cid sit at the near table (Cid on its north chair); Dan stands by the fire.

    `strong` is a heavy brawler, the other of the two a weak one who never yields (`weak_courage`).
    """
    world = create_world(spotted_hall(), seed)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "n")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    advance(world, 3)
    weak = "bea" if strong == "ada" else "ada"
    actor(world, strong)["traits"].update(strength=1.0, brawling=1.0, courage=1.0, temper=0.2)
    actor(world, weak)["traits"].update(strength=0.1, brawling=0.0, courage=weak_courage, temper=0.2)
    return world


def at_blows(world: dict[str, Any], attacker: str = "ada", victim: str = "bea") -> None:
    """Have the attacker start a fight with the victim."""
    assert start_action(world, attacker, command("start_fight", victim))["accepted"]


def until_fight_ends(world: dict[str, Any], limit: float = 40.0) -> dict[str, Any]:
    """Run the world until the first fight is over and return it."""
    for _ in range(round(limit * 10)):
        advance(world, 0.1)
        if world["fights"] and world["fights"][0]["outcome"] is not None:
            return dict(world["fights"][0])
    raise AssertionError("the fight never ended")


def battered(world: dict[str, Any], actor_id: str, health: float = 40.0) -> None:
    """Leave a guest hurt, as after a fight, without the fight."""
    actor(world, actor_id)["health"] = health
