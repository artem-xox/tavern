"""Small four-way A* paths and interaction-point selection."""

from collections.abc import Sequence
from heapq import heappop, heappush
from itertools import count


def _point(value: Sequence[int], width: int, height: int) -> tuple[int, int]:
    if len(value) != 2 or any(type(item) is not int for item in value):
        raise ValueError("Coordinates must contain two integers")
    x, y = value
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError("Coordinates must be inside the map")
    return x, y


def _distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _reconstruct(came_from: dict[tuple[int, int], tuple[int, int]], goal: tuple[int, int]) -> list[tuple[int, int]]:
    path = [goal]
    while path[-1] in came_from:
        path.append(came_from[path[-1]])
    return list(reversed(path))


def _neighbors(point: tuple[int, int], width: int, height: int, blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
    x, y = point
    return [(a, b) for a, b in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1))
            if 0 <= a < width and 0 <= b < height and (a, b) not in blocked]


def find_path(start: Sequence[int], goal: Sequence[int], width: int, height: int,
              blocked: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """Find a shortest four-way path, including both endpoints.

    Args:
        start: Starting cell.
        goal: Destination cell.
        width: Positive grid width.
        height: Positive grid height.
        blocked: Obstacle cells; duplicates have no extra effect.

    Returns:
        Inclusive path, or an empty list when either endpoint is blocked or unreachable.

    Raises:
        ValueError: Grid dimensions or coordinates are malformed.
    """
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("Map dimensions must be positive integers")
    origin, destination = _point(start, width, height), _point(goal, width, height)
    obstacles = {_point(item, width, height) for item in blocked}
    if origin in obstacles or destination in obstacles:
        return []
    return _search(origin, destination, width, height, obstacles)


def _search(start: tuple[int, int], goal: tuple[int, int], width: int, height: int,
            blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
    order = count()
    pending = [(_distance(start, goal), next(order), start)]
    costs: dict[tuple[int, int], int] = {start: 0}
    parents: dict[tuple[int, int], tuple[int, int]] = {}
    while pending:
        _, _, current = heappop(pending)
        if current == goal:
            return _reconstruct(parents, goal)
        for neighbor in _neighbors(current, width, height, blocked):
            cost = costs[current] + 1
            if cost < costs.get(neighbor, float("inf")):
                costs[neighbor], parents[neighbor] = cost, current
                heappush(pending, (cost + _distance(neighbor, goal), next(order), neighbor))
    return []


def select_interaction_spot(start: Sequence[int], spots: Sequence[Sequence[int]],
                            width: int, height: int, blocked: Sequence[Sequence[int]]) -> tuple[tuple[int, int], list[tuple[int, int]]] | None:
    """Choose the reachable spot with the shortest walking route.

    Args:
        start: Starting cell.
        spots: Possible interaction cells; input order breaks route-length ties.
        width: Grid width.
        height: Grid height.
        blocked: Obstacle cells.

    Returns:
        Selected cell and inclusive path, or None when no spot is reachable.

    Raises:
        ValueError: Grid dimensions or coordinates are malformed.
    """
    best = None
    for spot in spots:
        position = _point(spot, width, height)
        path = find_path(start, position, width, height, blocked)
        if path and (best is None or len(path) < len(best[1])):
            best = position, path
    return best
