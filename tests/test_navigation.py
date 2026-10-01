"""Navigation behavior for four-way room paths."""

import pytest

from tavern.navigation import find_path, select_interaction_spot


@pytest.mark.parametrize(
    "blocked, expected",
    [
        pytest.param([], [(0, 0), (1, 0), (2, 0)], id="empty-obstacles"),
        pytest.param([(1, 0)], [(0, 0), (0, 1), (1, 1), (2, 1), (2, 0)], id="single-obstacle"),
        pytest.param([(1, 0), (1, 0)], [(0, 0), (0, 1), (1, 1), (2, 1), (2, 0)], id="duplicate-obstacles"),
        pytest.param([(1, 0), (1, 1)], [], id="unreachable"),
    ],
)
def test_path_routes_around_obstacles(blocked: list[tuple[int, int]], expected: list[tuple[int, int]]) -> None:
    assert find_path((0, 0), (2, 0), 3, 2, blocked) == expected


@pytest.mark.parametrize(
    "start, goal, width, blocked",
    [
        pytest.param((-1, 0), (2, 0), 3, [], id="invalid-start"),
        pytest.param((0, 0), (3, 0), 3, [], id="invalid-goal"),
        pytest.param((0, 0), (2, 0), 0, [], id="empty-grid"),
        pytest.param((0, 0), (2, 0), 3, [("bad", 0)], id="malformed-obstacle"),
    ],
)
def test_path_rejects_invalid_grid(start: tuple[int, int], goal: tuple[int, int], width: int, blocked: list[tuple[int, int]]) -> None:
    with pytest.raises(ValueError):
        find_path(start, goal, width, 2, blocked)


@pytest.mark.parametrize(
    "spots, expected",
    [
        pytest.param([], None, id="empty-spots"),
        pytest.param([(0, 1)], (0, 1), id="single-spot"),
        pytest.param([(0, 1), (0, 1)], (0, 1), id="duplicate-spots"),
        pytest.param([(2, 0), (0, 3)], (0, 3), id="closer-object-longer-route"),
    ],
)
def test_selects_reachable_spot_by_route_length(spots: list[tuple[int, int]], expected: tuple[int, int] | None) -> None:
    selected = select_interaction_spot((0, 0), spots, 5, 5, [(1, 0), (1, 1), (1, 2)])
    assert (selected[0] if selected else None) == expected


def test_malformed_interaction_spot_is_rejected() -> None:
    with pytest.raises(ValueError):
        select_interaction_spot((0, 0), [(1,)], 5, 5, [])
