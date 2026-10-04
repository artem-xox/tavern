"""Staff cells: the floor behind a bar that only staff walk on, and what a hall must say about it."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.navigation import find_path
from tavern.hall.room import impassable_cells, line_approach, object_cells

FACINGS = ("north", "south", "east", "west")


def check_staff_cells(world_map: Mapping[str, Any]) -> None:
    """Check the staff cells of a hall's bars.

    Args:
        world_map: Map whose objects were validated by `room.create_map`. A bar may have `staff_cells`
            (cells behind it, in listed order, that only staff walk on) and then needs `staff_facing`,
            the way its staff look when idle; they come together or not at all.

    Raises:
        ValueError: Anything but a bar has staff cells; a bar has one of the two fields without the other;
            the cells are not a nonempty run of distinct cells inside the hall, free floor, each next to
            the one before it, off every interaction spot, queue spot and line's way in, with one next to
            a tap; or they would cut one place off from the others.
    """
    bars = [item for item in world_map["objects"] if "staff_cells" in item or "staff_facing" in item]
    for item in bars:
        if item["kind"] != "bar":
            raise ValueError(f"Staff cells belong to a bar, not to {item['id']!r}")
        if "staff_cells" not in item or item.get("staff_facing") not in FACINGS:
            raise ValueError(f"Bar {item['id']!r} needs staff_cells with a staff_facing of {', '.join(FACINGS)}")
        _check_stretch(world_map, item["id"], item["staff_cells"])
    _check_nothing_cut_off(world_map, off_limits(world_map, {}))


def off_limits(world_map: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    """List the cells a visitor may not walk on.

    Args:
        world_map: Validated map.
        actor: The visitor who walks. Every visitor is a guest for now.

    Returns:
        The staff cells of every bar, in map order.
    """
    return [(x, y) for item in world_map["objects"] for x, y in item.get("staff_cells", [])]


def _check_stretch(world_map: Mapping[str, Any], bar_id: str, cells: Any) -> None:
    if not isinstance(cells, list) or not cells or not all(
            isinstance(cell, list) and len(cell) == 2 and all(type(value) is int for value in cell)
            for cell in cells):
        raise ValueError(f"Staff cells of {bar_id!r} must be a nonempty list of cells")
    inside = all(0 <= x < world_map["width"] and 0 <= y < world_map["height"] for x, y in cells)
    if len({tuple(cell) for cell in cells}) != len(cells) or not inside:
        raise ValueError(f"Staff cells of {bar_id!r} must be distinct cells inside the hall")
    furniture = {cell for item in world_map["objects"] for cell in object_cells(item)}
    if any(tuple(cell) in {*impassable_cells(world_map), *furniture} for cell in cells):
        raise ValueError(f"Staff cells of {bar_id!r} must be free floor")
    if any(abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1 for a, b in zip(cells, cells[1:])):
        raise ValueError(f"Staff cells of {bar_id!r} must form one stretch of adjacent cells")
    if any(tuple(cell) in _kept(world_map) for cell in cells):
        raise ValueError(f"Staff cells of {bar_id!r} must keep off every interaction spot, queue spot and way in")
    taps = {cell for item in world_map["objects"] if item["kind"] == "tap" for cell in object_cells(item)}
    if not any((x + dx, y + dy) in taps for x, y in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
        raise ValueError(f"Staff cells of {bar_id!r} must include a cell next to a tap")


def _kept(world_map: Mapping[str, Any]) -> set[tuple[int, int]]:
    # What the room keeps clear for guests: the spots where places are used, where lines wait, and the
    # way from the front of each line to its place.
    objects = world_map["objects"]
    kept = {tuple(spot) for item in objects for spot in [*item["interaction_spots"], *item.get("queue_spots", [])]}
    return kept | {cell for item in objects if "queue_spots" in item for cell in line_approach(world_map, item)}


def _check_nothing_cut_off(world_map: Mapping[str, Any], staff: list[tuple[int, int]]) -> None:
    # Guests cannot cross staff cells, so a place reached only through them would be lost to guests.
    size, walls = (world_map["width"], world_map["height"]), impassable_cells(world_map)
    places = [tuple(spot) for item in world_map["objects"] for spot in item["interaction_spots"]]
    for spot in places:
        if find_path(places[0], spot, *size, walls) and not find_path(places[0], spot, *size, walls + staff):
            raise ValueError("Staff cells must not cut any place off from the rest of the hall")
