"""Moving to a free table together: when it is offered, which table, and the errand that seats both."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import create_world, start_action
from tavern.social.invitations import offered_kinds
from social_hall import actor, advance, chair, command, say, scene_of

HOME = {"home": (5, 2)}


def tables_hall(tables: dict[str, tuple[int, int]], standing: dict[str, tuple[int, int]] | None = None) -> dict[str, Any]:
    """Build a hall of one-cell tables, each with a chair either side and a spot to stand south of it."""
    objects: list[dict[str, Any]] = []
    for table_id, (x, y) in tables.items():
        objects += [{"id": table_id, "kind": "table", "name": table_id.title(), "x": x, "y": y,
                     "interaction_spots": [[x, y + 1]]},
                    chair(f"{table_id}-w", x - 1, y, table_id), chair(f"{table_id}-e", x + 1, y, table_id)]
    start = {"ada": (1, 8), "bea": (2, 8), "cid": (3, 8), "dan": (4, 8), **(standing or {})}
    return {"width": 14, "height": 9, "blocked": [], "objects": objects,
            "actors": [{"id": name, "name": name.title(), "x": x, "y": y} for name, (x, y) in start.items()]}


def talking(tables: dict[str, tuple[int, int]], seated: dict[str, str | None] | None = None,
            standing: dict[str, tuple[int, int]] | None = None) -> dict[str, Any]:
    """Seat Ada and Bea at the home table (and anyone else where `seated` says; None leaves one standing) and let Ada talk to Bea."""
    world = create_world(tables_hall(tables, standing), 4)
    for name, seat in {"ada": "home-w", "bea": "home-e", **(seated or {})}.items():
        if seat is not None:
            assert start_action(world, name, command("sit", seat))["accepted"]
    advance(world, 12)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    return world


def agree_to_move(world: dict[str, Any], answer: str = "accept") -> None:
    """Ada invites Bea to move to a free table; Bea answers."""
    say(world, "invite", "Shall we sit elsewhere?", invitation="move_together")
    say(world, answer, "Gladly.")


def seat_table(world: dict[str, Any], actor_id: str) -> str | None:
    """The table a guest sits at."""
    seat = next((item for item in world["map"]["objects"] if item["id"] == actor(world, actor_id)["seat_id"]), None)
    return seat["table_id"] if seat else None


@pytest.mark.parametrize("tables, expected", [
    pytest.param({**HOME, "spare": (5, 6), "far": (11, 6)}, "spare", id="the-nearest-of-two-free-tables"),
    pytest.param({**HOME, "far": (11, 6), "spare": (5, 6)}, "spare", id="not-the-first-in-map-order"),
    pytest.param({**HOME, "zeta": (1, 6), "alpha": (7, 6)}, "zeta", id="a-tie-goes-to-map-order"),
])
def test_both_move_to_the_nearest_free_table(tables: dict[str, tuple[int, int]], expected: str) -> None:
    world = talking(tables)
    agree_to_move(world)
    advance(world, 15)
    assert (seat_table(world, "ada"), seat_table(world, "bea")) == (expected, expected)


def with_cid_at(chair_id: str) -> Callable[[], dict[str, Any]]:
    """Cid sits on a chair at the only other table."""
    return lambda: talking({**HOME, "busy": (5, 6)}, {"cid": chair_id})


def busy_pair() -> dict[str, Any]:
    """Cid and Dan sit at the only other table."""
    return talking({**HOME, "busy": (5, 6)}, {"cid": "busy-w", "dan": "busy-e"})


def away_owner() -> dict[str, Any]:
    """Cid is away from the only other table, but a chair there is his own."""
    world = talking({**HOME, "busy": (5, 6)})
    actor(world, "cid")["favorite_seat_id"] = "busy-w"
    return world


def bea_belongs_elsewhere() -> dict[str, Any]:
    """Bea stands by the home table, and the only other table is hers."""
    world = talking({**HOME, "hers": (5, 6)}, seated={"bea": None}, standing={"bea": (5, 3)})
    actor(world, "bea")["favorite_seat_id"] = "hers-w"
    return world


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda: talking({**HOME, "spare": (5, 6)}), True, id="a-free-table"),
    pytest.param(lambda: talking(HOME), False, id="no-other-table"),
    pytest.param(busy_pair, False, id="the-other-table-is-full"),
    pytest.param(with_cid_at("busy-w"), False, id="only-one-chair-there-is-free"),
    pytest.param(away_owner, False, id="a-chair-is-someones-own-seat"),
    pytest.param(bea_belongs_elsewhere, False, id="the-other-table-is-the-inviteess"),
])
def test_moving_together_is_offered_only_with_a_free_table(prepare: Callable[[], dict[str, Any]],
                                                           expected: bool) -> None:
    world = prepare()
    assert ("move_together" in offered_kinds(world, scene_of(world), actor(world, "ada"))) is expected


def test_the_errand_stays_while_they_walk_and_names_the_table() -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world)
    assert world["invitations"] == [{"kind": "move_together", "from": "ada", "to": "bea", "stage": "seating",
                                     "held": 0, "table": "spare"}]
    assert [actor(world, who)["action"]["verb"] for who in ("ada", "bea")] == ["sit", "sit"]


def test_the_errand_ends_once_both_sit() -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world)
    advance(world, 15)
    assert world["invitations"] == []


def test_the_errand_ends_when_one_goes_elsewhere_and_the_other_sits() -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world)
    assert start_action(world, "bea", command("wait"))["accepted"]
    advance(world, 15)
    assert (world["invitations"], seat_table(world, "ada"), seat_table(world, "bea")) == ([], "spare", None)


def test_a_declined_move_changes_nothing() -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world, "decline")
    advance(world, 15)
    assert (world["invitations"], seat_table(world, "ada"), seat_table(world, "bea")) == ([], "home", "home")


def test_an_errand_on_its_way_to_a_table_survives_save_and_load(tmp_path: Path) -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world)
    save_world(world, tmp_path / "save.json")
    assert load_world(tmp_path / "save.json")["invitations"] == world["invitations"]


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda errand: errand.pop("table"), id="seating-without-a-table"),
    pytest.param(lambda errand: errand.update(table="nowhere"), id="an-unknown-table"),
    pytest.param(lambda errand: errand.update(table=7), id="a-malformed-table"),
    pytest.param(lambda errand: errand.update(stage="accepted"), id="a-table-before-seating"),
])
def test_corrupt_seating_errands_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = talking({**HOME, "spare": (5, 6)})
    agree_to_move(world)
    corrupt(world["invitations"][0])
    save_world(world, tmp_path / "save.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "save.json")
