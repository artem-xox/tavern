"""Whether a wall stands on the straight line between two cells."""


def line_visible(origin: tuple[int, int], target: tuple[int, int], blocked: set[tuple[int, int]]) -> bool:
    """Tell whether a straight line between two cells passes no blocked cell.

    Args:
        origin: Viewer's cell.
        target: Cell looked at.
        blocked: Cells that hide what lies behind them.
    Returns:
        True when nothing blocks the view between the cells.
    """
    # Integer Bresenham visibility treats the endpoint itself as visible furniture.
    x, y = origin
    end_x, end_y = target
    dx, dy = abs(end_x - x), -abs(end_y - y)
    step_x, step_y = (1 if x < end_x else -1), (1 if y < end_y else -1)
    error = dx + dy
    while (x, y) != target:
        if (x, y) != origin and (x, y) in blocked:
            return False
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y
    return True
