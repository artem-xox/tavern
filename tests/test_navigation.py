"""Navigation behavior for room paths: eight ways, with no cutting a corner."""

import pytest

from tavern.hall.navigation import find_path, select_interaction_spot, step_length


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


@pytest.mark.parametrize(
    "goal, blocked, expected",
    [
        pytest.param((2, 2), [], [(0, 0), (1, 1), (2, 2)], id="open-floor-goes-corner-to-corner"),
        pytest.param((1, 1), [(1, 0)], [(0, 0), (0, 1), (1, 1)], id="no-cutting-a-corner-past-an-obstacle"),
        pytest.param((1, 1), [(1, 0), (0, 1)], [], id="no-squeezing-between-two-diagonal-obstacles"),
    ],
)
def test_path_steps_across_a_corner_only_when_both_sides_are_free(
        goal: tuple[int, int], blocked: list[tuple[int, int]], expected: list[tuple[int, int]]) -> None:
    assert find_path((0, 0), goal, 3, 3, blocked) == expected


def test_path_takes_a_diagonal_where_it_is_shorter_than_two_straight_steps() -> None:
    path = find_path((0, 0), (3, 1), 5, 3, [])
    assert [(a[0] != b[0] and a[1] != b[1]) for a, b in zip(path, path[1:])].count(True) == 1
    assert len(path) == 4


@pytest.mark.parametrize(
    "origin, cell, expected",
    [
        pytest.param((2, 2), (3, 2), 1.0, id="straight-across"),
        pytest.param((2, 2), (2, 1), 1.0, id="straight-up"),
        pytest.param((2, 2), (3, 3), 2 ** 0.5, id="diagonal"),
    ],
)
def test_a_diagonal_step_is_longer_than_a_straight_one(origin: tuple[int, int], cell: tuple[int, int],
                                                       expected: float) -> None:
    assert step_length(origin, cell) == pytest.approx(expected)


def test_selects_the_spot_that_takes_least_time_not_the_fewest_cells() -> None:
    # Three diagonal steps (4.24) are a longer walk than four straight ones (4.0), though fewer cells.
    selected = select_interaction_spot((0, 0), [(3, 3), (4, 0)], 5, 5, [])
    assert selected is not None and selected[0] == (4, 0)
