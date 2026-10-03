"""Validated hall geometry: furniture footprints, obstacles, and table appeal."""

from collections.abc import Mapping
from copy import deepcopy
from math import hypot
from typing import Any

from tavern.navigation import find_path, select_interaction_spot
from tavern.validation import coordinate, number, position, unique_ids


def create_map(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the hall and rate its tables, without sharing the supplied records.

    Args:
        data: Room definition with dimensions, blocked cells, and objects.
    Returns:
        New map with validated objects, cleared reservations, and table/chair appeal.
    Raises:
        ValueError: Dimensions, footprints, kinds, stock, or interaction spots are invalid.
    """
    width, height = data.get("width"), data.get("height")
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("Map dimensions must be positive integers")
    result = {key: deepcopy(data.get(key, [])) for key in ("blocked", "objects")}
    result.update(width=width, height=height, tile_size=data.get("tile_size", 32))
    if type(result["tile_size"]) is not int or result["tile_size"] <= 0:
        raise ValueError("Tile size must be a positive integer")
    _validate_objects(result)
    _rate_tables(result)
    return result


def _comfort(source: Mapping[str, Any], table: Mapping[str, Any]) -> float:
    # A window or fireplace lends its whole appeal to tables within `reach` cells in a straight line.
    distance = min(hypot(x - a, y - b) for x, y in object_cells(source) for a, b in object_cells(table))
    return source["appeal"] if distance <= source["reach"] else 0.0


def _rate_tables(world_map: dict[str, Any]) -> None:
    sources = [item for item in world_map["objects"] if item["kind"] in ("window", "fireplace")]
    ratings = {}
    for table in (item for item in world_map["objects"] if item["kind"] == "table"):
        shares = [(source["kind"], _comfort(source, table)) for source in sources]
        ratings[table["id"]] = (min(1.0, sum(share for _, share in shares)),
                                sorted({kind for kind, share in shares if share > 0}))
    # Chairs share their table's rating: guests choose seats, but appeal comes from the spot.
    for item in world_map["objects"]:
        rating = ratings.get(item["id"] if item["kind"] == "table" else item.get("table_id"))
        if rating:
            item.update(appeal=rating[0], comforts=list(rating[1]))


def impassable_cells(world_map: Mapping[str, Any]) -> list[tuple[int, int]]:
    """List the cells nobody can stand on: walls and furniture other than chair seats.

    Args:
        world_map: Validated map.
    Returns:
        Blocked wall cells followed by every non-walkable furniture cell.
    """
    return [tuple(cell) for cell in world_map["blocked"]] + [
        cell for item in world_map["objects"] if not item.get("walkable", False)
        for cell in object_cells(item)]


def object_cells(item: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Return the complete rectangular footprint of furniture.

    Args:
        item: Validated object with an anchor and optional width/height in cells.
    Returns:
        Every occupied cell, including walkable chair seats.
    """
    return [(x, y) for y in range(item["y"], item["y"] + item.get("height", 1))
            for x in range(item["x"], item["x"] + item.get("width", 1))]


def find_object(world_map: Mapping[str, Any], object_id: Any) -> dict[str, Any] | None:
    """Find a piece of furniture by ID.

    Args:
        world_map: Validated map.
        object_id: Object ID, or anything else for a target-less action.
    Returns:
        The live object record, or None when no object has that ID.
    """
    return next((item for item in world_map["objects"] if item["id"] == object_id), None)


def line_approach(world_map: Mapping[str, Any], item: Mapping[str, Any]) -> list[tuple[int, int]]:
    """List the cells between the front of an object's line and the spot where it is used.

    Args:
        world_map: Validated map.
        item: Object with queue spots.
    Returns:
        The shortest walk past walls and furniture from the first queue spot to the nearest
        interaction spot, excluding the queue spot and including the interaction spot.
    """
    selected = select_interaction_spot(item["queue_spots"][0], item["interaction_spots"],
                                       world_map["width"], world_map["height"], impassable_cells(world_map))
    if selected is None:
        raise ValueError("The front of a line must reach its object")
    return selected[1][1:]


def _validate_footprint(item: Mapping[str, Any], world_map: Mapping[str, Any]) -> None:
    position(item, world_map["width"], world_map["height"])
    for name in ("width", "height"):
        if type(item.get(name, 1)) is not int or item.get(name, 1) <= 0:
            raise ValueError("Furniture dimensions must be positive integers")
    for x, y in object_cells(item):
        coordinate(x, world_map["width"])
        coordinate(y, world_map["height"])
    if type(item.get("walkable", False)) is not bool:
        raise ValueError("Furniture walkability must be a boolean")
    if item.get("walkable") and item.get("kind") != "chair":
        raise ValueError("Only chair seats may be walkable furniture")


def _validate_objects(world_map: dict[str, Any]) -> None:
    unique_ids(world_map["objects"], "object")
    occupied: set[tuple[int, int]] = set()
    for item in world_map["objects"]:
        _validate_footprint(item, world_map)
        cells = set(object_cells(item))
        if cells & (occupied | set(map(tuple, world_map["blocked"]))):
            raise ValueError("Objects must occupy distinct unblocked cells")
        _validate_kind(item)
        occupied.update(cells)
        item.setdefault("interaction_spots", [])
        item.setdefault("name", item["id"])
        item.update(stock=item.get("stock", 0), reserved_by=None)
        if type(item["stock"]) is not int or item["stock"] < 0:
            raise ValueError("Object stock must be a nonnegative integer")
    _validate_spots(world_map)
    _validate_lines(world_map)


def _validate_kind(item: Mapping[str, Any]) -> None:
    kinds = ("tap", "chair", "toilet", "table", "bar", "darts", "door", "window", "fireplace")
    if item.get("kind") not in kinds:
        raise ValueError("Unknown object kind")
    if item["kind"] in ("window", "fireplace"):
        number(item.get("appeal"), "Comfort appeal", 0, 1)
        if type(item.get("reach")) is not int or item["reach"] <= 0:
            raise ValueError("Comfort reach must be a positive integer")


def _validate_spots(world_map: Mapping[str, Any]) -> None:
    obstacles = impassable_cells(world_map)
    # find_path performs strict validation of every static obstacle coordinate.
    find_path((0, 0), (0, 0), world_map["width"], world_map["height"], obstacles)
    for item in world_map["objects"]:
        spots = item.get("interaction_spots", [])
        if not spots and item["kind"] not in ("table", "bar", "window", "fireplace"):
            raise ValueError("Every object needs an interaction spot")
        for spot in spots:
            if not find_path(spot, spot, world_map["width"], world_map["height"], obstacles):
                raise ValueError("Interaction spots must be walkable")
        if item.get("table_id") is not None and not any(
                table["id"] == item["table_id"] and table["kind"] == "table"
                for table in world_map["objects"]):
            raise ValueError("Chair table must refer to an existing table")


def _validate_lines(world_map: dict[str, Any]) -> None:
    # A line forms on its queue spots, in order, outside the way in and out of every lined place,
    # so nobody waiting can block someone leaving (the WC is a dead end behind a narrow doorway).
    lined = [item for item in world_map["objects"] if "queue_spots" in item]
    for item in lined:
        spots = item["queue_spots"]
        if not isinstance(spots, list) or not spots or not all(isinstance(spot, list) and len(spot) == 2
                                                              for spot in spots):
            raise ValueError("Queue spots must be a nonempty list of cells")
        for x, y in spots:
            coordinate(x, world_map["width"])
            coordinate(y, world_map["height"])
        if len(item["interaction_spots"]) != 1:
            raise ValueError("A place with a line is used by one visitor at a time, from one spot")
        item["queue"] = []
    blocked = set(impassable_cells(world_map))
    kept = {tuple(spot) for item in world_map["objects"] for spot in item["interaction_spots"]}
    kept |= {cell for item in lined for cell in line_approach(world_map, item)}
    spots = [tuple(spot) for item in lined for spot in item["queue_spots"]]
    if len(set(spots)) != len(spots):
        raise ValueError("Queue spots must be distinct cells")
    for spot in spots:
        if spot in blocked or spot in kept:
            raise ValueError("Queue spots must be free cells off every interaction spot and way in")
    _check_nothing_cut_off(world_map, spots)


def _check_nothing_cut_off(world_map: Mapping[str, Any], queue_spots: list[tuple[int, int]]) -> None:
    # A full line must not wall anything off, such as a dead-end WC behind its doorway.
    size, walls = (world_map["width"], world_map["height"]), impassable_cells(world_map)
    places = [spot for item in world_map["objects"] for spot in item["interaction_spots"]]
    for spot in places:
        if find_path(places[0], spot, *size, walls) and not find_path(places[0], spot, *size, walls + queue_spots):
            raise ValueError("A full line must not cut any place off from the rest of the hall")
