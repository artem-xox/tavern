"""A visitor's personal memories: the room's event log keeps everything recent, a guest the newest of their own."""

import pytest

from tavern.hall.memory import record_event
from tavern.hall.world import create_world
from social_hall import actor, hall


@pytest.mark.parametrize("count, kept", [
    pytest.param(0, [], id="nothing-happened"),
    pytest.param(1, [0], id="a-single-event"),
    pytest.param(100, list(range(100)), id="a-whole-evening-fits"),
    pytest.param(150, list(range(50, 150)), id="only-the-newest-hundred"),
])
def test_a_guest_remembers_the_newest_hundred_of_their_events(count: int, kept: list[int]) -> None:
    world = create_world(hall(), 4)
    ada = actor(world, "ada")
    ada["memory"] = []
    for number in range(count):
        record_event(world, ada, "served", f"Event {number}")
    assert [item["message"] for item in ada["memory"]] == [f"Event {number}" for number in kept]
