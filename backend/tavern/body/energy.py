"""Energy: what each activity costs a visitor in tiredness, and what a nap gives back."""

from tavern.body.activities import ACTIVITIES
from tavern.hall.staff import on_staff
from tavern.hall.state import World


def tire(world: World, elapsed: float) -> None:
    """Tire, or rest, every guest by the activity they walk to or are doing.

    A negative `Activity.fatigue_per_second` restores. Walking costs what the activity it walks for
    costs, so the way to one's own seat is free and the way to the darts is as tiring as the darts.
    Someone held up on their route, queued, or idle spends nothing here (hours at an inn still wear
    on them: see `need_rates`). Tiredness stays within 0 to 100.

    Args:
        world: World whose guests' `fatigue` is updated in place; staff are never tired by their work.
        elapsed: Game seconds since the last tick.
    """
    for actor in world["actors"]:
        action = actor["action"]
        if action is None or actor["status"] not in ("walking", "interacting") or on_staff(actor):
            continue
        needs = actor["needs"]
        needs["fatigue"] = min(100.0, max(0.0, needs["fatigue"] + ACTIVITIES[action["verb"]].fatigue_per_second * elapsed))
