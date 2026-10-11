"""Small eight-way A* paths, the length of a step, and interaction-point selection."""

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


def step_length(origin: Sequence[int], cell: Sequence[int]) -> float:
    """Measure one step of a route, in straight steps.

    Args:
        origin: Cell stepped from.
        cell: Cell next to it, straight or across a corner.

    Returns:
        1 for a straight step, the square root of 2 for a diagonal one: a visitor takes that much longer.
    """
    return 1.0 if origin[0] == cell[0] or origin[1] == cell[1] else 2 ** 0.5


def _octile(left: tuple[int, int], right: tuple[int, int]) -> float:
    # The cost of the cheapest walk on an open floor: as many diagonal steps as the shorter side, then straight.
    across, down = abs(left[0] - right[0]), abs(left[1] - right[1])
    return max(across, down) + (2 ** 0.5 - 1) * min(across, down)


def _reconstruct(came_from: dict[tuple[int, int], tuple[int, int]], goal: tuple[int, int]) -> list[tuple[int, int]]:
    path = [goal]
    while path[-1] in came_from:
        path.append(came_from[path[-1]])
    return list(reversed(path))


def _neighbors(point: tuple[int, int], width: int, height: int, blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
    x, y = point

    def free(a: int, b: int) -> bool:
        return 0 <= a < width and 0 <= b < height and (a, b) not in blocked

    straight = [(a, b) for a, b in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)) if free(a, b)]
    # A corner is crossed only where both cells beside it are free, so nobody cuts past an obstacle's edge
    # or slips between two that touch at their corners.
    across = [(x + dx, y + dy) for dx, dy in ((1, 1), (-1, 1), (-1, -1), (1, -1))
              if free(x + dx, y + dy) and free(x + dx, y) and free(x, y + dy)]
    return straight + across


def find_path(start: Sequence[int], goal: Sequence[int], width: int, height: int,
              blocked: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """Find a shortest eight-way path, including both endpoints.

    Args:
        start: Starting cell.
        goal: Destination cell.
        width: Positive grid width.
        height: Positive grid height.
        blocked: Obstacle cells; duplicates have no extra effect.

    Returns:
        Inclusive path, shortest in walking time (a diagonal step is the square root of 2 straight ones, and
        equal routes keep the order they were found in), or an empty list when either endpoint is blocked
        or unreachable.

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
    pending = [(_octile(start, goal), next(order), start)]
    costs: dict[tuple[int, int], float] = {start: 0.0}
    parents: dict[tuple[int, int], tuple[int, int]] = {}
    while pending:
        _, _, current = heappop(pending)
        if current == goal:
            return _reconstruct(parents, goal)
        for neighbor in _neighbors(current, width, height, blocked):
            cost = costs[current] + step_length(current, neighbor)
            if cost < costs.get(neighbor, float("inf")):
                costs[neighbor], parents[neighbor] = cost, current
                heappush(pending, (cost + _octile(neighbor, goal), next(order), neighbor))
    return []


def select_interaction_spot(start: Sequence[int], spots: Sequence[Sequence[int]],
                            width: int, height: int, blocked: Sequence[Sequence[int]]) -> tuple[tuple[int, int], list[tuple[int, int]]] | None:
    """Choose the reachable spot with the shortest walking time.

    Args:
        start: Starting cell.
        spots: Possible interaction cells; input order breaks ties in walking time.
        width: Grid width.
        height: Grid height.
        blocked: Obstacle cells.

    Returns:
        Selected cell and inclusive path, or None when no spot is reachable.

    Raises:
        ValueError: Grid dimensions or coordinates are malformed.
    """
    best = None
    best_time = float("inf")
    for spot in spots:
        position = _point(spot, width, height)
        path = find_path(start, position, width, height, blocked)
        walk = sum(step_length(a, b) for a, b in zip(path, path[1:]))
        if path and walk < best_time:
            best, best_time = (position, path), walk
    return best
