"""Where lines may stand in a hall, and how a line in progress is saved and validated."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.persistence import load_world, save_world
from tavern.world import create_world, start_action, step_world

HALL = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())


def hall(queue_spots: Any = None, **fields: Any) -> dict[str, Any]:
    """Build the shipped hall without guests, with other queue spots for the WC if given."""
    data = {key: value for key, value in HALL.items() if key != "arrival"}
    objects = [dict(item) for item in data["objects"]]
    toilet = next(item for item in objects if item["id"] == "toilet")
    if queue_spots is not None:
        toilet["queue_spots"] = queue_spots
    toilet.update(fields)
    return {**data, "objects": objects, "actors": []}


def toilet(world: dict[str, Any]) -> dict[str, Any]:
    """Return the WC."""
    return next(item for item in world["map"]["objects"] if item["id"] == "toilet")


@pytest.mark.parametrize("queue_spots, line", [
    pytest.param([[14, 2]], [], id="single-spot"),
    pytest.param([[14, 2], [13, 2], [12, 2], [11, 2]], [], id="shipped-line"),
])
def test_a_place_with_queue_spots_starts_with_an_empty_line(queue_spots: list[list[int]], line: list[Any]) -> None:
    assert toilet(create_world(hall(queue_spots)))["queue"] == line


@pytest.mark.parametrize("queue_spots, fields", [
    pytest.param([], {}, id="empty-line"),
    pytest.param([[14, 2], [14, 2]], {}, id="duplicate-spots"),
    pytest.param([[14]], {}, id="malformed-spot"),
    pytest.param("north", {}, id="malformed-spots"),
    pytest.param([[30, 2]], {}, id="outside-the-map"),
    pytest.param([[15, 2]], {}, id="inside-a-wall"),
    pytest.param([[15, 3]], {}, id="in-the-wc-doorway"),
    pytest.param([[14, 3]], {}, id="on-the-way-out-of-the-doorway"),
    pytest.param([[17, 3]], {}, id="on-the-interaction-spot"),
    pytest.param([[6, 3]], {}, id="on-the-tap-spot"),
    pytest.param([[7, 4]], {}, id="on-the-tap-line"),
    pytest.param([[14, 2]], {"interaction_spots": [[17, 3], [16, 3]]}, id="place-used-from-two-spots"),
])
def test_lines_never_block_a_way_in_or_out(queue_spots: Any, fields: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        create_world(hall(queue_spots, **fields))


def test_a_line_needs_a_need_that_sets_patience() -> None:
    data = hall()
    chair = next(item for item in data["objects"] if item["id"] == "chair-1")
    chair["queue_spots"] = [[13, 6]]
    with pytest.raises(ValueError):
        create_world(data)


def lined_up() -> dict[str, Any]:
    """Return a hall where Ann uses the WC and Bob and Cid wait in line for it."""
    data = hall()
    data["actors"] = [{"id": guest, "name": guest.title(), "sprite": guest, "x": x, "y": 3}
                      for guest, x in (("ann", 17), ("bob", 12), ("cid", 10))]
    world = create_world(data)
    for guest in ("ann", "bob", "cid"):
        assert start_action(world, guest, {"id": "use_toilet:toilet", "verb": "use_toilet",
                                           "target_id": "toilet"})["accepted"]
    for _ in range(30):
        step_world(world, 0.1)
    return world


def test_a_line_in_progress_survives_a_save(tmp_path: Path) -> None:
    world = lined_up()
    save_world(world, tmp_path / "line.json")
    loaded = load_world(tmp_path / "line.json")
    assert (loaded, [entry["actor_id"] for entry in toilet(loaded)["queue"]]) == (world, ["bob", "cid"])


def visitor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Return a present visitor by ID."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: toilet(world).update(queue={}), id="malformed-line"),
    pytest.param(lambda world: toilet(world)["queue"].append({"actor_id": "zed", "since": 0.0}),
                 id="unknown-guest-in-line"),
    pytest.param(lambda world: toilet(world)["queue"].append(dict(toilet(world)["queue"][0])),
                 id="duplicate-guest-in-line"),
    pytest.param(lambda world: toilet(world)["queue"].append({"actor_id": "ann", "since": 0.0}),
                 id="user-also-in-line"),
    pytest.param(lambda world: toilet(world)["queue"][0].update(since="early"), id="malformed-since"),
    pytest.param(lambda world: toilet(world)["queue"][0].update(since=99.0), id="joined-in-the-future"),
    pytest.param(lambda world: toilet(world)["queue"][0].pop("actor_id"), id="entry-without-guest"),
    pytest.param(lambda world: visitor(world, "bob").update(action=None), id="in-line-without-an-action"),
    pytest.param(lambda world: visitor(world, "bob")["action"].update(target_id="tap", verb="take_beer"),
                 id="in-line-for-something-else"),
    pytest.param(lambda world: toilet(world)["queue"].pop(), id="queued-guest-in-no-line"),
    pytest.param(lambda world: toilet(world)["queue"].extend(
        {"actor_id": guest, "since": 0.0} for guest in ("x1", "x2", "x3")), id="more-than-the-spots"),
])
def test_corrupt_lines_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world = lined_up()
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


@pytest.mark.parametrize("version", [
    pytest.param(1, id="version-1-save"),
    pytest.param(2, id="version-2-save-without-lines"),
])
def test_saves_from_before_lines_are_rejected(tmp_path: Path, version: int) -> None:
    world = lined_up()
    world["schema_version"] = version
    save_world(world, tmp_path / "old.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "old.json")
