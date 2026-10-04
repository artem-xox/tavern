"""Staff: who works behind a bar, and the cells only they walk on."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.navigation import find_path
from tavern.hall.room import find_object, impassable_cells, line_approach, object_cells
from tavern.hall.state import Actor

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


def on_staff(actor: Mapping[str, Any]) -> bool:
    """Tell whether a visitor works at a bar rather than visiting.

    Args:
        actor: Visitor; one without a `post` (a hand-made test visitor) is a guest.

    Returns:
        True when their `post` names a bar.
    """
    return actor.get("post") is not None


def guests(world: Mapping[str, Any]) -> list[Actor]:
    """List the visitors in the hall who came for the evening, not to work.

    Args:
        world: Current world.

    Returns:
        Present visitors without a post, in actor order.
    """
    return [actor for actor in world["actors"] if not on_staff(actor)]


def tended(world: Mapping[str, Any]) -> bool:
    """Tell whether anyone is at work behind a bar, so that the bar serves its guests.

    Args:
        world: Current world.

    Returns:
        True while a staff member is in the hall.
    """
    return any(on_staff(actor) for actor in world["actors"])


def post_of(world_map: Mapping[str, Any], actor: Mapping[str, Any]) -> Mapping[str, Any]:
    """Find the bar a staff member works at.

    Args:
        world_map: Validated map.
        actor: Visitor on staff.

    Returns:
        The bar, which has staff cells.

    Raises:
        ValueError: Their post is no bar with staff cells.
    """
    bar = find_object(world_map, actor.get("post"))
    if bar is None or bar["kind"] != "bar" or not bar.get("staff_cells"):
        raise ValueError(f"Staff post {actor.get('post')!r} must be a bar with staff cells")
    return bar


def pour_cell(world_map: Mapping[str, Any], bar: Mapping[str, Any]) -> tuple[int, int]:
    """Find the staff cell where a bar's staff stand to serve a tap.

    Args:
        world_map: Validated map.
        bar: Bar with staff cells.

    Returns:
        The first staff cell, in listed order, that is orthogonally next to a tap.

    Raises:
        ValueError: No staff cell is next to a tap (`check_staff_cells` forbids it).
    """
    taps = {cell for item in world_map["objects"] if item["kind"] == "tap" for cell in object_cells(item)}
    for x, y in bar["staff_cells"]:
        if any((x + dx, y + dy) in taps for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            return (x, y)
    raise ValueError(f"Bar {bar['id']!r} has no staff cell next to a tap")


def facing_of(world_map: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    """Tell which way a staff member looks when nothing turns their head.

    Args:
        world_map: Validated map.
        actor: Visitor.

    Returns:
        Their bar's `staff_facing`, or None for a guest, whose seat or task decides.
    """
    return post_of(world_map, actor)["staff_facing"] if on_staff(actor) else None


def off_limits(world_map: Mapping[str, Any], actor: Mapping[str, Any]) -> list[tuple[int, int]]:
    """List the cells a visitor may not walk on.

    Args:
        world_map: Validated map.
        actor: The visitor who walks.

    Returns:
        For a guest, the staff cells of every bar, in map order. For a staff member, every cell of
        the hall but the staff cells of their own bar.
    """
    if on_staff(actor):
        own = {tuple(cell) for cell in post_of(world_map, actor)["staff_cells"]}
        return [(x, y) for y in range(world_map["height"]) for x in range(world_map["width"]) if (x, y) not in own]
    return [(x, y) for item in world_map["objects"] for x, y in item.get("staff_cells", [])]


def check_saved_staff(world: Mapping[str, Any]) -> None:
    """Check the posts of a saved world's visitors.

    Args:
        world: Decoded save whose actors and departed visitors each carry a `post`.

    Raises:
        ValueError: A visitor lacks a post or has one that is not a string or null; staff have left,
            sit on a seat, stand off their bar's staff cells or work at something that is no bar with
            staff cells; a bar has two staff members; or a guest stands on a staff cell.
    """
    people = [*world["actors"], *world["departed"]]
    if any("post" not in person or not (person["post"] is None or isinstance(person["post"], str))
           for person in people):
        raise ValueError("Invalid saved post")
    if any(person["post"] is not None for person in world["departed"]):
        raise ValueError("Saved staff cannot have gone home")
    bars = {item["id"]: item for item in world["map"]["objects"] if item["kind"] == "bar" and item.get("staff_cells")}
    behind = {tuple(cell) for bar in bars.values() for cell in bar["staff_cells"]}
    posts = [person["post"] for person in world["actors"] if person["post"] is not None]
    if len(set(posts)) != len(posts):
        raise ValueError("Saved bar has more than one staff member")
    for person in world["actors"]:
        if person["post"] is None:
            if (person["x"], person["y"]) in behind:
                raise ValueError("Saved guest stands behind the bar")
        elif person["post"] not in bars or person["seat_id"] is not None or [
                person["x"], person["y"]] not in bars[person["post"]]["staff_cells"]:
            raise ValueError("Saved staff member must stand on the staff cells of a bar, unseated")


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
